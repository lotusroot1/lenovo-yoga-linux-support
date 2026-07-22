# Fingerprint sensor reverse engineering — Goodix `27c6:550c`

Status as of 2026-07-21: **research in progress, not a working driver yet.**
Core protocol has been reverse-engineered and validated end-to-end against
real hardware, including successfully capturing and decoding real
fingerprint images. What's missing is packaging this into an actual
`libfprint` driver (C code, real enrollment/matching, a finger-detect loop)
— right now it's a Python proof-of-concept that pulls one raw image per run.

---

## Hardware / starting point

- Sensor: Goodix `27c6:550c` (USB, Shenzhen Goodix Technology), Bulk OUT
  `0x01` / Bulk IN `0x83`.
- `fprintd` / `libfprint-2-tod1` report "No devices available" — no Linux
  kernel driver binds this device (`Driver=[none]`), and no `libfprint`
  driver exists upstream for this exact chip.
- Tracking issue for this exact laptop:
  `github.com/goodix-fp-linux-dev/goodix-fp-dump` issue #59. The
  `goodix-fp-dump` / `libfprint-tod` project has no active maintainer as of
  this writing.
- The 55-series Goodix sensors use TLS-PSK encryption over USB specifically
  to defeat passive USB sniffing (a deliberate anti-clone measure). The only
  prior public break of a sibling chip in this family (Neodyme, 2021,
  covering 55a2/5503/55x4) required attaching a debugger to the Windows OEM
  driver to catch the PSK during a fresh-pairing event — passive `usbmon`
  capture cannot work here, the key material never appears on the wire.

## udev rule

Linux has no existing driver claiming this device, so `libusb` can open it
directly — no Zadig/WinUSB-style driver fight like on Windows. Just needs
non-root USB access:

```
sudo cp 99-goodix-550c.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --action=add
```
(`--action=add` matters — a plain trigger doesn't reapply `MODE` to an
already-enumerated device node.)

## Getting your own PSK

**There's no way to just read it off the sensor over USB** — confirmed by
directly probing `COMMAND_PRESET_PSK_READ_R` (`0xe4`) with every known
data-type constant (`0xbb010002`, `0xbb020001`, `0xbb020007`, `0xbb010003`)
and reading until the device stops responding rather than assuming a fixed
frame count. Every variant gets an identical, well-formed rejection
(`message[0] = 0x01`, which per the community reference driver's own
convention for this specific command means failure — `0x00` would mean
success). The sensor stores its PSK sealed on its own onboard flash and
will not hand it back once provisioned — this looks like a deliberate
write-once-then-locked security property, not a protocol detail we're
missing.

The PSK is per-device key material extracted from the *live process memory*
of the Windows OEM driver during a debugger session — not something that
can be redistributed or is included in this repo. Roughly:

1. On Windows, use `HostProcessDbgBreakOnDriverLoad` + `cdb` to attach a
   debugger to the `wbdi.dll`-hosting process at driver load.
2. Break on `wbdi.dll` at the call site that hands the PSK to the crypto
   layer (`RDX` = PSK pointer, `R8` = length at that instruction — found via
   Ghidra decompilation of `wbdi.dll` and cross-referenced against the
   TLS-PSK identity `Client_identity` / cipher suite
   `TLS_PSK_WITH_AES_128_CBC_SHA256`).
3. Trigger a fingerprint verification through Windows Hello to hit the
   breakpoint, dump the 32 bytes at `RDX`.

Save the result as `dumps/CAPTURED_PSK.txt` (gitignored — see below) in the
format:
```
PSK (hex): <64 hex characters>
```

**This file is real cryptographic key material for your specific sensor —
never commit it, post it, or share it publicly.** `dumps/` in this folder
is gitignored for exactly this reason.

## Chip config / calibration data

Image capture also needs a chip-specific config blob
(`COMMAND_UPLOAD_CONFIG_MCU`, opcode `0x90`) and finger-detect threshold
data (`0x32`/`0x34`/`0x36`) — these are **not** encrypted, unlike the PSK,
so they can be captured with a plain USB packet capture (Wireshark +
USBPcap, or live-memory breakpoints if USBPcap doesn't work on your USB
controller — it didn't on this laptop, USB4/Thunderbolt host controller
incompatibility) of the stock Windows driver running a normal fingerprint
verification. The captured values for this exact sensor are hardcoded into
`tools/capture_fingerprint_linux.py` (`CONFIG_BLOB`, `FDT_DOWN_SAMPLE`) —
these are calibration constants, not secrets, safe to share (compare to the
community `goodix-fp-dump` project's public `DEVICE_CONFIG` blob for the
sibling 55x4 chip).

