#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test migration preparation against a fake filesystem; no live settings change."""
from pathlib import Path
import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

SCRIPT=Path(__file__).resolve().parents[1]/"01-platform/sleep/prepare-nvme-migration.py"
class Migration(unittest.TestCase):
    def setup_lab(self, directory):
        spec=importlib.util.spec_from_file_location("migration",SCRIPT)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.ROOT=Path(directory)
        def write(name,data):
            file=m.path(name);file.parent.mkdir(parents=True,exist_ok=True);file.write_text(data)
        write("/boot/loader/loader.conf","default h7607a.conf\n")
        write("/boot/loader/entries/h7607a.conf","efi /EFI/H7607A/Shell.efi\n")
        write("/boot/EFI/H7607A/startup.nsh","original boot and audio markers\n")
        write("/boot/initramfs-linux-n1x.img","original initramfs")
        write("/etc/fstab","unchanged UUIDs\n")
        for service in m.SERVICES:
            write("/etc/systemd/system/"+service,"[Service]\nExecStart=/usr/bin/insmod hp_n1x_sleep.ko\n")
        info={"dmi":{"sys_vendor":"HP","product_name":"HP OmniBook X Laptop 14-ks000","board_name":"8F22"},
              "ssd":{"vendor":"0x1e81","device":"0x6d14","model":"RPEYJ1TBMNV1QWX","serial":"TEST-SOURCE"},
              "boot":{"LoaderEntryOneShot":None},"duplicate_filesystem_uuids":{}}
        return m,info

    def contexts(self,m,fail=False):
        stack=ExitStack()
        stack.enter_context(patch.object(m.os.path,"ismount",return_value=True))
        stack.enter_context(patch.object(m.os,"sync"))
        stack.enter_context(patch.object(m,"require_private_backup"))
        def run(args):
            if fail:raise subprocess.CalledProcessError(1,args)
            return "masked" if "show" in args else ""
        stack.enter_context(patch.object(m,"run",side_effect=run))
        return stack

    def test_prepare_and_cancel_preserve_boot_audio_and_prior_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            m,info=self.setup_lab(directory)
            prior=m.path("/etc/systemd/system/sleep.target")
            prior.symlink_to("/dev/null")
            original={str(p.relative_to(m.ROOT)):p.read_bytes() for p in m.path("/boot").rglob("*") if p.is_file()}
            with self.contexts(m):
                m.prepare(info)
                state=json.loads(m.path(m.STATE).read_text())
                backup=Path(state["backup"])
                self.assertTrue((backup/"boot.tar").is_file())
                self.assertTrue((backup/"configuration.tar").is_file())
                for target in m.TARGETS:
                    self.assertEqual(m.current(m.path("/etc/systemd/system/"+target)),
                                     {"kind":"symlink","link":"/dev/null"})
                for service in m.SERVICES:
                    text=m.path("/etc/systemd/system/"+service+".d/"+m.DROPIN).read_text()
                    self.assertIn("ConditionPathExists=!"+m.STATE,text)
                m.restore(backup,info)
            self.assertTrue(prior.is_symlink())
            for target in m.TARGETS[1:]:self.assertFalse(m.path("/etc/systemd/system/"+target).is_symlink())
            self.assertFalse(m.path(m.STATE).exists())
            for name,data in original.items():self.assertEqual(m.path("/"+name).read_bytes(),data)

    def test_pending_trial_refuses_before_backup_or_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            m,info=self.setup_lab(directory);info["boot"]["LoaderEntryOneShot"]="hp-audio-trial.conf"
            with self.contexts(m),self.assertRaisesRegex(RuntimeError,"one-boot trial"):
                m.prepare(info)
            self.assertFalse(m.path(m.BACKUPS).exists())
            self.assertFalse(m.path(m.STATE).exists())

    def test_failure_restores_config_and_keeps_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            m,info=self.setup_lab(directory)
            with self.contexts(m,fail=True),self.assertRaises(subprocess.CalledProcessError):
                m.prepare(info)
            self.assertFalse(m.path(m.STATE).exists())
            for target in m.TARGETS:self.assertFalse(m.path("/etc/systemd/system/"+target).is_symlink())
            self.assertEqual(len(list(m.path(m.BACKUPS).glob("*/receipt.json"))),1)

    def test_changed_ssd_cannot_reenable_old_sleep(self):
        with tempfile.TemporaryDirectory() as directory:
            m,info=self.setup_lab(directory)
            with self.contexts(m):
                m.prepare(info)
                state=json.loads(m.path(m.STATE).read_text())
                replacement=dict(info,ssd=dict(info["ssd"],serial="REPLACEMENT",model="NEW SSD"))
                with self.assertRaisesRegex(RuntimeError,"SSD has changed"):
                    m.restore(state["backup"],replacement)
            self.assertTrue(m.path(m.STATE).exists())

    def test_custom_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            m,info=self.setup_lab(directory)
            file=m.path("/etc/systemd/system/sleep.target");file.write_text("custom user policy\n")
            with self.contexts(m),self.assertRaisesRegex(RuntimeError,"Custom target"):
                m.prepare(info)
            self.assertEqual(file.read_text(),"custom user policy\n")
            self.assertFalse(m.path(m.BACKUPS).exists())

if __name__=="__main__":unittest.main()
