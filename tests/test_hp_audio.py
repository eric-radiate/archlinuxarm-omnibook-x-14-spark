#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check private staging and distinguish ROM, tuning and calibration evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage = load('stage_hp_firmware', '02-drivers/soundwire/stage-hp-firmware.py')
audio = load('check_hp_audio', '03-system/check/check-hp-audio.py')


def message(unit, text):
    return f'cs35l56 sdw:0:0:01fa:3556:01:{unit}: {text}\n'


def loaded_log():
    return ''.join(message(u, 'Cirrus Logic CS35L56 Rev B0 OTP3 fw:3.4.4 (patched=0)') +
                   message(u, 'DSP1: Firmware: 1a00d6 vendor: 0x2 v3.13.5, 41 algorithms') +
                   message(u, 'Calibration applied') +
                   message(u, f'Tuning PID: 0x103135, SID: {u}, TID: 0x5a0618') for u in (0, 1))


class AudioEvidence(unittest.TestCase):
    def test_initial_rom_line_does_not_override_completed_load(self):
        result = audio.parse(loaded_log())
        self.assertTrue(result['both_firmware_and_tunings_loaded'])
        self.assertTrue(result['both_calibrations_applied'])

    def test_rom_only_and_one_missing_tuning_do_not_pass(self):
        self.assertFalse(audio.parse(message(0, 'DSP1: Firmware: 1a00d6 vendor: 0x2 v3.4.4, 37 algorithms'))[
            'both_firmware_and_tunings_loaded'])
        log = loaded_log().replace(message(1, 'Tuning PID: 0x103135, SID: 1, TID: 0x5a0618'), '')
        self.assertFalse(audio.parse(log)['both_firmware_and_tunings_loaded'])

    def test_later_failed_reprobe_invalidates_prior_success(self):
        log = loaded_log() + message(1, 'DSP1: Firmware: 1a00d6 vendor: 0x2 v3.4.4, 37 algorithms')
        result = audio.parse(log)
        self.assertFalse(result['both_firmware_and_tunings_loaded'])
        self.assertFalse(result['both_calibrations_applied'])

    def test_calibration_is_separate_from_firmware_and_tuning(self):
        result = audio.parse(loaded_log().replace('Calibration applied', 'No calibration data'))
        self.assertTrue(result['both_firmware_and_tunings_loaded'])
        self.assertFalse(result['both_calibrations_applied'])


class FirmwareStaging(unittest.TestCase):
    def fixture(self, root):
        driver = root / 'driver'
        driver.mkdir()
        rows = []
        for name, data in [('firmware.wmfw', b'synthetic WMFW'),
                           ('right.bin', b'synthetic right'), ('left.bin', b'synthetic left')]:
            (driver / name).write_bytes(data)
            rows.append({'source': name, 'target': 'test-' + name, 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})
        return driver, {'files': rows}

    def test_stages_all_three_privately_with_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver, manifest = self.fixture(root)
            out = stage.stage(driver, root / 'private', manifest)
            for row in manifest['files']:
                target = out / 'cirrus' / row['target']
                self.assertEqual(target.read_bytes(), (driver / row['source']).read_bytes())
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((out / 'firmware-map.json').read_text()), manifest)

    def test_last_input_mismatch_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver, manifest = self.fixture(root)
            (driver / 'left.bin').write_bytes(b'wrong board')
            with self.assertRaisesRegex(RuntimeError, 'Unreviewed HP input'):
                stage.stage(driver, root / 'private', manifest)
            self.assertFalse((root / 'private').exists())

    def test_refuses_output_inside_repository(self):
        with self.assertRaisesRegex(RuntimeError, 'outside the source repository'):
            stage.stage('/unused', ROOT / 'private-firmware', {'files': []})


if __name__ == '__main__':
    unittest.main()
