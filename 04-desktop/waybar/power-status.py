#!/usr/bin/env python3
"""Waybar label for the NVIDIA power profile. Click cycles it."""
import json
import subprocess

ORDER = ('balanced', 'performance', 'power-saver')
LABEL = {
    'balanced': 'bal',
    'performance': 'perf',
    'power-saver': 'save',
}

try:
    profile = subprocess.check_output(
        ['powerprofilesctl', 'get'], text=True, timeout=2,
    ).strip()
except (OSError, subprocess.SubprocessError):
    profile = ''

if profile not in ORDER:
    print(json.dumps({
        'text': 'pwr',
        'class': 'unknown',
        'tooltip': 'Power profile is unavailable',
    }))
else:
    nxt = ORDER[(ORDER.index(profile) + 1) % len(ORDER)]
    print(json.dumps({
        'text': LABEL[profile],
        'class': profile,
        'tooltip': f'Power profile: {profile}\nClick for {nxt}',
    }))