## Wire protocol (validated against real hardware)

```python
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
```

Outer `flags`: `0xA0` = plain message protocol, `0xB0` = TLS handshake data,
`0xB2` = TLS application data (e.g. image transfer).

Known opcodes (inner `command` byte), cross-referenced against the
open-source `goodix-fp-dump` project's driver for the sibling 55x4 chip
family (`driver_55x4.py`) — its opcode constants matched almost this whole
list, strong confirmation 550c shares the same command set:

| Opcode | Name |
|---|---|
| `0x00` | NOP |
| `0x20` | MCU_GET_IMAGE |
| `0x32`/`0x34`/`0x36` | MCU_SWITCH_TO_FDT_DOWN/UP/MODE |
| `0x60` | MCU_SWITCH_TO_SLEEP_MODE |
| `0x70` | MCU_SWITCH_TO_IDLE_MODE |
| `0x80`/`0x82` | WRITE/READ_SENSOR_REGISTER |
| `0x90` | UPLOAD_CONFIG_MCU |
| `0x94` | SET_POWERDOWN_SCAN_FREQUENCY |
| `0xa2` | RESET |
| `0xa4` | MCU_ERASE_APP |
| `0xa6` | READ_OTP |
| `0xa8` | FIRMWARE_VERSION |
| `0xac` | SET_POV_CONFIG |
| `0xae` | QUERY_MCU_STATE |
| `0xc4` | SET_DRV_STATE |
| `0xd0` | REQUEST_TLS_CONNECTION |
| `0xe0`/`0xe4` | PRESET_PSK_WRITE_R / PRESET_PSK_READ_R |
| `0xf0`/`0xf4` | WRITE_FIRMWARE / CHECK_FIRMWARE |

(`0x40` and 4-byte extended opcodes `0xa000`-`0xb002`/`0x8000`-`0x8002` are
still unmapped — not blocking basic image capture.)

TLS handshake sequence (`request_tls_connection` + a bridged
`openssl s_server` acting as the PSK-side TLS terminator):
1. Send `COMMAND_REQUEST_TLS_CONNECTION` (`0xd0`).
2. Read the ACK, then the sensor's ClientHello (`flags=0xB0`) — a genuine
   TLS 1.2 ClientHello offering cipher `0x00AE`
   (`TLS_PSK_WITH_AES_128_CBC_SHA256`), identity `Client_identity`.
3. Forward it into a local `openssl s_server -psk <hex> ...`, forward each
   response/flight back and forth (4 flights total) between the device and
   the local TLS server.
4. Handshake complete; subsequent application data uses `flags=0xB2`.

This handshake **hung indefinitely on Windows** (`SSL_accept()` never
returning when driven from a Python subprocess/socket, despite the identical
config working fine via `openssl s_client` directly — looked like a
Windows-specific subprocess/socket quirk, not a protocol issue) but **works
cleanly on Linux** with the exact same bridging approach.

## Image capture

Once the handshake works:

1. `upload_config_mcu` (`0x90`) with the captured 256-byte config blob.
2. `mcu_switch_to_fdt_down` (`0x32`) with a captured 24-byte threshold
   sample. **This is what arms the sensor** — without it, `mcu_get_image`
   still completes the full protocol round-trip (right byte count and
   everything) but returns an all-zero image. `mcu_switch_to_fdt_mode`
   (`0x36`) was never captured and turned out **not** to be required for a
   basic capture, contrary to what the sibling 55x4 driver's flow suggests.
3. `mcu_get_image` (`0x20`) → 14334-byte response (`flags=0xB2`) → strip the
   first 9 bytes → forward into the TLS socket → `openssl s_server` decrypts
   it and echoes 14260 bytes of plaintext to its own stdout.
4. Strip the last 4 bytes → 12-bit-packed pixel decode, 6 bytes → 4 pixels:
   ```python
   def decode_pixels(data):
       image = []
       for i in range(0, len(data), 6):
           c = data[i:i+6]
           image.append(((c[0] & 0xf) << 8) + c[1])
           image.append((c[3] << 4) + (c[0] >> 4))
           image.append(((c[5] & 0xf) << 8) + c[2])
           image.append((c[4] << 4) + (c[5] >> 4))
       return image
   ```
   Result: exactly 9504 pixels = 88×108 — identical resolution and framing
   to the community project's 55x4 sibling chip, stored column-major
   (`pixel(x, y) = image[x*height + y]`).

