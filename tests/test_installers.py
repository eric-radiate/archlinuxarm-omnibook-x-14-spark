#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Failure cases use temporary files; never invoke live hardware installers."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "01-platform/acpi"),
                str(ROOT / "02-drivers/soundwire")]
import hp_boot
import battery_aml
import patch_module


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


battery = load("install_battery", "01-platform/acpi/install-battery.py")
audio = load("install_two_amps", "02-drivers/soundwire/install-two-amps.py")


class Installers(unittest.TestCase):
    def test_vram_rollback_uses_current_invocation(self):
        script = ROOT / "02-drivers/nvidia-display/vram-mode.sh"
        for initially_present in (False, True):
            with self.subTest(initially_present=initially_present), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                conf = directory / "vram.conf"
                if initially_present:
                    conf.write_text("actual original\n")
                (directory / "vram.conf.bak").write_text("stale backup\n")
                harness = r'''
source "$1"
CONF="$2/vram.conf"
rebuild() {
  if [[ ! -e "$TEST_DIR/failed-once" ]]; then
    touch "$TEST_DIR/failed-once"
    return 1
  fi
  return 0
}
export TEST_DIR="$2"
if change_mode shared; then exit 9; fi
'''
                result = subprocess.run(["bash", "-c", harness, "test", str(script), tmp],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(conf.exists(), initially_present)
                if initially_present:
                    self.assertEqual(conf.read_text(), "actual original\n")
                self.assertEqual((directory / "vram.conf.bak").read_text(), "stale backup\n")
                self.assertFalse(list(directory.glob("*.rollback.*")))

    def test_partial_image_build_restores_all_previous_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(hp_boot.os, "geteuid", return_value=0):
            directory = Path(tmp)
            conf, image, new = [directory / s for s in ("conf", "initramfs", "new")]
            conf.write_bytes(b"prior config"); image.write_bytes(b"bootable prior image")
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                with hp_boot.transaction([conf, image, new], directory / "backups"):
                    conf.write_bytes(b"changed")
                    image.write_bytes(b"partial new image")
                    new.write_bytes(b"new file")
                    raise RuntimeError("build failed")
            self.assertEqual(conf.read_bytes(), b"prior config")
            self.assertEqual(image.read_bytes(), b"bootable prior image")
            self.assertFalse(new.exists())
            self.assertEqual(len(list((directory / "backups").glob("*/files.json"))), 1)

    def test_conflict_in_either_override_directory_is_rejected(self):
        for index in (0, 1):
            with self.subTest(directory=index), tempfile.TemporaryDirectory() as tmp:
                directories = [Path(tmp) / s for s in ("etc", "usr")]
                for d in directories: d.mkdir()
                (directories[index] / "other.aml").write_bytes(b"unreviewed")
                with self.assertRaisesRegex(RuntimeError, "Conflicting"):
                    battery.check_overrides(directories)

    def test_duplicate_overrides_are_rejected_even_if_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirs = [Path(tmp) / s for s in ("etc", "usr")]
            for d in dirs:
                d.mkdir(); (d / "DSDT.aml").write_bytes(b"same")
            with self.assertRaisesRegex(RuntimeError, "Multiple"):
                battery.check_overrides(dirs)

    def test_hook_edit_is_idempotent_and_preserves_other_settings(self):
        source = "MODULES=(nvme)\nHOOKS=(h7607a-preload base udev)\nCOMPRESSION=zstd\n"
        edited = battery.hook_config(source)
        self.assertIn("h7607a-preload acpi_override base udev", edited)
        self.assertIn("COMPRESSION=zstd", edited)
        self.assertEqual(edited, battery.hook_config(edited))
        for bad in ("HOOKS=(base udev)\n", "HOOKS=(\nbase\n)\n", source + source):
            with self.assertRaises(RuntimeError):
                battery.hook_config(bad)

    def test_minimal_aml_edit_preserves_every_unrelated_byte(self):
        # Synthetic table: it deliberately cannot satisfy the real firmware hash gate.
        data = bytearray(148362)
        data[:4] = b"DSDT"; struct.pack_into("<I", data, 4, len(data))
        struct.pack_into("<I", data, 24, 0x01072009)
        data[battery_aml.OFFSET:battery_aml.OFFSET + len(battery_aml.FIELD)] = battery_aml.FIELD
        data[9] = (-sum(data)) & 255
        result = battery_aml.edit(bytes(data))
        self.assertEqual(len(result), len(data))
        self.assertEqual(sum(result) % 256, 0)
        allowed = {9, 24, 25, 26, 27} | set(range(battery_aml.OFFSET, battery_aml.OFFSET + 15))
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(data, result)) if i not in allowed))
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            battery_aml.patch(bytes(data))
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            battery_aml.patch(result)

    def test_soundwire_refuses_unreviewed_and_signed_inputs(self):
        for raw in (b"", b"ELF other module", b"ELF other module~Module signature appended~\n"):
            with self.assertRaises(ValueError):
                patch_module.patch(raw)

    def test_soundwire_rebuild_extracts_and_checks_embedded_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "initramfs"; image.write_bytes(b"image")
            raw = b"synthetic correctly embedded module"
            def extract(args, **kwargs):
                destination = Path(kwargs["cwd"]) / "usr/lib/modules/test"
                destination.mkdir(parents=True)
                (destination / "soundwire-mtk.ko").write_bytes(raw)
            with patch.object(audio, "IMAGE", image), patch.object(audio.subprocess, "run", side_effect=extract):
                with patch.object(audio, "PATCHED", hashlib.sha256(raw).hexdigest()):
                    audio.verify_image()
                with self.assertRaisesRegex(RuntimeError, "different SoundWire"):
                    audio.verify_image()


if __name__ == "__main__":
    unittest.main()
