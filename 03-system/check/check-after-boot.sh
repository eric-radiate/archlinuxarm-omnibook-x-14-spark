#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Read-only report after a reboot. Does not change configuration.
set -u

echo '=== command line ==='
cat /proc/cmdline

echo '=== ACPI override and power messages ==='
if command -v journalctl >/dev/null 2>&1; then
  journalctl -k -b -o cat --no-pager \
    | grep -E 'Table override|ACPI:.*(DSDT|Override|Upgrade)|AE_AML_BUFFER_LIMIT|FFA0\.RBUF|BAT0|ADP1|PM: suspend' \
    || true
else
  echo 'journalctl is not installed'
fi

echo '=== power supply ==='
shopt -s nullglob
for supply in /sys/class/power_supply/*; do
  [[ -d "$supply" ]] || continue
  echo "-- $(basename "$supply")"
  if [[ -r "$supply/uevent" ]]; then
    cat "$supply/uevent"
  else
    echo 'uevent is not readable'
  fi
done

if command -v upower >/dev/null 2>&1; then
  upower -d || true
fi

echo '=== GPU ==='
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
else
  echo 'nvidia-smi is not installed'
fi

echo '=== sleep ==='
echo -n 'state: '
cat /sys/power/state 2>/dev/null || true
echo -n 'mem_sleep: '
cat /sys/power/mem_sleep 2>/dev/null || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl --failed --no-pager || true
fi
