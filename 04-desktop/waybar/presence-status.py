#!/usr/bin/env python3
"""Waybar status for walk-away blanking. Click toggles it."""
import json
import os
from pathlib import Path

state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'hp-presence.enabled'
enabled = True
try:
    if state.exists() and state.read_text().strip() == '0':
        enabled = False
except OSError:
    pass

if enabled:
    text, klass, tip = 'away', 'on', 'Walk-away blanking is on\nClick to turn it off'
else:
    text, klass, tip = 'away off', 'off', 'Walk-away blanking is off\nClick to turn it on'

print(json.dumps({'text': text, 'class': klass, 'tooltip': tip}))
