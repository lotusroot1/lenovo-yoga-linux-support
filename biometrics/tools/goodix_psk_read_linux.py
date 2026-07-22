"""
Reads the sealed PSK blob directly from the Goodix 27c6:550c sensor via
libusb. This only returns a short ACK, not the raw key - the actual PSK
requires a live-memory capture from the Windows OEM driver (see
../FINDINGS.md). Useful mainly to confirm the message-pack/message-protocol
framing round-trips correctly against real hardware before attempting the
full TLS bridge.
"""

import struct
import sys
import usb.core
import usb.util

VID = 0x27C6
PID = 0x550C
EP_OUT = 0x01
EP_IN = 0x83

COMMAND_PRESET_PSK_READ_R = 0xe4
PSK_DATA_TYPE = 0xbb010002


def encode_message_protocol(payload: bytes, command: int) -> bytes:
    length = len(payload) + 1
    data = bytes([command]) + struct.pack("<H", length) + payload
    checksum = (0xAA - sum(data)) & 0xFF
    return data + bytes([checksum])


def encode_message_pack(inner: bytes, flags: int = 0xA0) -> bytes:
    header = bytes([flags]) + struct.pack("<H", len(inner))
    checksum = sum(header) & 0xFF
    return header + bytes([checksum]) + inner


COMMAND_NOP = 0x00


def nop_message() -> bytes:
    inner = encode_message_protocol(b"\x00\x00\x00\x00", COMMAND_NOP)
    return encode_message_pack(inner)


def preset_psk_read_message(flags: int) -> bytes:
    payload = struct.pack("<II", flags, 0)
    return encode_message_pack(encode_message_protocol(payload, COMMAND_PRESET_PSK_READ_R))


def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("Device not found")
        sys.exit(1)

    dev.set_configuration()
    usb.util.claim_interface(dev, 0)
    print("Interface claimed successfully.")

    try:
        print("Draining any stale buffered data...")
        drained = 0
        while True:
            try:
                stale = dev.read(EP_IN, 512, timeout=300)
                drained += 1
                print(f"  drained {len(stale)} bytes: {bytes(stale).hex()}")
            except usb.core.USBTimeoutError:
                break
        print(f"Drain complete ({drained} stale packets).")

        nop = nop_message()
        print("Sending NOP:", nop.hex())
        dev.write(EP_OUT, nop, timeout=3000)
        nop_resp = dev.read(EP_IN, 512, timeout=3000)
        print(f"NOP response ({len(nop_resp)} bytes):", bytes(nop_resp).hex())

        msg = preset_psk_read_message(PSK_DATA_TYPE)
        print("Sending PSK read:", msg.hex())
        dev.write(EP_OUT, msg, timeout=3000)

        resp = dev.read(EP_IN, 512, timeout=3000)
        resp_bytes = bytes(resp)
        print(f"Response 1 ({len(resp_bytes)} bytes):", resp_bytes.hex())

        try:
            resp2 = dev.read(EP_IN, 512, timeout=3000)
            resp2_bytes = bytes(resp2)
            print(f"Response 2 ({len(resp2_bytes)} bytes):", resp2_bytes.hex())
            resp_bytes += resp2_bytes
        except usb.core.USBTimeoutError:
            print("No second response.")

        out_path = "dumps/psk_read_response_linux.bin"
        with open(out_path, "wb") as f:
            f.write(resp_bytes)
        print(f"Saved to {out_path}")
    finally:
        usb.util.release_interface(dev, 0)
        usb.util.dispose_resources(dev)
        print("Released interface.")


if __name__ == "__main__":
    main()
