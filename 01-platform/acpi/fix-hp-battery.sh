#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build the HP OmniBook X battery DSDT override from this machine's tables.
#
# BAT0._STA calls \_SB.FFA0.RBUF. That method builds a 64-byte buffer and
# creates field DATA at bit 208 for 400 bits. The field does not fit, ACPI
# aborts, and the battery driver never creates /sys/class/power_supply.
#
# This dumps the running tables, widens that one buffer to 80 bytes, and
# installs the compiled table for the acpi_override initramfs hook. It does
# not write firmware flash and it does not copy another machine's tables.
#
#   sudo bash 01-platform/acpi/fix-hp-battery.sh
#
# Reboot afterward. Keep a boot entry whose initramfs has no override until
# the new image has been checked.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run: sudo bash $0" >&2
  exit 1
fi

read_dmi() {
  local key=$1
  local path="/sys/class/dmi/id/${key}"
  [[ -r "$path" ]] || {
    echo "cannot read $path" >&2
    exit 1
  }
  tr -d '\0' <"$path"
}

product="$(read_dmi product_name)"
board="$(read_dmi board_name)"
bios="$(read_dmi bios_version)"
[[ "$product" == "HP OmniBook X Laptop 14-ks000" && "$board" == "8F22" && "$bios" == "F.05" ]] || {
  echo "refusing: this script is for the HP OmniBook X 14-ks000, board 8F22, BIOS F.05" >&2
  echo "found: product='$product' board='$board' bios='$bios'" >&2
  exit 1
}

[[ -f /usr/lib/initcpio/install/acpi_override ]] || {
  echo "missing the acpi_override mkinitcpio hook from the N1X kernel package" >&2
  exit 1
}
[[ -f /etc/mkinitcpio.conf ]] || {
  echo "missing /etc/mkinitcpio.conf" >&2
  exit 1
}

patcher="$(cd "$(dirname "$0")" && pwd)/fix-hp-battery.py"
[[ -f "$patcher" ]] || {
  echo "missing $patcher" >&2
  exit 1
}

if ! command -v iasl >/dev/null 2>&1; then
  echo "installing acpica for iasl"
  pacman -S --needed --noconfirm acpica
fi

work=/var/lib/hp-omnibook-acpi
rm -rf "$work"
mkdir -p "$work/orig" "$work/dsl" /etc/initcpio/acpi_override

shopt -s nullglob
tables=(/sys/firmware/acpi/tables/DSDT /sys/firmware/acpi/tables/SSDT*)
if [[ ${#tables[@]} -eq 0 ]]; then
  echo "no ACPI tables under /sys/firmware/acpi/tables" >&2
  exit 1
fi

for table in "${tables[@]}"; do
  name="$(basename "$table")"
  cp -a "$table" "$work/orig/$name"
  cp -a "$table" "$work/$name.dat"
  if ! iasl -d "$work/$name.dat" >"$work/$name.iasl" 2>&1; then
    echo "iasl could not disassemble $name" >&2
    cat "$work/$name.iasl" >&2
    exit 1
  fi
  mv "$work/$name.dsl" "$work/dsl/$name.dsl"
done

patched=""
note=""
for dsl in "$work"/dsl/*.dsl; do
  set +e
  note="$(python3 "$patcher" "$dsl" "$work/patched.dsl")"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    patched="$dsl"
    break
  fi
  if [[ "$status" -eq 4 ]]; then
    echo "$dsl: $note"
    echo "The buffer is already large enough. No override written."
    exit 0
  fi
  if [[ "$status" -ne 3 ]]; then
    echo "patcher failed on $dsl: $note" >&2
    exit 1
  fi
done

if [[ -z "$patched" ]]; then
  echo "Could not find CreateField DATA at bit 208 length 400." >&2
  echo "Disassembly is in $work/dsl" >&2
  exit 1
fi

echo "patched $(basename "$patched"): $note"

if ! iasl -ve -p "$work/hp-omnibook-battery" "$work/patched.dsl" >"$work/iasl-compile.txt" 2>&1; then
  echo "iasl refused the patched table. Nothing was installed." >&2
  cat "$work/iasl-compile.txt" >&2
  exit 1
fi
if [[ ! -f "$work/hp-omnibook-battery.aml" ]]; then
  echo "iasl did not write an AML file" >&2
  cat "$work/iasl-compile.txt" >&2
  exit 1
fi

for existing in /etc/initcpio/acpi_override/*.aml; do
  base="$(basename "$existing")"
  if [[ "$base" != "hp-omnibook-battery.aml" ]]; then
    echo "refusing to stack $existing beside the new override" >&2
    echo "The compiled table is in $work and was not installed." >&2
    exit 1
  fi
done

install -m 0644 "$work/hp-omnibook-battery.aml" /etc/initcpio/acpi_override/hp-omnibook-battery.aml

conf=/etc/mkinitcpio.conf
if ! grep -Eq '^HOOKS=\([^)]*\bacpi_override\b' "$conf"; then
  if ! grep -Eq '^HOOKS=\(h7607a-preload ' "$conf"; then
    echo "HOOKS in $conf does not start with h7607a-preload." >&2
    echo "Add acpi_override to HOOKS, then run mkinitcpio -P." >&2
    echo "The table is installed at /etc/initcpio/acpi_override/hp-omnibook-battery.aml" >&2
    exit 1
  fi
  cp -a "$conf" "${conf}.pre-hp-omnibook-battery"
  sed -i 's/HOOKS=(h7607a-preload /HOOKS=(h7607a-preload acpi_override /' "$conf"
fi
if ! grep -Eq '^HOOKS=\([^)]*\bacpi_override\b' "$conf"; then
  echo "could not add the acpi_override hook to $conf" >&2
  exit 1
fi

mkinitcpio -P

{
  echo "installed /etc/initcpio/acpi_override/hp-omnibook-battery.aml"
  echo "source table: $(basename "$patched")"
  echo "change: $note"
  echo "reboot, then:"
  echo "  journalctl -k -b -o cat --no-pager | grep -E 'Table Upgrade|BUFFER_LIMIT' || true"
  echo "  ls /sys/class/power_supply"
} | tee "$work/report.txt"

echo
echo "The running system is unchanged until you reboot."
