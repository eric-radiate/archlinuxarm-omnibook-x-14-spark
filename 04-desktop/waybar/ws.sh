#!/bin/sh
# Print one workspace button. Waybar passes the workspace number.
n=${1:?}
id=$(hyprctl activeworkspace -j 2>/dev/null \
  | sed -n 's/.*"id":[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -n 1)
if [ "$id" = "$n" ]; then
  printf '{"text":"%s","class":"active"}\n' "$n"
else
  printf '{"text":"%s","class":"idle"}\n' "$n"
fi
