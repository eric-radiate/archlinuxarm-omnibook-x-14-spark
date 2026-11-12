#!/bin/sh
# Blank eDP-1 when the HP 5MP camera reports the user has left, and wake it
# when they come back. in_proximity0 is HID human presence: 1 present, 0 absent.
# This unit's distance and attention channels stay at the unknown sentinels
# (65535 and 25500), so they are not used.
set -eu

runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
mkdir -p "$runtime"
exec 9>"$runtime/hp-presence.lock"
flock -n 9 || exit 0

dpms=$(dirname "$0")/dpms.sh
enabled_file=${XDG_STATE_HOME:-$HOME/.local/state}/hp-presence.enabled
absent_need=10
present_need=2

# Missing file means on, which is the default. "0" turns blanking off.
enabled() {
  [ -f "$enabled_file" ] || return 0
  [ "$(cat "$enabled_file" 2>/dev/null || echo 1)" != 0 ]
}

pick_sensor() {
  best=
  best_hz=0
  for dev in /sys/bus/iio/devices/iio:device*; do
    [ -r "$dev/name" ] || continue
    [ "$(cat "$dev/name")" = prox ] || continue
    [ -r "$dev/in_proximity0_raw" ] || continue
    hz=$(cat "$dev/in_proximity0_sampling_frequency" 2>/dev/null || echo 0)
    if awk -v a="$hz" -v b="$best_hz" 'BEGIN { exit !(a > b) }'; then
      best=$dev
      best_hz=$hz
    fi
  done
  if [ -z "$best" ]; then
    for dev in /sys/bus/iio/devices/iio:device*; do
      [ -r "$dev/name" ] || continue
      [ "$(cat "$dev/name")" = prox ] || continue
      [ -r "$dev/in_proximity0_raw" ] || continue
      best=$dev
      break
    done
  fi
  printf '%s' "$best"
}

sensor=$(pick_sensor)
if [ -z "$sensor" ]; then
  logger -t hp-presence "no human-presence sensor"
  exit 0
fi

logger -t hp-presence "watching $sensor"
we_blanked=0
absent=0
present=0

while true; do
  if ! enabled; then
    absent=0
    present=0
    if [ "$we_blanked" -eq 1 ]; then
      "$dpms" on || true
      we_blanked=0
      logger -t hp-presence "disabled, panel on"
    fi
    sleep 1
    continue
  fi
  raw=$(cat "$sensor/in_proximity0_raw" 2>/dev/null || true)
  case "$raw" in
    1)
      absent=0
      present=$((present + 1))
      if [ "$we_blanked" -eq 1 ] && [ "$present" -ge "$present_need" ]; then
        "$dpms" on || true
        we_blanked=0
        logger -t hp-presence "present, panel on"
      fi
      ;;
    0)
      present=0
      absent=$((absent + 1))
      if [ "$we_blanked" -eq 0 ] && [ "$absent" -ge "$absent_need" ]; then
        "$dpms" off || true
        we_blanked=1
        logger -t hp-presence "absent, panel off"
      fi
      ;;
  esac
  sleep 1
done
