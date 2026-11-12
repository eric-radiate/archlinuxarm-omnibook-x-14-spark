#!/usr/bin/env python3
import json,subprocess
try:
    r=subprocess.run(['wpctl','get-volume','@DEFAULT_AUDIO_SOURCE@'],capture_output=True,text=True,timeout=2,check=True)
    volume=round(float(r.stdout.split()[1])*100)
    muted='MUTED' in r.stdout
    print(json.dumps({'text':'mic off' if muted else f'mic {volume}%', 'class':'muted' if muted else 'active', 'tooltip':f'Built-in microphone · {volume}%'+ (' · muted' if muted else '')+'\nClick: mute · Scroll: level · Right-click: input settings'}))
except (OSError,subprocess.SubprocessError,ValueError,IndexError):
    print(json.dumps({'text':'mic n/a','class':'unavailable','tooltip':'No default microphone is available'}))
