"""
Offline emulator for the Goodix wbdi.dll "whitebox" PSK-encryption function
(FUN_1800013c0, internally named SecWhiteEncrypt / GoodixDataAesEncrypt).
See ../FINDINGS.md, "Whitebox PSK encryption is emulatable offline" section,
for the full writeup.

Turns out to be ordinary mbedtls AES-128-CBC, not exotic obfuscated crypto -
maps the real wbdi.dll into a Unicorn x86-64 emulator and just runs the
compiled function directly with a chosen plaintext, rather than trying to
hand-derive the key/IV logic from decompiled pseudocode.

Validated against real ground truth: encrypting an all-zero 32-byte PSK with
this emulator produces output that matches the community goodix-fp-dump
project's independently-published PSK_WHITE_BOX constant (for the sibling
55x4 chip, a different device) byte-for-byte, all 96 bytes. That's strong
evidence both that the emulation is correct and that 550c/55x4 share the
literal same whitebox implementation, not just protocol framing.

Needs pip install pefile unicorn, and your own copy of wbdi.dll (pull it
from C:\\Windows\\System32\\DriverStore\\FileRepository\\wbdiusb.inf_amd64_*\\
on the Windows install paired with your sensor - not included here, it's
Goodix/Lenovo's binary, not something to redistribute).

Usage: python3 emulate_whitebox.py <path-to-wbdi.dll> [plaintext-hex]
Prints the 96-byte whitebox-wrapped output. Defaults to an all-zero PSK
(reproduces the community PSK_WHITE_BOX validation case) if no hex is given.
"""

import struct
import sys
import pefile
from unicorn import *
from unicorn.x86_const import *

TARGET_FUNC = 0x1800013c0  # FUN_1800013c0 = SecWhiteEncrypt / GoodixDataAesEncrypt

# Functions we've identified as pure logging/telemetry, safe to neutralize
# (overwrite with a bare `ret`) rather than emulate - their return values are
# never used by the crypto logic itself.
NEUTRALIZE = [0x180001db0]  # the log function called throughout FUN_1800013c0

FAKE_IMPORT_BASE = 0x7000000000
STACK_BASE = 0x00007fff00000000
STACK_SIZE = 0x100000
HEAP_BASE = 0x0000600000000000
HEAP_SIZE = 0x100000
OUT_BUF = 0x0000600000100000
OUT_LEN_PTR = 0x0000600000101000
RET_SENTINEL = 0x1111111111111110

PAGE = 0x1000


def align_down(x, a=PAGE):
    return x & ~(a - 1)


def align_up(x, a=PAGE):
    return (x + a - 1) & ~(a - 1)