**Confirmed with a live finger on the sensor**: pixel values shift sharply
between no-finger (avg ~4030/4095, near-saturated) and finger-present
(avg ~700-900/4095, wide value spread) states, and a real, legible
ridge/valley pattern is visible in the decoded image — not just a
statistical shift.

### Raw output has a per-column artifact — needs correction

The raw decoded image has a strong vertical banding pattern: both a
per-column DC offset *and* a per-column gain difference (column standard
deviation varied ~150–258 across a test frame, ~1.7× spread) — consistent
with a multi-lane parallel ADC readout (period looked like ~4 columns).
Confirmed via a background-subtracted diff between a no-finger and a
finger-present frame that this is real sensor output, not a decode bug —
the banding is present nearly identically in both.

**Fix**: per-column z-score normalization (subtract each column's own mean,
divide by its own standard deviation) before display/further processing.
Plain mean-subtraction alone wasn't enough (leaves the gain difference
visible); z-score cleaned it up well enough to show clear ridge detail
across nearly the whole frame in testing. This is a post-processing fix
applied after decode — unclear yet whether a fuller/different config blob
would calibrate it away at the firmware level instead, or whether
`libfprint`'s existing `goodix_tls` driver (for other Goodix chips) already
does equivalent post-processing.

## Whitebox PSK encryption is emulatable offline (but the write path is locked anyway)

The sensor's write path (`COMMAND_PRESET_PSK_WRITE_R`, `0xe0` — used to
*provision* a PSK onto the sensor, the mirror image of the read path above)
requires the PSK to be "whitebox-encrypted" first. Traced this
(`wbdi.dll`'s `PresetPskWriteKey`) via decompiled pseudocode and found the
whitebox step is just a call to a function internally named
`SecWhiteEncrypt`/`GoodixDataAesEncrypt` — which turns out to be **ordinary
mbedtls AES-128-CBC**, not exotic obfuscated crypto (identified by its exact
sequence of `mbedtls_cipher_setup`/`setkey`/`set_iv`/`update`/`finish`
calls).

Built `tools/emulate_whitebox.py`: maps the real `wbdi.dll` into a Unicorn
x86-64 emulator and runs that function directly against a chosen 32-byte
plaintext, rather than hand-deriving the key/IV logic. **Validated against
real ground truth**: encrypting an all-zero PSK produces output matching the
community `goodix-fp-dump` project's independently-published
`PSK_WHITE_BOX` constant (for the *sibling* 55x4 chip) byte-for-byte, all 96
bytes — strong evidence the emulation is correct, and that `550c`/`55x4`
share the literal same whitebox implementation, not just protocol framing.
This means a valid whitebox-wrapped PSK for *any* chosen 32-byte key can be
computed entirely offline in milliseconds, no Windows or live capture
needed for this part.

**But writing it to the sensor doesn't work** — tried twice against the
live device, both failed cleanly with no damage:
1. A plain (unauthenticated) write got an explicit rejection
   (`message[0] = 0x01` — a real "no" per the write command's own success
   convention, same file/logic as the read path above).
2. The same write wrapped as encrypted TLS application data inside an
   already-authenticated session (requires building the *encrypt* direction
   of the USB↔TLS bridge — feed plaintext into `openssl s_server`'s stdin,
   forward the resulting ciphertext to the device tagged `flags=0xB2`) got
   **no response at all**, not even a rejection — timeout. Different
   failure mode, suggesting `0xB2` isn't a bidirectional secure command
   channel; every legitimate use seen so far has been device→host data
   (images), so the firmware may have no parser for an inbound frame tagged
   that way at all.

Verified the sensor was completely unaffected both times (the existing
captured PSK still authenticates and decrypts real image data afterward).

**Root cause found (static analysis only, not yet tested live)**: traced the
actual caller of the write path in the decompiled pseudocode — `ProcessPsk`
(source `geneva.c`). Its real logic: check if the current PSK is already
valid (skip write if so) → if not, check whether the sensor's firmware is
**already running in "IAP"/"TESTIAP" mode** (a firmware-update/bootloader
mode, not normal operation) → if not already in that mode, issue what looks
like an erase-app / mode-switch command and retry on a later loop iteration
→ **only once confirmed in IAP mode does it actually call the PSK write**.

This is the missing precondition, and it's a meaningfully different risk
category from everything else in this document. Entering IAP mode appears
to require an erase-app step first — the same class of operation this
project has deliberately avoided from the start (see the guardrails
originally written for the Windows-side capture: never run
firmware-write/erase code against this specific device). A failed or
interrupted firmware-mode transition here could plausibly brick the sensor,
unlike every other experiment in this document, which has all been fully
safe and reversible (confirmed via real before/after checks each time).

**Status: root cause identified, not attempted live.** If a future session
wants to actually pursue this, treat it as a distinct, higher-risk
undertaking requiring explicit fresh authorization — not something to just
try because the write-path investigation was going well. Worth scoping the
exact erase/IAP-mode command from the decompiled pseudocode *before* any
live attempt, and worth considering whether the payoff (a self-written PSK,
when a working captured one already exists) justifies the risk at all.

**This caution is independently confirmed by the wider community, not just
this project's own guardrails.** `goodix-fp-dump` GitHub issue #61
documents a real bricking incident — a Goodix sensor (27c6:5125, in a
Huawei MateBook) rendered unusable during TLS-handshake/protocol
experimentation, referenced in later issues as a standing cautionary
example, with no recorded recovery. Separately, a community guide for
installing an experimental driver for the sibling 55b4 chip
(gist.github.com/d-k-bo/15e53eab53e2845e97746f5f8661b224) uses the *exact
same* "type a random confirmation number before running anything
firmware-adjacent" pattern found in this project's own
`tools/community/driver_55x4.py`, plus two warnings worth carrying
forward: don't run flashing scripts automatically/repeatedly (can damage
the sensor over time), and — relevant here since this laptop dual-boots —
**leaving the Windows driver enabled means Windows will silently reflash
the sensor with its own firmware**, which could collide badly with an
in-progress Linux-side firmware operation. No public, reliable recovery
procedure exists for a sensor bricked this way; vendor tools (Goodix's
`gdixupdate`, the fwupd Goodix plugin) cover normal signed firmware
updates, not un-bricking a corrupted/erased state.

