#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose the HP OmniBook X UL1/DP12 microphone while this process runs.

Playback routing and WirePlumber policy are left alone. Capture controls are
restored when the process stops. Install it next to hp-audio-route.py.
"""
import ctypes
import importlib.util
from pathlib import Path
import signal
import subprocess
import sys

CONTROLS = {
    'PDI7 Mux': 'DP12',
    'O020 I168 Switch': 1,
    'O021 I169 Switch': 1,
    'cs42l43 Decimator 3 Switch': 1,
    'cs42l43 Decimator 4 Switch': 1,
    # 128 = 0 dB, 0.5 dB per step; +18 dB improves normal voice level.
    'cs42l43 Decimator 3 Volume': 164,
    'cs42l43 Decimator 4 Volume': 164,
    'cs42l43 DP1TX1 Input': 'Decimator 3',
    'cs42l43 DP1TX2 Input': 'Decimator 4',
}

def main():
    product = Path('/sys/class/dmi/id/product_name').read_text().strip().strip('\0')
    board = Path('/sys/class/dmi/id/board_name').read_text().strip().strip('\0')
    if product != 'HP OmniBook X Laptop 14-ks000' or board != '8F22':
        raise SystemExit(
            'This microphone route is only for the HP OmniBook X 14-ks000, board 8F22 '
            f'(found {product!r} board {board!r})'
        )
    spec = importlib.util.spec_from_file_location('hp_route', Path(__file__).with_name('hp-audio-route.py'))
    route = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(route)
    alsa = route._alsa()
    ctl = ctypes.c_void_p()
    if alsa.snd_ctl_open(ctypes.byref(ctl), b'hw:mt8901soundwire', 0) < 0:
        raise SystemExit('SoundWire mixer unavailable')
    saved = {}
    child = None
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for name in CONTROLS:
            info = subprocess.check_output(['amixer', '-c', 'mt8901soundwire', 'cget', f'name={name}'], text=True)
            value = info.split(': values=')[1].splitlines()[0]
            saved[name] = int({'on': '1', 'off': '0'}.get(value, value))
        for name, value in CONTROLS.items():
            error = route.set_ctrl(alsa, ctl, name, value)
            if error:
                raise RuntimeError(error)
        props = '''{
            factory.name = api.alsa.pcm.source
            node.name = hp.internal-microphone
            node.description = "Built-in Microphone"
            media.class = Audio/Source
            api.alsa.path = "hw:mt8901soundwire,8"
            api.alsa.period-size = 1024
            api.alsa.headroom = 0
            audio.format = S16LE
            audio.rate = 48000
            audio.channels = 2
            audio.position = [ FL FR ]
            priority.session = 1800
            node.suspend-on-idle = true
        }'''
        print('Routing HP PDM2 -> codec DP1 -> controller DP12 -> UL1; creating source', flush=True)
        child = subprocess.Popen(['pw-cli', '-m', 'create-node', 'adapter', props], stdin=subprocess.PIPE)
        code = child.wait()
        if code:
            raise SystemExit(code)
    except KeyboardInterrupt:
        pass
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for name, value in reversed(list(saved.items())):
            error = route.set_ctrl(alsa, ctl, name, value)
            if error:
                print('Restore failed:', error, file=sys.stderr)
        print('Microphone source removed; capture controls restored.', flush=True)

if __name__ == '__main__':
    main()