class Emu:
    def __init__(self, dll_path):
        self.pe = pefile.PE(dll_path, fast_load=False)
        self.image_base = self.pe.OPTIONAL_HEADER.ImageBase
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.heap_off = 0
        self.import_stubs = {}  # fake_addr -> (dll, name)
        self._map_image()
        self._map_stack()
        self._map_scratch()
        self._patch_imports()
        self._neutralize_logging()
        self.uc.hook_add(UC_HOOK_CODE, self._hook_code, begin=FAKE_IMPORT_BASE,
                          end=FAKE_IMPORT_BASE + 0x1000 * 2000)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._hook_unmapped)

    def _map_image(self):
        total_size = align_up(self.pe.OPTIONAL_HEADER.SizeOfImage)
        self.uc.mem_map(self.image_base, total_size, UC_PROT_ALL)
        # headers
        headers = self.pe.header
        self.uc.mem_write(self.image_base, headers)
        for section in self.pe.sections:
            va = self.image_base + section.VirtualAddress
            data = section.get_data()
            self.uc.mem_write(va, data)
        print(f"Mapped image at 0x{self.image_base:x}, size 0x{total_size:x}")

    def _map_stack(self):
        self.uc.mem_map(STACK_BASE, STACK_SIZE, UC_PROT_ALL)
        self.uc.mem_map(HEAP_BASE, HEAP_SIZE, UC_PROT_ALL)
        self.uc.mem_map(align_down(OUT_BUF), PAGE * 4, UC_PROT_ALL)

    def _map_scratch(self):
        # fake import trampoline area
        size = align_up(0x1000 * 2000)
        self.uc.mem_map(FAKE_IMPORT_BASE, size, UC_PROT_ALL)

    def _patch_imports(self):
        if not hasattr(self.pe, "DIRECTORY_ENTRY_IMPORT"):
            print("No imports?!")
            return
        idx = 0
        for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
            dllname = entry.dll.decode(errors="replace")
            for imp in entry.imports:
                name = imp.name.decode(errors="replace") if imp.name else f"ord{imp.ordinal}"
                fake_addr = FAKE_IMPORT_BASE + idx * 0x1000
                idx += 1
                iat_slot = imp.address  # RVA already absolute (pefile gives absolute VA here)
                self.uc.mem_write(iat_slot, struct.pack("<Q", fake_addr))
                self.import_stubs[fake_addr] = (dllname, name)
        print(f"Patched {idx} import slots")

    def _neutralize_logging(self):
        for addr in NEUTRALIZE:
            self.uc.mem_write(addr, b"\xc3")  # ret
        print(f"Neutralized {len(NEUTRALIZE)} logging function(s)")

    def _hook_unmapped(self, uc, access, address, size, value, user_data):
        rip = uc.reg_read(UC_X86_REG_RIP)
        print(f"UNMAPPED access: type={access} addr=0x{address:x} size={size} at RIP=0x{rip:x}")
        return False

    def _pop_ret(self, uc):
        rsp = uc.reg_read(UC_X86_REG_RSP)
        ret_addr = struct.unpack("<Q", uc.mem_read(rsp, 8))[0]
        uc.reg_write(UC_X86_REG_RSP, rsp + 8)
        uc.reg_write(UC_X86_REG_RIP, ret_addr)

    def _hook_code(self, uc, address, size, user_data):
        if address not in self.import_stubs:
            return
        dllname, name = self.import_stubs[address]
        rcx = uc.reg_read(UC_X86_REG_RCX)
        rdx = uc.reg_read(UC_X86_REG_RDX)
        r8 = uc.reg_read(UC_X86_REG_R8)
        r9 = uc.reg_read(UC_X86_REG_R9)

        handled = True
        if name == "memset":
            # memset(ptr, value, num) -> ptr
            ptr, val, num = rcx, rdx & 0xff, r8
            if num > 0:
                uc.mem_write(ptr, bytes([val]) * num)
            uc.reg_write(UC_X86_REG_RAX, ptr)
        elif name in ("calloc",):
            nmemb, elemsize = rcx, rdx
            total = align_up(nmemb * elemsize if nmemb * elemsize else 1, 16)
            addr = HEAP_BASE + self.heap_off
            self.heap_off += total
            if self.heap_off >= HEAP_SIZE:
                raise RuntimeError("heap exhausted")
            uc.mem_write(addr, b"\x00" * total)
            uc.reg_write(UC_X86_REG_RAX, addr)
        elif name in ("malloc",):
            size_ = rcx
            addr = HEAP_BASE + self.heap_off
            self.heap_off += align_up(size_ if size_ else 1, 16)
            uc.reg_write(UC_X86_REG_RAX, addr)
        elif name in ("free", "LocalFree"):
            uc.reg_write(UC_X86_REG_RAX, 0)
        elif name == "__security_check_cookie":
            pass  # no-op
        elif name in ("_errno",):
            uc.reg_write(UC_X86_REG_RAX, HEAP_BASE + HEAP_SIZE - 8)
        elif name in ("_invalid_parameter_noinfo",):
            pass
        elif name in ("memcpy", "memmove"):
            dst, src, num = rcx, rdx, r8
            if num > 0:
                data = uc.mem_read(src, num)
                uc.mem_write(dst, bytes(data))
            uc.reg_write(UC_X86_REG_RAX, dst)
        else:
            handled = False

        if not handled:
            print(f"UNHANDLED IMPORT CALLED: {dllname}!{name} rcx=0x{rcx:x} rdx=0x{rdx:x} r8=0x{r8:x} r9=0x{r9:x}")
            uc.reg_write(UC_X86_REG_RAX, 0)

        self._pop_ret(uc)

    def call_function(self, addr, args, max_instructions=2_000_000):
        sp = STACK_BASE + STACK_SIZE - 0x1000
        # shadow space (0x20) + return address
        sp -= 0x20
        sp -= 8
        self.uc.mem_write(sp, struct.pack("<Q", RET_SENTINEL))
        self.uc.reg_write(UC_X86_REG_RSP, sp)

        regs = [UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9]
        for reg, val in zip(regs, args):
            self.uc.reg_write(reg, val)

        try:
            self.uc.emu_start(addr, RET_SENTINEL, count=max_instructions)
        except UcError as e:
            rip = self.uc.reg_read(UC_X86_REG_RIP)
            print(f"Emulation stopped with error: {e} at RIP=0x{rip:x}")
            raise
        rip = self.uc.reg_read(UC_X86_REG_RIP)
        if rip != RET_SENTINEL:
            print(f"WARNING: stopped at RIP=0x{rip:x}, not sentinel (possible instruction-count limit hit)")
        return self.uc.reg_read(UC_X86_REG_RAX)


