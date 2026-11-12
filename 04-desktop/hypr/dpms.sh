#!/bin/sh
# Turn the internal panel on or off. Hyprland 0.57 only accepts the boolean form.
case "$1" in
  on) hyprctl dispatch 'hl.dsp.dpms(true)' ;;
  off) hyprctl dispatch 'hl.dsp.dpms(false)' ;;
  *) echo "usage: dpms.sh on|off" >&2; exit 2 ;;
esac
