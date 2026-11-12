#!/usr/bin/env python3
import json
import subprocess

try:
    result = subprocess.run(
        ['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'],
        capture_output=True, text=True, timeout=2, check=True,
    )
    volume = round(float(result.stdout.split()[1]) * 100)
    muted = 'MUTED' in result.stdout
    print(json.dumps({
        'text': 'muted' if muted else f'vol {volume}%',
        'class': 'muted' if muted else 'active',
        'tooltip': (
            f'Built-in speakers · {volume}%'
            + (' · muted' if muted else '')
            + '\nClick: mute · Scroll: volume · Right-click: mixer'
        ),
    }))
except (OSError, subprocess.SubprocessError, ValueError, IndexError):
    print(json.dumps({
        'text': 'vol n/a',
        'class': 'unavailable',
        'tooltip': 'No default speaker is available',
    }))
