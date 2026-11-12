#!/bin/sh
# Cycle balanced -> performance -> power-saver -> balanced.
set -eu
current=$(powerprofilesctl get 2>/dev/null || echo balanced)
case "$current" in
  balanced) next=performance ;;
  performance) next=power-saver ;;
  power-saver) next=balanced ;;
  *) next=balanced ;;
esac
powerprofilesctl set "$next"
pkill -RTMIN+10 -x waybar 2>/dev/null || true
