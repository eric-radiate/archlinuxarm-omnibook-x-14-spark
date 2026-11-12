#!/usr/bin/env python3
"""Notify once per low-battery band while discharging; never change power state."""
import json,os,subprocess
from pathlib import Path
battery=Path('/sys/class/power_supply/BAT0')
runtime=os.environ.get('XDG_RUNTIME_DIR') or f'/run/user/{os.getuid()}'
state=Path(runtime)/'hp-battery-alert.json'
try:
    capacity=int((battery/'capacity').read_text())
    discharging=(battery/'status').read_text().strip()=='Discharging'
except (OSError,ValueError):
    raise SystemExit(0)
band='critical' if discharging and capacity<=10 else 'warning' if discharging and capacity<=20 else 'normal'
try:
    previous=json.loads(state.read_text()).get('band')
except (OSError,ValueError):
    previous=None
if band!='normal' and band!=previous:
    urgency='critical' if band=='critical' else 'normal'
    subprocess.run(['notify-send','--app-name=Battery','--urgency='+urgency,'--icon=battery-caution-symbolic','Battery low' if band=='warning' else 'Battery critically low',f'{capacity}% remaining. Connect the charger.'],check=True,timeout=5)
state.write_text(json.dumps({'band':band})+'\n')
