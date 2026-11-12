#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
 bluetooth)
  if command -v blueman-manager >/dev/null; then
   exec blueman-manager
  fi
  exec kitty --title 'Bluetooth setup' bluetoothctl
  ;;
 audio|audio-input)
  if command -v pavucontrol >/dev/null; then
   if [[ $1 == audio-input ]]; then exec pavucontrol --tab=4; fi
   exec pavucontrol --tab=3
  fi
  exec kitty --title 'Audio settings' sh -c 'printf "pavucontrol is not installed.\n"; read -r answer'
  ;;
 *) exit 2 ;;
esac