def whitebox_encrypt(emu, plaintext: bytes) -> bytes:
    assert len(plaintext) == 32
    in_buf = HEAP_BASE + HEAP_SIZE - 0x2000
    emu.uc.mem_write(in_buf, plaintext)
    out_buf = OUT_BUF
    emu.uc.mem_write(out_buf, b"\x00" * 0x100)
    out_len_ptr = OUT_LEN_PTR
    emu.uc.mem_write(out_len_ptr, struct.pack("<I", 0x100))

    ret = emu.call_function(TARGET_FUNC, [in_buf, 0x20, out_buf, out_len_ptr])
    out_len = struct.unpack("<I", emu.uc.mem_read(out_len_ptr, 4))[0]
    out_data = bytes(emu.uc.mem_read(out_buf, out_len))
    return ret, out_len, out_data


EXPECTED_ALL_ZERO_OUTPUT = (
    "ec35ae3abb45ed3f12c4751f1e5c2cc05b3c5452e9104d9f2a3118644f37a04b"
    "6fd66b1d97cf80f1345f76c84f03ff30bb51bf308f2a9875c41e6592cd2a2f9e"
    "60809b17b5316037b69bb2fa5d4c8ac31edb3394046ec06bbdacc57da6a756c5"
)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <path-to-wbdi.dll> [plaintext-hex]")
        sys.exit(1)

    dll_path = sys.argv[1]
    if len(sys.argv) >= 3:
        plaintext = bytes.fromhex(sys.argv[2])
        if len(plaintext) != 32:
            print(f"plaintext must be exactly 32 bytes, got {len(plaintext)}")
            sys.exit(1)
    else:
        plaintext = b"\x00" * 32
        print("No plaintext given - using all-zero PSK (reproduces the validation case).")

    emu = Emu(dll_path)
    ret, out_len, out_data = whitebox_encrypt(emu, plaintext)
    print(f"\nret=0x{ret:x} out_len={out_len}")
    print(f"whitebox-wrapped (hex): {out_data.hex()}")

    if plaintext == b"\x00" * 32:
        match = out_data.hex() == EXPECTED_ALL_ZERO_OUTPUT
        print(f"\nGround-truth check against community PSK_WHITE_BOX constant: {'PASS' if match else 'FAIL'}")
        if not match:
            print("This should match exactly for an all-zero PSK - if it doesn't, something in this")
            print("emulation setup or your wbdi.dll copy differs from what was validated originally.")
