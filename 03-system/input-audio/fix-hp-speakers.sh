#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Let PipeWire see the HP SoundWire speakers.
#
# h7607a-hardware can install 72-h7607a-no-microphone.rules with MODE 0600 on
# every capture PCM. PipeWire 1.6 then skips the whole card, speakers included.
# This replaces that rule with the udev file next to this script and
# restores root:audio mode 0660 on the live capture nodes.
#
#   sudo bash 03-system/input-audio/fix-hp-speakers.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

product="$(tr -d '\0' </sys/class/dmi/id/product_name)"
board="$(tr -d '\0' </sys/class/dmi/id/board_name)"
[[ "$product" == "HP OmniBook X Laptop 14-ks000" && "$board" == "8F22" ]] || {
  echo "refusing: speaker node fix is for the HP OmniBook X 14-ks000, board 8F22" >&2
  echo "found: product='$product' board='$board'" >&2
  exit 1
}

src="$(cd "$(dirname "$0")" && pwd)/udev/72-h7607a-no-microphone.rules"
[[ -f "$src" ]] || {
  echo "missing $src" >&2
  exit 1
}

rule=/etc/udev/rules.d/72-h7607a-no-microphone.rules
install -d -m 0755 /etc/udev/rules.d
if [[ -f "$rule" && ! -f "${rule}.bak" ]]; then
  cp -a "$rule" "${rule}.bak"
fi
install -m 0644 "$src" "$rule"

udevadm control --reload-rules
# The old rule used MODE:= so a reload does not restore the kernel mode.
shopt -s nullglob
for node in /dev/snd/pcmC[0-9]*D[0-9]*c; do
  chown root:audio "$node"
  chmod 0660 "$node"
done
udevadm trigger --subsystem-match=sound --action=change
udevadm settle || true

echo "capture nodes:"
ls -l /dev/snd/pcmC[0-9]*D[0-9]*c || true

user_name="${SUDO_USER:-}"
if [[ -n "$user_name" && "$user_name" != root ]]; then
  user_id="$(id -u "$user_name")"
  if [[ -S "/run/user/${user_id}/bus" ]]; then
    runuser -u "$user_name" -- env \
      XDG_RUNTIME_DIR="/run/user/${user_id}" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${user_id}/bus" \
      systemctl --user restart wireplumber
    echo "WirePlumber restarted for ${user_name}."
    echo "Run hp-audio-route.py next. The pro-audio profile mutes the speaker amps."
  fi
else
  echo "No desktop user in SUDO_USER. Restart WirePlumber from that session, then run hp-audio-route.py."
fi