## Enrollment/matching is match-on-chip — the real opcodes (static analysis only)

Worth asking up front: does Windows' driver stack (or Windows itself)
implement the actual fingerprint matching algorithm? No to both. `wbdi.dll`
literally stands for Windows Biometric Driver Interface — Goodix's
implementation of Microsoft's generic biometric driver contract. Across all
the decompiled code traced for this project, there's no ridge-comparison
logic anywhere in it. These sensors are "match-on-chip": the physical MCU
inside the sensor stores enrolled templates and runs the matching algorithm
itself; the host driver is just a thin client that forwards requests and
relays results.

Found the real enroll/verify opcodes (source `malibuseries/virtualfp.c` in
`wbdi.dll`, via `command_opcode_callers.txt` — generated last night by a
different Ghidra pass than the one everything else in this document reads
from, scoped to a broader command-dispatch trace rather than PSK-only
strings):

| Opcode | Function | Role |
|---|---|---|
| `0xa100` | `_EnrollStart` | Begin an enrollment session |
| `0xa000` | `_Enroll` | Submit one enrollment sample |
| `0xa200` | `_CheckForDuplicate` | Check if this finger is already enrolled |
| `0xa300` | `_CommitTemplate` | Finalize and save the enrolled template |
| `0xa400` | `_IdentifyFeatureSet` | The actual verify/match operation |

(Also confirmed `0x8000`-`0x8002` = `UpdateFirmware`, source `malibu.c` —
independent confirmation that range is the dangerous firmware-write
territory already flagged above, unrelated to enrollment.)

**Practical implication**: a real `libfprint` driver for this chip likely
won't need to implement fingerprint-matching algorithms at all — just drive
the sensor's own built-in enroll/verify state machine, the same kind of
"find the right opcode sequence" problem already solved for image capture.

**Wire format for these (traced, not yet tested live)**: all the framing
validated live so far assumes a 1-byte opcode. These are native 2-byte
(`ushort`) opcodes, routed through a different-looking dispatch path
(`IoHubMcuSendCmd2`). Traced it through `CmdOutCreate` into `_IoHubExec`'s
`sendCmd` branch and found no separate serialization step — the opcode
flows through as a raw `ushort` to the same low-level transport function
pointer used for every other command. Well-grounded conclusion: these
almost certainly use the *same* framing already validated
(`command + length + payload + checksum`), just with the command field
being 2 bytes instead of 1 — not a different protocol, just a wider field.

