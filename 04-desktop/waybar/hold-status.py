#!/usr/bin/env python3
"""Waybar status for the hypridle hold. Click pauses the 5-minute blank."""
import json
import os
from pathlib import Path

runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
pidfile = runtime / 'hp-idle-hold.pid'
holding = False
try:
    pid = int(pidfile.read_text().strip())
    os.kill(pid, 0)
    holding = True
except (OSError, ValueError):
    holding = False

if holding:
    tip = '5-minute blank is paused\nClick to let the timer run'
    klass = 'on'
else:
    tip = '5-minute blank is running\nClick to pause it'
    klass = 'off'

print(json.dumps({'text': 'hold', 'class': klass, 'tooltip': tip}))
