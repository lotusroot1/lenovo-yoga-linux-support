"""
Clean, single-path fingerprint capture for the Goodix 27c6:550c sensor.

Validated working sequence (see ../FINDINGS.md for full write-up):

1. TLS-PSK handshake using a captured PSK (see FINDINGS.md for how to get
   your own - not included here, it's per-device key material).
2. upload_config_mcu (0x90) with the captured 256-byte config blob.
3. mcu_switch_to_fdt_down (0x32) with a captured 24-byte threshold sample -
   this is what arms the sensor; without it mcu_get_image returns all zeros.
   mcu_switch_to_fdt_mode (0x36) is NOT required for a basic capture (never
   captured, never needed so far).
4. mcu_get_image (0x20) -> 14334-byte outer payload (flags 0xB2) -> strip
   first 9 bytes -> forward into the TLS socket -> openssl s_server decrypts
   and echoes 14260 bytes of plaintext to its stdout -> strip last 4 bytes
   -> 12-bit-packed pixel decode (6 bytes -> 4 pixels) -> 88x108 image,
   stored column-major (pixel(x, y) = image[x*height + y]).

Raw pixel data has a real per-column gain/offset artifact (confirmed via a
background-subtracted diff between a no-finger and a finger frame - present
identically in both, so it's the sensor's raw uncalibrated output, not a
capture bug). Per-column z-score normalization (subtract each column's own
mean, divide by its own stdev) removes it and reveals actual ridge/valley
detail cleanly - confirmed against two live finger captures.

Usage: python3 capture_fingerprint_linux.py [output_basename]
Expects a captured PSK at dumps/CAPTURED_PSK.txt (relative to this file's
parent's parent, i.e. biometrics/dumps/CAPTURED_PSK.txt) in the format:
  PSK (hex): <64 hex chars>
Writes dumps/<basename>_raw.bin, _raw.png, _zscore.png.
"""

import os
import select
import struct
import socket
import subprocess
import sys
import time
import usb.core
import usb.util
from PIL import Image

VID = 0x27C6
PID = 0x550C
EP_OUT = 0x01
EP_IN = 0x83

FLAGS_MESSAGE_PROTOCOL = 0xA0
FLAGS_TRANSPORT_LAYER_SECURITY = 0xB0
FLAGS_TRANSPORT_LAYER_SECURITY_DATA = 0xB2

COMMAND_ACK = 0xB0
COMMAND_REQUEST_TLS_CONNECTION = 0xD0
COMMAND_MCU_GET_IMAGE = 0x20
COMMAND_MCU_SWITCH_TO_FDT_DOWN = 0x32
COMMAND_UPLOAD_CONFIG_MCU = 0x90

OPENSSL = "openssl"
WIDTH, HEIGHT = 88, 108

# Chip-specific config blob, captured via a plain (non-TLS) USB packet
# capture of the stock Windows driver initializing the sensor for a normal
# fingerprint verification. Not secret - it's a calibration constant, not a
# per-device key (compare to the community goodix-fp-dump project's public
# DEVICE_CONFIG for the sibling 55x4 chip family).
CONFIG_BLOB = bytes.fromhex(
    "40116c7d28a528cd1ce910f900f900f9000402000008001111ba000180ca0007"
    "008400beb28600c5b98800b5ad8a009d958c0000be8e0000c5900000b59200009d940000"
    "af960000bf980000b69a0000a730006c1c50000105d0000000700000007200785674003"
    "412260000122000104012000304020216212c020a032a0102002200012024003200800005"
    "045c0000015600282058000100320024028200800c2002880d2a0192072200012024001400"
    "800005045c009000560008205800030032000804820080112002380c2a0118045c0090005"
    "400000162000903640018008200800c2002380c2a0118045c0090005200080054000001000"
    "000000051ff")
assert len(CONFIG_BLOB) == 256

# One sample of the FDT_DOWN threshold buffer - this data varies slightly
# per call in a live driver (finger-detect thresholds get live-adapted), but
# a single captured sample is enough to arm the sensor for a basic capture.
FDT_DOWN_SAMPLE = bytes.fromhex("9797a2a2a0a094949797a3a3a1a1989893939f9f9c9c9393")
assert len(FDT_DOWN_SAMPLE) == 24


