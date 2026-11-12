#!/bin/sh
# Turn walk-away blanking on or off. The watcher reads this file each second.
set -eu
state=${XDG_STATE_HOME:-$HOME/.local/state}/hp-presence.enabled
mkdir -p "$(dirname "$state")"
current=1
if [ -f "$state" ]; then
  current=$(cat "$state" 2>/dev/null || echo 1)
fi
if [ "$current" = 0 ]; then
  printf '1\n' > "$state"
else
  printf '0\n' > "$state"
fi
pkill -RTMIN+9 -x waybar 2>/dev/null || true
