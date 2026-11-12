#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Match the installed SoundWire machine table to this HP's two CS35L56 amps.
#
# h7607a soundwire-mtk.ko describes mtk_sdw_cs35l56_l0_cs42l43_l1 with four
# amplifiers on link 0. This board has two (unique ids 0 and 1) plus the
# CS42L43 on link 1. Until that table is rebuilt from source, this changes
# num_adr from 4 to 2 in the installed module and keeps a backup.
#
# A later reinstall of the module package replaces the file. Run this again
# after that upgrade, then reboot. This script does not unbind the live driver.
#
#   sudo bash 02-drivers/soundwire/match-two-amps.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run: sudo bash $0" >&2
  exit 1
fi

product="$(tr -d '\0' </sys/class/dmi/id/product_name)"
board="$(tr -d '\0' </sys/class/dmi/id/board_name)"
[[ "$product" == "HP OmniBook X Laptop 14-ks000" && "$board" == "8F22" ]] || {
  echo "refusing: two-amp match is for the HP OmniBook X 14-ks000, board 8F22" >&2
  echo "found: product='$product' board='$board'" >&2
  exit 1
}

kver="$(uname -r)"
mod="/lib/modules/${kver}/updates/h7607a/soundwire-mtk.ko"
backup_dir=/var/lib/hp-omnibook
backup="${backup_dir}/soundwire-mtk.ko.four-amp.bak"

if [[ ! -f "$mod" ]]; then
  echo "missing $mod" >&2
  exit 1
fi

install -d -m 0755 "$backup_dir"
python3 - "$mod" "$backup" <<'PY'
import shutil, struct, sys
from pathlib import Path

mod = Path(sys.argv[1])
backup = Path(sys.argv[2])
data = bytearray(mod.read_bytes())

def u16(off):
    return struct.unpack_from("<H", data, off)[0]

def u64(off):
    return struct.unpack_from("<Q", data, off)[0]

e_shoff = u64(40)
e_shentsize = u16(58)
e_shnum = u16(60)
e_shstrndx = u16(62)
secs = []
for i in range(e_shnum):
    off = e_shoff + i * e_shentsize
    name_off, _, _, _, sh_offset, sh_size, _, _, _, _ = struct.unpack_from("<IIQQQQIIQQ", data, off)
    secs.append((name_off, sh_offset, sh_size))
str_off = secs[e_shstrndx][1]

def cstr(off):
    end = data.index(b"\0", off)
    return data[off:end].decode()

names = [cstr(str_off + s[0]) for s in secs]
ro = secs[names.index(".rodata")]
sy = secs[names.index(".symtab")]
st = secs[names.index(".strtab")]
target = None
for i in range(0, sy[2], 24):
    st_name, _, _, shndx, st_value, st_size = struct.unpack_from("<IBBHQQ", data, sy[1] + i)
    if cstr(st[1] + st_name) == "mtk_sdw_cs35l56_l0_cs42l43_l1":
        target = (shndx, st_value, st_size)
        break
if target is None:
    sys.exit("machine table symbol not found")
shndx, value, size = target
if names[shndx] != ".rodata" or size < 8:
    sys.exit(f"unexpected symbol location {names[shndx]} size {size}")
file_off = ro[1] + value
mask, num = struct.unpack_from("<II", data, file_off)
if mask != 1 or num not in (2, 4):
    sys.exit(f"refusing to patch link0 mask={mask:#x} num_adr={num}")
if num == 2:
    print("already matched to two amps")
    sys.exit(0)
if not backup.exists():
    shutil.copy2(mod, backup)
data[file_off + 4] = 2
mod.write_bytes(data)
print(f"patched {mod}: link 0 num_adr 4 -> 2 (backup {backup})")
PY

echo "Reboot so soundwire_mtk loads the matched table."