def encode_message_protocol(payload: bytes, command: int) -> bytes:
    length = len(payload) + 1
    data = bytes([command]) + struct.pack("<H", length) + payload
    checksum = (0xAA - sum(data)) & 0xFF
    return data + bytes([checksum])


def encode_message_pack(inner: bytes, flags: int = FLAGS_MESSAGE_PROTOCOL) -> bytes:
    header = bytes([flags]) + struct.pack("<H", len(inner))
    checksum = sum(header) & 0xFF
    return header + bytes([checksum]) + inner


def decode_message_pack(data: bytes):
    flags = data[0]
    length = struct.unpack("<H", data[1:3])[0]
    payload = data[4:4 + length]
    return payload, flags, length


def check_message_pack(data: bytes, expected_flags: int) -> bytes:
    payload, flags, length = decode_message_pack(data)
    if flags != expected_flags:
        raise ValueError(f"Unexpected outer flags: got 0x{flags:02x}, expected 0x{expected_flags:02x}")
    if len(payload) < length:
        raise ValueError(f"Truncated message: got {len(payload)} bytes, declared {length}")
    return payload


class UsbDevice:
    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise RuntimeError("Device not found")
        try:
            self.dev.reset()
            time.sleep(0.5)
            self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        except usb.core.USBError as e:
            print(f"(reset warning, continuing: {e})")
        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, 0)

    def write(self, data: bytes):
        self.dev.write(EP_OUT, data, timeout=5000)

    def read(self, size=4096, timeout=5000) -> bytes:
        return bytes(self.dev.read(EP_IN, size, timeout=timeout))

    def close(self):
        usb.util.release_interface(self.dev, 0)
        usb.util.dispose_resources(self.dev)


def drain(usbdev: UsbDevice):
    while True:
        try:
            usbdev.read(4096, timeout=200)
        except usb.core.USBTimeoutError:
            break


def request_tls_connection(usbdev: UsbDevice) -> bytes:
    msg = encode_message_pack(encode_message_protocol(b"\x00\x00", COMMAND_REQUEST_TLS_CONNECTION))
    usbdev.write(msg)

    first_raw = usbdev.read()
    first_payload, first_flags, _ = decode_message_pack(first_raw)
    if first_flags == FLAGS_MESSAGE_PROTOCOL:
        tls_raw = usbdev.read()
        tls_payload = check_message_pack(tls_raw, FLAGS_TRANSPORT_LAYER_SECURITY)
    elif first_flags == FLAGS_TRANSPORT_LAYER_SECURITY:
        tls_payload = first_payload
    else:
        raise ValueError(f"Unexpected first-frame flags: 0x{first_flags:02x}")
    return tls_payload


def do_handshake(usbdev: UsbDevice, tls_client: socket.socket):
    client_hello = request_tls_connection(usbdev)
    tls_client.sendall(client_hello)

    time.sleep(0.05)
    server_response = tls_client.recv(4096)
    usbdev.write(encode_message_pack(server_response, FLAGS_TRANSPORT_LAYER_SECURITY))

    for _ in range(3):
        raw = usbdev.read()
        payload = check_message_pack(raw, FLAGS_TRANSPORT_LAYER_SECURITY)
        tls_client.sendall(payload)

    time.sleep(0.05)
    final_response = tls_client.recv(4096)
    usbdev.write(encode_message_pack(final_response, FLAGS_TRANSPORT_LAYER_SECURITY))
    time.sleep(0.05)


def send_command(usbdev: UsbDevice, payload: bytes, command: int, read_timeout=8000):
    frame = encode_message_pack(encode_message_protocol(payload, command))
    usbdev.write(frame)
    usbdev.read(4096, timeout=read_timeout)  # ACK, not strictly validated
    return usbdev.read(65536, timeout=read_timeout)  # actual response


def get_image(usbdev: UsbDevice, read_timeout=8000):
    frame = encode_message_pack(encode_message_protocol(b"\x01\x00", COMMAND_MCU_GET_IMAGE))
    usbdev.write(frame)
    usbdev.read(4096, timeout=read_timeout)  # ACK
    resp_raw = usbdev.read(65536, timeout=read_timeout)
    payload, flags, length = decode_message_pack(resp_raw)
    return payload, flags


