"""
Safe, read-only probe: read the sensor's chip-ID register (0x0000, 4 bytes)
via COMMAND_READ_SENSOR_REGISTER (0x82). Plain message-protocol channel, no
TLS/PSK needed - good first check that the device is reachable and the
message-pack/message-protocol framing is correct before attempting anything
that needs the captured PSK. Returns chip ID 04051180 on a healthy 550c.
"""

import struct
import sys
import time
import usb.core
import usb.util

VID = 0x27C6
PID = 0x550C
EP_OUT = 0x01
EP_IN = 0x83

COMMAND_NOP = 0x00
COMMAND_ACK = 0xb0
COMMAND_READ_SENSOR_REGISTER = 0x82


def encode_message_protocol(payload: bytes, command: int) -> bytes:
    length = len(payload) + 1
    data = bytes([command]) + struct.pack("<H", length) + payload
    checksum = (0xAA - sum(data)) & 0xFF
    return data + bytes([checksum])


def encode_message_pack(inner: bytes, flags: int = 0xA0) -> bytes:
    header = bytes([flags]) + struct.pack("<H", len(inner))
    checksum = sum(header) & 0xFF
    return header + bytes([checksum]) + inner


def decode_message_pack(data: bytes):
    flags = data[0]
    length = struct.unpack("<H", data[1:3])[0]
    payload = data[4:4 + length]
    return payload, flags, length


def decode_message_protocol(data: bytes):
    command = data[0]
    length = struct.unpack("<H", data[1:3])[0]
    payload = data[3:2 + length]
    return payload, command, length


def read_sensor_register(dev, address: int, length: int):
    msg = b"\x00" + struct.pack("<H", address) + struct.pack("<B", length)
    frame = encode_message_pack(encode_message_protocol(msg, COMMAND_READ_SENSOR_REGISTER))
    print("Sending read_sensor_register:", frame.hex())
    dev.write(EP_OUT, frame, timeout=3000)

    ack_raw = bytes(dev.read(EP_IN, 512, timeout=3000))
    print("ACK raw:", ack_raw.hex())
    ack_payload, ack_flags, _ = decode_message_pack(ack_raw)
    inner_payload, inner_cmd, _ = decode_message_protocol(ack_payload)
    print(f"  ack outer flags=0x{ack_flags:02x} inner cmd=0x{inner_cmd:02x} inner payload={inner_payload.hex()}")

    resp_raw = bytes(dev.read(EP_IN, 512, timeout=3000))
    print("Response raw:", resp_raw.hex())
    resp_payload, resp_flags, _ = decode_message_pack(resp_raw)
    inner_payload2, inner_cmd2, _ = decode_message_protocol(resp_payload)
    print(f"  resp outer flags=0x{resp_flags:02x} inner cmd=0x{inner_cmd2:02x} inner payload={inner_payload2.hex()}")
    return inner_payload2


def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("Device not found")
        sys.exit(1)

    try:
        dev.reset()
        time.sleep(0.5)
        dev = usb.core.find(idVendor=VID, idProduct=PID)
    except usb.core.USBError as e:
        print(f"(reset warning, continuing: {e})")

    dev.set_configuration()
    usb.util.claim_interface(dev, 0)
    print("Interface claimed.")

    try:
        print("Draining stale data...")
        while True:
            try:
                dev.read(EP_IN, 512, timeout=200)
            except usb.core.USBTimeoutError:
                break

        chip_id = read_sensor_register(dev, 0x0000, 4)
        print(f"\nChip ID register (0x0000, 4 bytes): {chip_id.hex()}")
    finally:
        usb.util.release_interface(dev, 0)
        usb.util.dispose_resources(dev)
        print("Released.")


if __name__ == "__main__":
    main()