**Risk of actually testing this (not done)**: lower than the PSK-write/IAP
path — these are normal runtime operations every Windows Hello enrollment
already uses, not firmware/bootloader territory. But not risk-free:
`_Enroll`/`_CommitTemplate` write to persistent template storage that
almost certainly already holds real enrollments on any machine running
this — testing could plausibly interact with or overwrite that (a real,
if far more recoverable, risk than a brick — probably "re-enroll in
Windows" worst case, not "sensor is dead"). `_IdentifyFeatureSet` is more
likely read-only/comparison and probably lower-risk, but still unconfirmed
either way.

Reusable tooling from this: `tools/FindFunctionsByString.java`, a generic
Ghidra headless script — search defined strings for any substring (source
file paths, log format strings, etc.) and decompile every function that
references a match. Not specific to this chip; useful for any "what part
of this driver actually does X" question against a binary already
(or freshly) imported into Ghidra. Note if reusing the original Ghidra
project (`tools/ghidra_project/`, gitignored, not in this repo) on a
different machine: it may refuse to reopen via headless `-process` mode
with a `NotOwnerException` if the OS/session identity doesn't match who
created it — reimporting the target DLL fresh into a new temp project
sidesteps this cleanly (~40s reanalysis for `wbdi.dll`).

## What's proven

- PSK capture, TLS-PSK handshake, config upload, sensor arming, image pull,
  pixel decode, and banding correction all work against real hardware.
- Two live-finger captures produced a legible fingerprint image after
  z-score correction (fingerprint images themselves are not included in
  this repo or committed anywhere — they're a permanent biometric
  identifier for whoever captured them).
- The whitebox PSK-wrap function is fully emulatable offline and validated
  against independent ground truth (see above) — even though writing a
  self-chosen PSK to the sensor doesn't currently work, this remains a
  useful, reusable capability for future work on this chip family.
- The real enrollment/matching opcodes are identified (see above) — not
  yet tested live, but this removes what looked like the biggest unknown
  for eventually building a real driver: we now believe no custom matching
  algorithm needs to be written, just the right commands to the sensor's
  own on-chip matcher.

## What's not done

- Only two live captures so far — no repeatability/consistency study across
  many placements.
- No finger-detection/wait loop — every capture right now is a single fixed
  request, not "wait for a finger, then capture."
- `0x36` (FDT_MODE) still completely unexplored.
- Enrollment/matching opcodes are identified but completely untested live —
  no live enroll, no live verify, and the 2-byte-opcode wire format is a
  well-grounded hypothesis, not a confirmed one.
- Not packaged as a `libfprint` driver — that needs a C port following the
  `goodix_tls` driver structure in the community's
  `goodix-fp-linux-dev/libfprint` fork, plus wiring up the enroll/verify
  calls above.

## Credits / prior art

- `goodix-fp-dump` (github.com/goodix-fp-linux-dev/goodix-fp-dump) — the
  open-source reference driver for the sibling 55x4/5503 chip family; its
  opcode table and message-pack/message-protocol framing matched this chip
  almost exactly and were essential for cross-checking the Ghidra-derived
  protocol understanding.
- Neodyme's 2021 writeup on breaking TLS-PSK on other 55-series Goodix
  sensors via a live debugger session — the general methodology this
  project's PSK capture follows.

## Tools in this folder

| File | What it does |
|---|---|
| `99-goodix-550c.rules` | udev rule for unprivileged USB access |
| `tools/read_chip_id_linux.py` | Read-only sanity check — reads the chip ID register, no PSK needed |
| `tools/goodix_psk_read_linux.py` | Reads the sealed PSK-read ACK from the device (not the raw key — confirms basic framing works) |
| `tools/goodix_tls_bridge_linux.py` | Standalone TLS-PSK handshake test (needs `dumps/CAPTURED_PSK.txt`) |
| `tools/capture_fingerprint_linux.py` | Full pipeline: handshake → config → arm → capture → decrypt → decode → z-score correct → save PNGs |
| `tools/emulate_whitebox.py` | Offline emulator for the sensor's whitebox PSK encryption — computes a valid wrapped PSK for any chosen key, no Windows needed. Needs your own copy of `wbdi.dll` (not included, see script docstring) and `pip install pefile unicorn`. |
| `tools/FindFunctionsByString.java` | Generic Ghidra headless script — finds and decompiles every function referencing a given string substring in any binary. Not chip-specific; edit `SEARCH_TERMS` at the top. Run via `analyzeHeadless` against a Ghidra project with the target binary imported. |

All Python scripts expect a `dumps/` folder alongside them (create it
yourself, it's gitignored) containing your own `CAPTURED_PSK.txt`.
