#!/bin/sh
# Rotate the internal panel and the ELAN touch coordinates together.
# portrait is Hyprland transform 1 (90 degrees). landscape is 0.
set -eu

case "${1:-}" in
  landscape) transform=0 ;;
  portrait) transform=1 ;;
  toggle)
    transform=$(hyprctl monitors -j | python3 -c 'import json,sys; ms=json.load(sys.stdin); m=next(x for x in ms if x["name"]=="eDP-1"); print(0 if int(m.get("transform") or 0) % 2 else 1)')
    ;;
  *)
    echo "usage: rotate-panel.sh landscape|portrait|toggle" >&2
    exit 2
    ;;
esac

hyprctl eval "
hl.monitor({
    output = 'eDP-1',
    mode = '2880x1800@120.00',
    position = '0x0',
    scale = 1.5,
    transform = $transform,
})
hl.device({
    name = 'elan2513:00-04f3:4664',
    output = 'eDP-1',
    transform = $transform,
})
hl.config({
    input = {
        touchdevice = {
            output = 'eDP-1',
            transform = $transform,
        },
    },
})
"
# Refresh the bar icon without waiting for its poll.
pkill -RTMIN+8 -x waybar 2>/dev/null || true
