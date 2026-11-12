#!/bin/sh
# Pause or resume hypridle's 5-minute panel blank.
# hypridle is configured to honor a systemd idle inhibitor.
set -eu
runtime=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
pidfile=$runtime/hp-idle-hold.pid
mkdir -p "$runtime"

holding() {
  [ -f "$pidfile" ] || return 1
  pid=$(cat "$pidfile" 2>/dev/null || true)
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null
}

if holding; then
  kill "$(cat "$pidfile")" 2>/dev/null || true
  rm -f "$pidfile"
else
  rm -f "$pidfile"
  nohup systemd-inhibit --what=idle --mode=block --who=hyprbar \
    --why='Pause the 5 minute screen blank' sleep infinity \
    >/dev/null 2>&1 &
  echo $! > "$pidfile"
  disown || true
fi
pkill -RTMIN+11 -x waybar 2>/dev/null || true
