"""
Establishes a live TLS-PSK session with the Goodix 27c6:550c sensor using a
captured PSK, bridging raw TLS bytes between the USB device and a local
`openssl s_server` process. Standalone diagnostic - confirms the handshake
completes without going on to capture an image. See ../FINDINGS.md.
"""

import struct
import socket
import subprocess
import time
import sys
import usb.core
import usb.util

VID = 0x27C6
PID = 0x550C
EP_OUT = 0x01
EP_IN = 0x83

FLAGS_MESSAGE_PROTOCOL = 0xA0
FLAGS_TRANSPORT_LAYER_SECURITY = 0xB0
FLAGS_TRANSPORT_LAYER_SECURITY_DATA = 0xB2

COMMAND_ACK = 0xB0
COMMAND_REQUEST_TLS_CONNECTION = 0xD0

OPENSSL = "openssl"


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


def check_message_pack(data: bytes, expected_flags: int = FLAGS_MESSAGE_PROTOCOL) -> bytes:
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
        print("USB interface claimed.")

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
    print("request_tls_connection()")
    msg = encode_message_pack(encode_message_protocol(b"\x00\x00", COMMAND_REQUEST_TLS_CONNECTION))
    usbdev.write(msg)

    first_raw = usbdev.read()
    first_payload, first_flags, _ = decode_message_pack(first_raw)
    if first_flags == FLAGS_MESSAGE_PROTOCOL:
        print("ACK payload:", first_payload.hex())
        tls_raw = usbdev.read()
        tls_payload = check_message_pack(tls_raw, FLAGS_TRANSPORT_LAYER_SECURITY)
    elif first_flags == FLAGS_TRANSPORT_LAYER_SECURITY:
        print("No separate ACK frame this time - first read was already the ClientHello.")
        tls_payload = first_payload
    else:
        raise ValueError(f"Unexpected first-frame flags: 0x{first_flags:02x}")
    print(f"Got TLS handshake data from sensor ({len(tls_payload)} bytes): {tls_payload.hex()}")
    return tls_payload


def connect_device(usbdev: UsbDevice, tls_client: socket.socket):
    client_hello = request_tls_connection(usbdev)
    tls_client.sendall(client_hello)

    time.sleep(0.05)
    server_response = tls_client.recv(4096)
    print(f"OpenSSL response 1 ({len(server_response)} bytes)")
    usbdev.write(encode_message_pack(server_response, FLAGS_TRANSPORT_LAYER_SECURITY))

    for i in range(3):
        raw = usbdev.read()
        payload = check_message_pack(raw, FLAGS_TRANSPORT_LAYER_SECURITY)
        print(f"Device flight {i+2} ({len(payload)} bytes): {payload[:16].hex()}...")
        tls_client.sendall(payload)

    time.sleep(0.05)
    final_response = tls_client.recv(4096)
    print(f"OpenSSL final response ({len(final_response)} bytes)")
    usbdev.write(encode_message_pack(final_response, FLAGS_TRANSPORT_LAYER_SECURITY))

    time.sleep(0.01)
    print("Handshake sequence complete.")


def main():
    with open("dumps/CAPTURED_PSK.txt") as f:
        for line in f:
            if line.startswith("PSK (hex):"):
                psk_hex = line.split(":", 1)[1].strip()
                break
    print(f"Using PSK: {psk_hex[:8]}...{psk_hex[-8:]} ({len(psk_hex)//2} bytes)")

    print("Starting openssl s_server...")
    server_proc = subprocess.Popen(
        [OPENSSL, "s_server", "-nocert", "-psk", psk_hex, "-psk_identity", "Client_identity",
         "-port", "4433", "-tls1_2", "-cipher", "PSK-AES128-CBC-SHA256:@SECLEVEL=0", "-state", "-msg"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE
    )
    time.sleep(1.0)
    if server_proc.poll() is not None:
        print("openssl s_server exited early!")
        print(server_proc.stdout.read())
        sys.exit(1)

    usbdev = UsbDevice()
    print("Draining stale USB data...")
    drain(usbdev)

    tls_client = socket.socket()
    tls_client.settimeout(5.0)
    tls_client.connect(("localhost", 4433))
    print("Connected to local openssl s_server.")

    try:
        connect_device(usbdev, tls_client)
        print("\n*** If no exceptions above, TLS handshake bridge completed! ***")
        print("Checking openssl s_server output for handshake success message...")
        time.sleep(0.5)
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
    finally:
        usbdev.close()
        tls_client.close()
        time.sleep(0.5)
        time.sleep(0.3)
        server_proc.terminate()
        try:
            out = server_proc.stdout.read()
            print("=== full openssl output ===")
            print(out.decode(errors="replace"))
        except Exception:
            pass


if __name__ == "__main__":
    main()
