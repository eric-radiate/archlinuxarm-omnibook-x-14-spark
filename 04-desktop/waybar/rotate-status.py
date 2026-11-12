#!/usr/bin/env python3
"""Waybar icon for the internal panel orientation."""
import json
import subprocess

portrait = False
try:
    monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], timeout=2))
    panel = next(m for m in monitors if m['name'] == 'eDP-1')
    portrait = int(panel.get('transform') or 0) % 2 == 1
except (OSError, subprocess.SubprocessError, ValueError, StopIteration, KeyError):
    pass

if portrait:
    tip = 'Panel is portrait\nClick for landscape'
else:
    tip = 'Panel is landscape\nClick to turn 90 degrees'

print(json.dumps({
    'text': '↻',
    'class': 'portrait' if portrait else 'landscape',
    'tooltip': tip,
}))
