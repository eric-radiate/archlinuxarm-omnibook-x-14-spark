#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise combined boot installation and rollback without live system writes."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"01-platform/sleep/prepare-combined.py"
def sha(data):return hashlib.sha256(data).hexdigest()

class Combined(unittest.TestCase):
    def exercise(self,failure=None):
        real_tmp=tempfile.TemporaryDirectory
        with real_tmp() as d:
            lab=Path(d)
            spec=importlib.util.spec_from_file_location("combined",SCRIPT)
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            def mapped(*args):
                p=Path(*args)
                return lab/p.relative_to("/") if p.is_absolute() and not p.is_relative_to(lab) else p
            def write(name,data):
                p=mapped(name);p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(data if isinstance(data,bytes) else data.encode());return p
            boot=mapped("/boot");payload=mapped("/usr/local/lib/hp-sleep-wake-kernel")
            original_startup=("if not exist \\initramfs-linux-n1x.img then\nexit /b 1\nendif\n"
                              "%homefilesystem%\\vmlinuz-linux-n1x initrd=\\initramfs-linux-n1x.img root=TEST\n")
            originals={}
            for name,data in {"vmlinuz-linux-n1x":b"old stock kernel",
                              "initramfs-linux-n1x.img":b"old stock image",
                              "initramfs-linux-n1x-hp-audio-test.img":b"old audio image",
                              "initramfs-linux-n1x-hp-wake-test.img":b"old wake image",
                              "vmlinuz-linux-n1x-hp-wake-test":b"sleep kernel25",
                              "EFI/H7607A/Shell.efi":b"shell",
                              "EFI/H7607A/startup.nsh":original_startup,
                              "loader/entries/h7607a.conf":"old normal entry\n",
                              "loader/entries/hp-audio-trial.conf":"audio entry\n",
                              "loader/entries/hp-wake-trial.conf":"wake entry\n",
                              "loader/loader.conf":"default h7607a.conf\n"}.items():
                p=write("/boot/"+name,data);originals[p]=p.read_bytes()
            write("/sys/class/dmi/id/product_name","HP OmniBook X Laptop 14-ks000")
            write("/sys/class/dmi/id/sys_vendor","HP")
            write("/sys/class/dmi/id/board_vendor","HP")
            write("/sys/class/dmi/id/board_name","8F22")
            write("/sys/class/dmi/id/bios_version","F.05")
            write("/sys/class/nvme/nvme0/model","RPEYJ1TBMNV1QWX")
            write("/sys/class/nvme/nvme0/device/vendor","0x1e81")
            write("/sys/class/nvme/nvme0/device/device","0x6d14")
            write("/sys/class/nvme/nvme0/firmware_rev","HPS1")
            write("/proc/cmdline","normal")
            write("/sys/firmware/acpi/tables/DSDT",b"synthetic DSDT")
            write("/etc/initcpio/hooks/hp-sleep-wake-trial",f"/sysroot {payload} hp_spark_wake_trial")
            preset=write("/etc/mkinitcpio.d/linux-n1x-nvidia-bin.preset","original preset\n")
            module=write(str(payload/"root/lib/modules"/m.RELEASE/m.MODULE),b"old audio")
            write(str(payload/"root/lib/modules"/m.RELEASE/"modules.dep"),"dependencies\n")
            write(str(payload/"hp_n1x_sleep.ko"),b"sleep companion")
            config=write(str(payload/"mkinitcpio.conf"),"HOOKS=(h7607a-preload hp-sleep-wake-trial)\n")
            here=lab/"bundle";here.mkdir();audio=lab/"audio";audio.mkdir();sleep=lab/"sleep";sleep.mkdir()
            candidate=audio/"module/mt8901-acp-sdw-legacy-mach.ko";candidate.parent.mkdir();candidate.write_bytes(b"new audio")
            image=sleep/"build/arch/arm64/boot/Image";image.parent.mkdir(parents=True);image.write_bytes(b"sleep kernel25")
            values={"kernel_image_sha256":sha(b"sleep kernel25"),"sleep_companion_sha256":sha(b"sleep companion"),
                    "new_audio_module_sha256":sha(b"new audio")}
            (here/"validation.json").write_text(json.dumps(values))
            (here/"sleep-modules.json").write_text(json.dumps({m.MODULE:sha(b"old audio"),"modules.dep":sha(b"dependencies\n")}))
            fw=[{"target":"cs35l56-b0-dsp1-misc-103c8f22.wmfw","sha256":sha(b"firmware")}]
            (audio/"firmware-map.json").write_text(json.dumps(fw))
            write("/usr/lib/firmware/cirrus/"+fw[0]["target"],b"firmware")
            for key,value in {"HERE":here,"AUDIO":audio,"SLEEP":sleep,"BOOT":boot,"PAYLOAD":payload,
                              "IMAGE":boot/"vmlinuz-hp-omnibook","INITRD":boot/"initramfs-hp-omnibook.img",
                              "SHELL":boot/"EFI/HP-OMNIBOOK","RECOVERY":boot/"loader/recovery",
                              "ENTRIES":boot/"loader/entries","NORMAL":boot/"loader/entries/h7607a.conf",
                              "PRESET":mapped("/etc/mkinitcpio.d/hp-omnibook.preset"),
                              "STOCK_PRESET":preset,"ARCHIVED_PRESET":payload/"original-stock.preset",
                              "REPORT":payload/"combined-install.json","BACKUPS":mapped("/var/backups/hp-combined-boot"),
                              "DSDT_SHA":sha(b"synthetic DSDT")}.items():setattr(m,key,value)
            m.CANDIDATE=candidate
            m.FIRMWARE_DIRECTORY=audio/"firmware/cirrus"
            m.FIRMWARE_DIRECTORY.mkdir(parents=True)
            (m.FIRMWARE_DIRECTORY/fw[0]["target"]).write_bytes(b"firmware")
            module_files=json.loads((here/"sleep-modules.json").read_text())
            calls=[]
            def run(args,**kw):
                calls.append(args)
                if args[0]=="mkinitcpio":
                    Path(args[args.index("-g")+1]).write_bytes(b"partial" if failure=="build" else b"image")
                    if failure=="build":raise subprocess.CalledProcessError(1,args)
                elif args[0]=="lsinitcpio":
                    dest=Path(kw["cwd"])
                    if "--early" in args:
                        p=dest/"kernel/firmware/acpi/DSDT.aml";p.parent.mkdir(parents=True);p.write_bytes(b"synthetic DSDT")
                    else:
                        p=dest/"usr/lib/modules"/m.RELEASE/m.MODULE;p.parent.mkdir(parents=True)
                        p.write_bytes(b"wrong module" if failure=="image" else b"new audio")
                        p=dest/"hooks/hp-sleep-wake-trial";p.parent.mkdir();p.write_bytes(b"hook")
                        p=dest/"usr/lib/firmware/cirrus"/fw[0]["target"];p.parent.mkdir(parents=True);p.write_bytes(b"firmware")
                elif args[0]=="bootctl" and failure=="bootctl" and args[-1]=="":
                    raise subprocess.CalledProcessError(1,args)
                return SimpleNamespace(returncode=0)
            with ExitStack() as stack:
                stack.enter_context(patch.object(m,"load_inputs",return_value=(values,module_files,fw)))
                stack.enter_context(patch.object(m,"Path",mapped))
                stack.enter_context(patch.object(m.os,"geteuid",return_value=0))
                stack.enter_context(patch.object(m.os,"uname",return_value=SimpleNamespace(release=m.RELEASE,version="#23~24.04.1")))
                stack.enter_context(patch.object(m.os.path,"ismount",return_value=True))
                stack.enter_context(patch.object(m.os,"sync"))
                stack.enter_context(patch.object(m,"efivar",side_effect=lambda k:"h7607a.conf" if k=="LoaderEntryDefault" else "hp-audio-trial.conf"))
                stack.enter_context(patch.object(m.subprocess,"check_output",return_value="enabled\n"))
                stack.enter_context(patch.object(m.subprocess,"run",side_effect=run))
                stack.enter_context(patch.object(m.tempfile,"TemporaryDirectory",side_effect=lambda **kw:real_tmp(dir=lab,**kw)))
                if failure:
                    with self.assertRaises((RuntimeError,subprocess.CalledProcessError)):m.install()
                else:m.install()
            if failure:
                for p,data in originals.items():self.assertEqual(p.read_bytes(),data)
                self.assertEqual(module.read_bytes(),b"old audio")
                self.assertEqual(config.read_text(),"HOOKS=(h7607a-preload hp-sleep-wake-trial)\n")
                self.assertTrue(preset.is_file())
                self.assertFalse(m.INITRD.exists())
                self.assertFalse(m.IMAGE.exists())
                self.assertFalse(m.PRESET.exists())
            else:
                self.assertEqual({p.name for p in m.ENTRIES.glob("*.conf")},{"h7607a.conf"})
                self.assertIn("HP-OMNIBOOK",m.NORMAL.read_text())
                self.assertEqual(module.read_bytes(),b"new audio")
                self.assertTrue(m.REPORT.is_file())
                self.assertFalse(preset.exists())
                self.assertEqual(m.ARCHIVED_PRESET.read_text(),"original preset\n")
                self.assertIn("-r",m.PRESET.read_text())
                self.assertTrue((m.RECOVERY/"h7607a-original.conf").is_file())
                for p,data in originals.items():
                    if p.parent!=m.ENTRIES and p.name not in m.OBSOLETE:
                        self.assertEqual(p.read_bytes(),data)
                for name in m.OBSOLETE:self.assertFalse((m.BOOT/name).exists())
            self.assertEqual(len(list(m.BACKUPS.glob("*/boot.tar"))),1)

    def test_one_entry_preserves_originals_and_records_recovery(self):self.exercise()
    def test_partial_build_restores_every_original(self):self.exercise("build")
    def test_wrong_embedded_module_restores_every_original(self):self.exercise("image")
    def test_boot_variable_failure_restores_menu_and_module(self):self.exercise("bootctl")

if __name__=="__main__":unittest.main()
