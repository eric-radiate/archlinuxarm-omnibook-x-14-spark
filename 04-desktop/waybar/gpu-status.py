#!/usr/bin/env python3
import json,subprocess,os
from pathlib import Path
try:
    r=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,temperature.gpu,power.draw,clocks.sm','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,check=True)
    util,temp,power,clock=[v.strip() for v in r.stdout.splitlines()[0].split(',')]
    details = f'NVIDIA RTX Spark N1X\nUsage {util}% · {temp}°C\nPower {power} W · Clock {clock} MHz'
    try:
        mem = {line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
        used = (mem['MemTotal'] - mem['MemAvailable']) / 1048576
        total = mem['MemTotal'] / 1048576
        soc = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
        details += f'\nCPU load (1 min): {os.getloadavg()[0]:.2f}\nRAM {used:.1f} / {total:.1f} GiB\nSoC {soc:g}°C'
    except (OSError, ValueError, KeyError):
        pass
    print(json.dumps({'text':f'GPU {util}% {temp}°C','tooltip':details}))
except (OSError,subprocess.SubprocessError,ValueError,IndexError):
    print(json.dumps({'text':'GPU n/a','tooltip':'GPU statistics unavailable'}))
