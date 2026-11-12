#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Route HP OmniBook X SoundWire playback to the internal speakers.

The shipped ASUS UCM enables O152/PDI3. On this HP, DL0 (hw:1,0) opens only
after O150/I032, O151/I033 and PDI2=DP2. Headphone PCM (hw:1,1) stays wired
so a headset still works.

WirePlumber keeps this card on the pro-audio profile. That profile runs the
UCM verb, which mutes the speaker amps, and it never runs the Speaker device
sequence that would unmute them. wpctl set-profile takes a numeric index, and
index 0 is off, so a name passed by mistake saves the card as off. This script
puts pro-audio back and re-asserts the amp switches after WirePlumber settles.
"""
import json
import subprocess
import time
from pathlib import Path
from ctypes import (
    CDLL, POINTER, c_char_p, c_int, c_long, c_uint, c_void_p, byref,
)
from ctypes.util import find_library

CARD = b'hw:1'

BOOLS_ON = (
    'O150 I032 Switch',
    'O151 I033 Switch',
    'O152 I032 Switch',
    'O153 I033 Switch',
    'O156 I034 Switch',
    'O157 I035 Switch',
    'Speaker Switch',
    'AMP1 Speaker Switch',
    'AMP2 Speaker Switch',
    'Headset Mic Switch',
    'cs42l43 Decimator 1 Switch',
    'cs42l43 Decimator 2 Switch',
)

ENUMS = {
    'PDI2 Demux': 'DP2',
    'PDI3 Demux': 'DP3',
    'PDI5 Demux': 'DP5',
    'PDI6 Demux': 'DP6',
    'cs42l43 Headphone L Input 1': 'DP5RX1',
    'cs42l43 Headphone R Input 1': 'DP5RX2',
}


def _alsa():
    lib = find_library('asound')
    if not lib:
        raise SystemExit('libasound not found')
    alsa = CDLL(lib)
    alsa.snd_ctl_open.argtypes = [POINTER(c_void_p), c_char_p, c_int]
    alsa.snd_ctl_ascii_elem_id_parse.argtypes = [c_void_p, c_char_p]
    alsa.snd_ctl_elem_id_malloc.argtypes = [POINTER(c_void_p)]
    alsa.snd_ctl_elem_value_malloc.argtypes = [POINTER(c_void_p)]
    alsa.snd_ctl_elem_info_malloc.argtypes = [POINTER(c_void_p)]
    alsa.snd_ctl_elem_info.argtypes = [c_void_p, c_void_p]
    alsa.snd_ctl_elem_write.argtypes = [c_void_p, c_void_p]
    alsa.snd_ctl_elem_info_set_id.argtypes = [c_void_p, c_void_p]
    alsa.snd_ctl_elem_value_set_id.argtypes = [c_void_p, c_void_p]
    alsa.snd_ctl_elem_info_get_type.argtypes = [c_void_p]
    alsa.snd_ctl_elem_info_get_type.restype = c_int
    alsa.snd_ctl_elem_info_get_items.argtypes = [c_void_p]
    alsa.snd_ctl_elem_info_get_items.restype = c_uint
    alsa.snd_ctl_elem_info_get_item_name.argtypes = [c_void_p]
    alsa.snd_ctl_elem_info_get_item_name.restype = c_char_p
    alsa.snd_ctl_elem_info_set_item.argtypes = [c_void_p, c_uint]
    alsa.snd_ctl_elem_value_set_integer.argtypes = [c_void_p, c_uint, c_long]
    alsa.snd_ctl_elem_value_set_enumerated.argtypes = [c_void_p, c_uint, c_uint]
    alsa.snd_strerror.restype = c_char_p
    alsa.snd_pcm_open.argtypes = [POINTER(c_void_p), c_char_p, c_int, c_int]
    alsa.snd_pcm_close.argtypes = [c_void_p]
    return alsa


def set_ctrl(alsa, ctl, name, value):
    eid = c_void_p()
    alsa.snd_ctl_elem_id_malloc(byref(eid))
    if alsa.snd_ctl_ascii_elem_id_parse(eid, f"name='{name}'".encode()) != 0:
        return f'skip parse {name}'
    inf = c_void_p()
    alsa.snd_ctl_elem_info_malloc(byref(inf))
    alsa.snd_ctl_elem_info_set_id(inf, eid)
    if alsa.snd_ctl_elem_info(ctl, inf) < 0:
        return f'skip missing {name}'
    typ = alsa.snd_ctl_elem_info_get_type(inf)
    val = c_void_p()
    alsa.snd_ctl_elem_value_malloc(byref(val))
    alsa.snd_ctl_elem_value_set_id(val, eid)
    if typ == 3:
        items = []
        for i in range(alsa.snd_ctl_elem_info_get_items(inf)):
            alsa.snd_ctl_elem_info_set_item(inf, i)
            alsa.snd_ctl_elem_info(ctl, inf)
            items.append(alsa.snd_ctl_elem_info_get_item_name(inf).decode())
        if isinstance(value, str):
            if value not in items:
                return f'skip enum {name}={value} not in {items}'
            value = items.index(value)
        alsa.snd_ctl_elem_value_set_enumerated(val, 0, int(value))
    else:
        alsa.snd_ctl_elem_value_set_integer(val, 0, int(value))
    r = alsa.snd_ctl_elem_write(ctl, val)
    if r < 0:
        return f'fail {name}: {alsa.snd_strerror(r).decode()}'
    return None


def pcm_ok(alsa, spec, stream):
    pcm = c_void_p()
    # NONBLOCK: do not wait. EBUSY means PipeWire already holds the device.
    r = alsa.snd_pcm_open(byref(pcm), spec, stream, 1)
    if r == 0:
        alsa.snd_pcm_close(pcm)
        return True
    err = alsa.snd_strerror(r).decode() if r else ''
    return 'Device or resource busy' in err or r == -16


def pipewire_card():
    try:
        raw = subprocess.run(
            ['pw-dump'], capture_output=True, text=True, timeout=3, check=True,
        ).stdout
        data = json.loads(raw)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None, '', None
    for obj in data:
        info = obj.get('info') or {}
        props = info.get('props') or {}
        if props.get('device.name') != 'alsa_card.platform-mtk_sdw_mc':
            continue
        params = info.get('params') or {}
        current = params.get('Profile') or []
        current_name = current[0].get('name', '') if current else ''
        pro = next(
            (p for p in (params.get('EnumProfile') or []) if p.get('name') == 'pro-audio'),
            None,
        )
        return obj.get('id'), current_name, None if pro is None else pro.get('index')
    return None, '', None


def ensure_pro_audio():
    """Keep the card on pro-audio. Index 0 is the off profile."""
    for _ in range(20):
        dev, current, index = pipewire_card()
        if dev is None:
            time.sleep(0.5)
            continue
        if current == 'pro-audio':
            print(f'pipewire profile pro-audio (device {dev})')
            return
        if index is None:
            print('pro-audio profile is not listed; leaving the card alone')
            return
        print(f'pipewire profile {current or "unset"} -> pro-audio index {index}')
        subprocess.run(
            ['wpctl', 'set-profile', str(dev), str(index)],
            check=False,
        )
        time.sleep(1)
        return


def switch_is_on(name):
    try:
        raw = subprocess.run(
            ['amixer', '-c', '1', 'cget', f'name={name}'],
            capture_output=True, text=True, timeout=2, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return 'values=on' in raw


def apply_route(alsa, ctl):
    errors = []
    for name in BOOLS_ON:
        err = set_ctrl(alsa, ctl, name, 1)
        if err:
            errors.append(err)
    err = set_ctrl(alsa, ctl, 'Headphone Switch', 0)
    if err:
        errors.append(err)
    for name, value in ENUMS.items():
        err = set_ctrl(alsa, ctl, name, value)
        if err:
            errors.append(err)
    return errors


def require_board():
    try:
        product = Path("/sys/class/dmi/id/product_name").read_text(encoding="utf-8").strip()
        board = Path("/sys/class/dmi/id/board_name").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit(f"cannot read DMI: {exc}") from exc
    if product != "HP OmniBook X Laptop 14-ks000" or board != "8F22":
        raise SystemExit(
            "refusing: speaker route is for the HP OmniBook X 14-ks000, board 8F22 "
            f"(found {product!r} board {board!r})"
        )


def main():
    require_board()
    ensure_pro_audio()
    alsa = _alsa()
    ctl = c_void_p()
    r = alsa.snd_ctl_open(byref(ctl), CARD, 0)
    if r < 0:
        raise SystemExit(f'cannot open {CARD.decode()}: {alsa.snd_strerror(r).decode()}')
    errors = apply_route(alsa, ctl)
    # The UCM verb mutes the amps when WirePlumber finishes the profile.
    # Re-apply until that has happened, then once more so the speakers stay on.
    quiet = 0
    for _ in range(16):
        time.sleep(0.5)
        if all(switch_is_on(name) for name in (
            'Speaker Switch', 'AMP1 Speaker Switch', 'AMP2 Speaker Switch',
        )):
            quiet += 1
            if quiet >= 4:
                break
            continue
        quiet = 0
        errors.extend(apply_route(alsa, ctl))
    spk = pcm_ok(alsa, b'hw:1,0', 0)
    hp = pcm_ok(alsa, b'hw:1,1', 0)
    amps = all(switch_is_on(name) for name in (
        'Speaker Switch', 'AMP1 Speaker Switch', 'AMP2 Speaker Switch',
    ))
    print(f'speaker pcm hw:1,0 {"open" if spk else "blocked"}')
    print(f'headphone pcm hw:1,1 {"open" if hp else "blocked"}')
    print(f'speaker amps {"on" if amps else "off"}')
    if errors:
        print('notes:')
        for e in dict.fromkeys(errors):
            print(' ', e)
    if not spk or not amps:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
