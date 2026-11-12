#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copy this machine's ACPI tables to DEST_DIR. Does not change boot files.
# MSDM is skipped because it can hold a Windows product key.
#
#   sudo bash 01-platform/acpi/collect-acpi.sh /var/tmp/hp-acpi
#
# Keep the copy out of this repository.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run: sudo bash $0 DEST_DIR" >&2
  exit 1
fi
if [[ $# -ne 1 || -z "${1:-}" ]]; then
  echo "usage: sudo bash $0 DEST_DIR" >&2
  exit 2
fi

root="$(cd "$(dirname "$0")" && pwd)"
while [[ "$root" != "/" && ! -f "$root/pins/machine.json" ]]; do
  root="$(dirname "$root")"
done
if [[ ! -f "$root/pins/machine.json" ]]; then
  echo "cannot find the repository root (pins/machine.json) from $0" >&2
  exit 1
fi
dest="$(realpath -m "$1")"
case "$dest" in
  "$root"|"$root"/*)
    echo "refusing to write ACPI tables inside $root" >&2
    exit 1
    ;;
esac

install -d -m 0700 "$dest"
shopt -s nullglob
copied=0
for table in /sys/firmware/acpi/tables/DSDT /sys/firmware/acpi/tables/SSDT* /sys/firmware/acpi/tables/FACP; do
  [[ -f "$table" ]] || continue
  name="$(basename "$table")"
  if [[ "$name" == MSDM ]]; then
    continue
  fi
  install -m 0600 "$table" "$dest/${name}.aml"
  copied=$((copied + 1))
done

if [[ "$copied" -eq 0 ]]; then
  echo "no DSDT, SSDT, or FACP tables were readable" >&2
  exit 1
fi
echo "Saved ${copied} ACPI tables in $dest"
echo "These files come from the firmware. Do not commit them."