def read_stdout_for(proc, duration=3.0):
    end = time.time() + duration
    buf = b""
    while True:
        remaining = end - time.time()
        if remaining <= 0:
            break
        r, _, _ = select.select([proc.stdout], [], [], remaining)
        if not r:
            break
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            break
        buf += chunk
    return buf


def decode_pixels(data: bytes):
    image = []
    for i in range(0, len(data), 6):
        chunk = data[i:i + 6]
        image.append(((chunk[0] & 0xf) << 8) + chunk[1])
        image.append((chunk[3] << 4) + (chunk[0] >> 4))
        image.append(((chunk[5] & 0xf) << 8) + chunk[2])
        image.append((chunk[4] << 4) + (chunk[5] >> 4))
    return image


def zscore_columns(pixels, width, height):
    corrected = [0.0] * (width * height)
    for x in range(width):
        col = pixels[x * height:(x + 1) * height]
        m = sum(col) / len(col)
        std = max((sum((v - m) ** 2 for v in col) / len(col)) ** 0.5, 1.0)
        for y in range(height):
            corrected[x * height + y] = (pixels[x * height + y] - m) / std
    return corrected


def to_png(values, width, height, scale=4):
    vmin, vmax = min(values), max(values)
    span = max(1e-9, vmax - vmin)
    im = Image.new("L", (width, height))
    px = im.load()
    for x in range(width):
        for y in range(height):
            px[x, y] = int((values[x * height + y] - vmin) * 255 / span)
    return im.resize((width * scale, height * scale), Image.NEAREST)


def capture_one(dumpdir: str):
    with open(os.path.join(dumpdir, "CAPTURED_PSK.txt")) as f:
        psk_hex = next(line.split(":", 1)[1].strip() for line in f if line.startswith("PSK (hex):"))

    server_proc = subprocess.Popen(
        [OPENSSL, "s_server", "-nocert", "-psk", psk_hex, "-psk_identity", "Client_identity",
         "-port", "4433", "-tls1_2", "-cipher", "PSK-AES128-CBC-SHA256:@SECLEVEL=0", "-quiet"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE
    )
    time.sleep(1.0)
    if server_proc.poll() is not None:
        raise RuntimeError("openssl s_server exited early: " + server_proc.stdout.read().decode(errors="replace"))

    usbdev = UsbDevice()
    drain(usbdev)
    tls_client = socket.socket()
    tls_client.settimeout(5.0)
    tls_client.connect(("localhost", 4433))

    try:
        do_handshake(usbdev, tls_client)
        send_command(usbdev, CONFIG_BLOB, COMMAND_UPLOAD_CONFIG_MCU)
        send_command(usbdev, FDT_DOWN_SAMPLE, COMMAND_MCU_SWITCH_TO_FDT_DOWN)
        img_payload, img_flags = get_image(usbdev)
        if img_flags != FLAGS_TRANSPORT_LAYER_SECURITY_DATA:
            raise ValueError(f"Unexpected image response flags 0x{img_flags:02x}")

        tls_client.sendall(img_payload[9:])
        plaintext = read_stdout_for(server_proc, duration=3.0)
        if len(plaintext) < 4:
            raise ValueError(f"Decrypted image too short: {len(plaintext)} bytes")
        return plaintext[:-4]
    finally:
        usbdev.close()
        tls_client.close()
        time.sleep(0.2)
        server_proc.terminate()


def main():
    basename = sys.argv[1] if len(sys.argv) > 1 else "capture"
    dumpdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dumps")
    os.makedirs(dumpdir, exist_ok=True)

    raw = capture_one(dumpdir)
    pixels = decode_pixels(raw)
    print(f"Captured {len(pixels)} pixels ({WIDTH}x{HEIGHT}), "
          f"min={min(pixels)} max={max(pixels)} avg={sum(pixels)/len(pixels):.1f}")

    with open(os.path.join(dumpdir, f"{basename}_raw.bin"), "wb") as f:
        f.write(raw)

    to_png(pixels, WIDTH, HEIGHT).save(os.path.join(dumpdir, f"{basename}_raw.png"))
    z = zscore_columns(pixels, WIDTH, HEIGHT)
    to_png(z, WIDTH, HEIGHT).save(os.path.join(dumpdir, f"{basename}_zscore.png"))
    print(f"Saved dumps/{basename}_raw.bin, _raw.png, _zscore.png")


if __name__ == "__main__":
    main()
