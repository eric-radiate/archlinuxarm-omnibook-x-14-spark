#!/bin/sh
# Hyprland 0.57 speaks Lua. Waybar 0.15 still sends the old "dispatch workspace N".
exec hyprctl dispatch "hl.dsp.focus({ workspace = $1 })"
