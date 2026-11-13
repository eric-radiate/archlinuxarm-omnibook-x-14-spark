#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check current-boot HP amplifier load evidence without changing audio settings."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def parse(log):
    amps = {str(unit): {'channel': 'right' if unit == 0 else 'left',
                       'firmware_version': None, 'tuning_ids': None,
                       'firmware_missing': False, 'calibration_applied': False}
            for unit in (0, 1)}
    for line in log.splitlines():
        device = re.search(r'cs35l56 sdw:0:0:01fa:3556:01:([01]): (.*)', line)
        if not device:
            continue
        amp, message = amps[device[1]], device[2]
        version = re.search(r'DSP1: Firmware: .* v(\d+\.\d+\.\d+),', message)
        if version:
            amp.update(firmware_version=version[1], tuning_ids=None,
                       firmware_missing=False, calibration_applied=False)
        if 'Tuning PID:' in message:
            amp['tuning_ids'] = message
        if 'FIRMWARE_MISSING' in message:
            amp['firmware_missing'] = True
        if 'Calibration applied' in message:
            amp['calibration_applied'] = True
    loaded = all(a['firmware_version'] == '3.13.5' and a['tuning_ids'] and
                 not a['firmware_missing'] for a in amps.values())
    calibrated = all(a['calibration_applied'] for a in amps.values())
    return {'amplifiers': amps, 'both_firmware_and_tunings_loaded': bool(loaded),
            'both_calibrations_applied': calibrated,
            'physical_playback_test': 'Requires listening; not established by kernel logs.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, help='Inspect a saved kernel log instead of the current boot')
    args = parser.parse_args()
    if args.log:
        log = args.log.read_text()
    else:
        for key, expected in (('sys_vendor', 'HP'), ('board_name', '8F22')):
            if Path('/sys/class/dmi/id', key).read_text().strip() != expected:
                raise SystemExit('This checker is scoped to HP board 8F22.')
        log = subprocess.check_output(['journalctl', '-k', '-b', '-o', 'cat', '--no-pager',
                                       '-g', 'cs35l56'], text=True)
    result = parse(log)
    print(json.dumps(result, indent=2))
    if not result['both_firmware_and_tunings_loaded'] or not result['both_calibrations_applied']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
