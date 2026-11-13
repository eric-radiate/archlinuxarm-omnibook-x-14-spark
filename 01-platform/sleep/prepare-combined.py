#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Back up boot and make one normal entry using the sleep kernel plus HP audio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SLEEP=None
CANDIDATE=None
FIRMWARE_DIRECTORY=None
sys.path.insert(0,str(REPO/"lib"))
from hp_boot import transaction

BOOT=Path("/boot")
PAYLOAD=Path("/usr/local/lib/hp-sleep-wake-kernel")
RELEASE="7.0.0-1022-nvidia"
MODULE="updates/h7607a/mt8901-acp-sdw-legacy-mach.ko"
IMAGE=BOOT/"vmlinuz-hp-omnibook"
INITRD=BOOT/"initramfs-hp-omnibook.img"
SHELL=BOOT/"EFI/HP-OMNIBOOK"
RECOVERY=BOOT/"loader/recovery"
ENTRIES=BOOT/"loader/entries"
NORMAL=ENTRIES/"h7607a.conf"
PRESET=Path("/etc/mkinitcpio.d/hp-omnibook.preset")
STOCK_PRESET=Path("/etc/mkinitcpio.d/linux-n1x-nvidia-bin.preset")
ARCHIVED_PRESET=PAYLOAD/"original-stock.preset"
REPORT=PAYLOAD/"combined-install.json"
BACKUPS=Path("/var/backups/hp-combined-boot")
DSDT_SHA="e4971160feb9cbc27b652a5f9fa10979834886ecfba06ed36ff5c2749c1a1e4e"
RECOGNIZED={"h7607a.conf","hp-audio-trial.conf","hp-wake-trial.conf"}
CREATED_DIRS=[]
PREVIOUS_ONESHOT=None
ATTEMPTED_CLEAR=False
OBSOLETE=("initramfs-linux-n1x-hp-audio-test.img",
          "initramfs-linux-n1x-hp-wake-test.img","vmlinuz-linux-n1x-hp-wake-test")


def require(value,message):
    if not value:raise RuntimeError(message)


def sha(file):
    with Path(file).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def efivar(name):
    for file in Path("/sys/firmware/efi/efivars").glob(name+"-*"):
        return file.read_bytes()[4:].decode("utf-16-le").rstrip("\0")
    return None


def startup_copy(original):
    require("hp_spark_" not in original and "hp_audio_trial" not in original,
            "The normal boot script already contains a trial marker.")
    lines=original.splitlines()
    calls=[i for i,line in enumerate(lines) if line.startswith("%homefilesystem%\\vmlinuz-linux-n1x ")]
    require(len(calls)==1,"Expected one normal kernel invocation.")
    args=lines[calls[0]].split()
    initrds=[arg for arg in args if arg.startswith("initrd=")]
    require(len(initrds)==1 and initrds[0] in
            ("initrd=\\initramfs-linux-n1x.img","initrd=%homefilesystem%\\initramfs-linux-n1x.img"),
            "Unrecognized normal initramfs argument.")
    lines=[line.replace("vmlinuz-linux-n1x",IMAGE.name).replace("initramfs-linux-n1x.img",INITRD.name)
           for line in lines]
    lines[calls[0]]+=" processor.hp_n1x_firmware_idle=1 hp_spark_wake_trial=1 nvme.quirks=1e81:6d14:simple_suspend"
    return "\n".join(lines)+"\n"


def backup_boot(directory):
    files=[p for p in BOOT.rglob("*") if p.is_file() and not p.is_symlink()]
    manifest={str(p.relative_to(BOOT)):sha(p) for p in files}
    require(shutil.disk_usage(directory).free > sum(p.stat().st_size for p in files)+512*1024**2,
            "Not enough space for a complete boot backup.")
    archive=directory/"boot.tar"
    with tarfile.open(archive,"w",dereference=False) as out:
        out.add(BOOT,arcname="boot")
    with tarfile.open(archive) as saved:
        for name,expected in manifest.items():
            with saved.extractfile("boot/"+name) as stream:
                require(hashlib.file_digest(stream,"sha256").hexdigest()==expected,
                        "Boot archive verification failed.")
    (directory/"boot-files.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"Verified full boot backup: {archive}",flush=True)
    return manifest



def load_inputs():
    require(SLEEP is not None and CANDIDATE is not None and FIRMWARE_DIRECTORY is not None,
            "Specify the local sleep bundle, HP audio module and private firmware directory.")
    validation=json.loads((SLEEP/"validation.json").read_text())
    require(validation["all_passed"],"Sleep bundle validation did not pass.")
    subprocess.run(["sha256sum","--check","--strict","--quiet","TRIAL-SHA256SUMS"],
                   cwd=SLEEP,check=True)
    module_version=subprocess.check_output(["modinfo","-F","srcversion",str(CANDIDATE)],text=True).strip()
    require(module_version=="9834795298B30A6CAE8BF85","Unexpected HP audio source version.")
    subprocess.run([sys.executable,str(REPO/"01-platform/sleep/verify-modules.py"),
                    str(SLEEP/"build/Module.symvers"),str(CANDIDATE)],check=True)
    stage=SLEEP/"stage/lib/modules"/RELEASE
    module_files={str(p.relative_to(stage)):sha(p) for p in stage.rglob("*")
                  if p.is_file() and not p.is_symlink()}
    require(len(module_files)>1000,"Incomplete sleep module bundle.")
    firmware=json.loads((REPO/"pins/hp-speaker-firmware.json").read_text())["files"]
    require(len(firmware)==3,"Expected the exact HP firmware and two tunings.")
    values={"kernel_image_sha256":validation["image_sha256"],
            "sleep_companion_sha256":validation["companion_sha256"],
            "new_audio_module_sha256":sha(CANDIDATE),"new_audio_srcversion":module_version,
            "firmware_files":firmware,
            "scope":"Maintainer combined boot; subsequent physical audio/sleep qualification required."}
    return values,module_files,firmware


def main():
    global PREVIOUS_ONESHOT, ATTEMPTED_CLEAR
    require(os.geteuid()==0,"Run with sudo.")
    require(os.uname().release==RELEASE and "#23~24.04.1" in os.uname().version,
            "Prepare this while running the current original kernel.")
    require(not any(x in Path("/proc/cmdline").read_text() for x in ("hp_spark_","hp_audio_trial")),
            "A trial module tree is active; do not modify a mounted payload.")
    for key,value in (("sys_vendor","HP"),("board_vendor","HP"),
                      ("product_name","HP OmniBook X Laptop 14-ks000"),("board_name","8F22"),
                      ("bios_version","F.05")):
        require(Path("/sys/class/dmi/id",key).read_text().strip()==value,"Unexpected HP hardware/BIOS.")
    require(Path("/sys/class/nvme/nvme0/model").read_text().strip()=="RPEYJ1TBMNV1QWX",
            "This boot is qualified only for the current Ramaxel SSD.")
    for key,value in (("vendor","0x1e81"),("device","0x6d14")):
        require(Path("/sys/class/nvme/nvme0/device",key).read_text().strip()==value,
                "Unexpected SSD PCI identity.")
    require(Path("/sys/class/nvme/nvme0/firmware_rev").read_text().strip()=="HPS1",
            "Unexpected SSD firmware; qualify it separately.")
    require(not Path("/var/lib/hp-nvme-migration/prepared.json").exists(),"NVMe migration guard is active.")
    require(os.path.ismount(BOOT),"Mount /boot first.")
    require(sha("/sys/firmware/acpi/tables/DSDT")==DSDT_SHA,"Unexpected active battery DSDT.")
    require(efivar("LoaderEntryDefault")=="h7607a.conf","Unexpected persistent default.")
    previous_oneshot=efivar("LoaderEntryOneShot")
    PREVIOUS_ONESHOT=previous_oneshot
    require(previous_oneshot in (None,"","hp-audio-trial.conf","hp-wake-trial.conf"),
            "Another one-shot boot is pending.")
    entries={p.name for p in ENTRIES.glob("*.conf")}
    require("h7607a.conf" in entries and entries<=RECOGNIZED,"Unrecognized boot entries need review.")
    for file in (IMAGE,INITRD,SHELL,RECOVERY,PRESET,ARCHIVED_PRESET,REPORT):
        require(not file.exists() and not file.is_symlink(),f"Already exists: {file}; inspect first.")
    require(STOCK_PRESET.is_file(),"The original stock preset is missing.")
    values,module_files,firmware=load_inputs()
    stage=PAYLOAD/"root/lib/modules"/RELEASE
    actual={str(p.relative_to(stage)) for p in stage.rglob("*") if p.is_file() and not p.is_symlink()}
    require(actual==module_files.keys(),"Installed sleep module tree differs from the validated build.")
    for name,value in module_files.items():
        require(sha(stage/name)==value,"Sleep module mismatch: "+name)
    require(sha(SLEEP/"build/arch/arm64/boot/Image")==values["kernel_image_sha256"],"Kernel image changed.")
    require(sha(PAYLOAD/"hp_n1x_sleep.ko")==values["sleep_companion_sha256"],"Sleep companion changed.")
    candidate=CANDIDATE
    require(sha(candidate)==values["new_audio_module_sha256"],"Audio module changed.")
    require(subprocess.check_output(["systemctl","is-enabled","hp-sleep-wake-kernel-trial.service"],
                                     text=True).strip()=="enabled","The sleep companion service must remain enabled.")
    hook=Path("/etc/initcpio/hooks/hp-sleep-wake-trial").read_text()
    require("/sysroot" in hook and str(PAYLOAD) in hook and "hp_spark_wake_trial" in hook,
            "Unexpected module-tree bind hook.")
    firmware_paths=[Path("/usr/lib/firmware/cirrus",row["target"]) for row in firmware]
    for row,file in zip(firmware,firmware_paths):
        require(sha(FIRMWARE_DIRECTORY/row["target"])==row["sha256"],"Staged HP firmware missing or changed.")
        require(not file.exists() or sha(file)==row["sha256"],"Conflicting installed HP firmware: "+str(file))
    startup=startup_copy((BOOT/"EFI/H7607A/startup.nsh").read_text())
    require(shutil.disk_usage(BOOT).free > (SLEEP/"build/arch/arm64/boot/Image").stat().st_size+32*1024**2,
            "Insufficient boot partition space even for the kernel copy.")
    config=PAYLOAD/"mkinitcpio.conf"
    targets=[stage/MODULE,config,NORMAL,IMAGE,INITRD,PRESET,STOCK_PRESET,ARCHIVED_PRESET,REPORT,SHELL/"Shell.efi",SHELL/"startup.nsh",
             RECOVERY/"h7607a-original.conf",RECOVERY/"README.txt"]
    for name in entries-{"h7607a.conf"}:
        targets.extend([ENTRIES/name,RECOVERY/name])
    obsolete=[BOOT/name for name in OBSOLETE if (BOOT/name).is_file()]
    targets.extend(obsolete)
    targets.extend(firmware_paths)
    with transaction(targets,base=BACKUPS) as backup:
        original_manifest=backup_boot(backup)
        original_entry=NORMAL.read_bytes()
        shutil.copy2(candidate,stage/MODULE)
        for row,file in zip(firmware,firmware_paths):
            file.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(FIRMWARE_DIRECTORY/row["target"],file)
            file.chmod(0o644)
        config.write_text(config.read_text()+"\nFILES+=("+" ".join(str(p) for p in firmware_paths)+")\n")
        work_image=backup/"combined-initramfs.img"
        subprocess.run(["mkinitcpio","-k",RELEASE,"-r",str(PAYLOAD/"root"),"-c",str(config),
                        "-g",str(work_image),"--nopost"],check=True)
        with tempfile.TemporaryDirectory(prefix="hp-combined-image-") as directory:
            subprocess.run(["lsinitcpio","--early","--extract",str(work_image)],cwd=directory,
                           stdout=subprocess.DEVNULL,check=True)
            require(sha(Path(directory)/"kernel/firmware/acpi/DSDT.aml")==DSDT_SHA,"Battery DSDT missing.")
            subprocess.run(["lsinitcpio","--cpio","--extract",str(work_image)],cwd=directory,
                           stdout=subprocess.DEVNULL,check=True)
            matches=list((Path(directory)/"usr/lib/modules"/RELEASE).rglob("mt8901-acp-sdw-legacy-mach.ko*"))
            require(len(matches)==1 and sha(matches[0])==values["new_audio_module_sha256"],
                    "Combined image has the wrong audio module.")
            require((Path(directory)/"hooks/hp-sleep-wake-trial").is_file(),"Matching-module hook is missing.")
            for row in firmware:
                require(sha(Path(directory)/"usr/lib/firmware/cirrus"/row["target"])==row["sha256"],
                        "Combined image lacks HP tuning.")
        require(shutil.disk_usage(BOOT).free > work_image.stat().st_size+
                (SLEEP/"build/arch/arm64/boot/Image").stat().st_size+32*1024**2,
                "Insufficient space for the verified combined image and kernel.")
        shutil.copyfile(SLEEP/"build/arch/arm64/boot/Image",IMAGE)
        shutil.copyfile(work_image,INITRD)
        require(sha(INITRD)==sha(work_image),"Combined initramfs copy differs.")
        require(sha(IMAGE)==values["kernel_image_sha256"],"Kernel copy differs.")
        SHELL.mkdir()
        CREATED_DIRS.append(SHELL)
        shutil.copyfile(BOOT/"EFI/H7607A/Shell.efi",SHELL/"Shell.efi")
        (SHELL/"startup.nsh").write_text(startup)
        RECOVERY.mkdir()
        CREATED_DIRS.append(RECOVERY)
        (RECOVERY/"h7607a-original.conf").write_bytes(original_entry)
        (RECOVERY/"README.txt").write_text(
            "Original boot files remain under /EFI/H7607A and the original kernel/initramfs names.\n"
            "To recover the previous normal entry from an EFI shell, copy:\n"
            "cp \\loader\\recovery\\h7607a-original.conf \\loader\\entries\\h7607a.conf\n"
            "Then restart. This restores the original kernel, whose sleep is not qualified.\n"
            f"The complete verified boot archive and changed-file receipt are in {backup}.\n")
        for name in entries-{"h7607a.conf"}:
            shutil.copyfile(ENTRIES/name,RECOVERY/name)
            (ENTRIES/name).unlink()
        NORMAL.write_text("title Arch Linux ARM - HP OmniBook X\n"
                          "efi /EFI/HP-OMNIBOOK/Shell.efi\noptions -startup -delay 0\n")
        # A bound #25 module tree must never rebuild the frozen #23 recovery image.
        shutil.copy2(STOCK_PRESET,ARCHIVED_PRESET)
        STOCK_PRESET.unlink()
        PRESET.write_text(f"ALL_config='{config}'\nALL_kver='{IMAGE}'\nPRESETS=('default')\n"
                          f"default_image='{INITRD}'\ndefault_options='-r {PAYLOAD}/root'\n")
        require({p.name for p in ENTRIES.glob("*.conf")}=={"h7607a.conf"},"Extra Linux entries remain.")
        changed_names={"loader/entries/"+name for name in entries}
        changed_names.update(file.name for file in obsolete)
        for name,value in original_manifest.items():
            if name not in changed_names:
                require(sha(BOOT/name)==value,"An unrelated boot file changed: "+name)
        report=dict(values,backup=str(backup),normal_entry="h7607a.conf",
                    kernel=str(IMAGE),initramfs=str(INITRD),combined_audio_sleep_test="pending reboot",
                    visible_linux_entries=["h7607a.conf"],recovery_entry=str(RECOVERY/"h7607a-original.conf"))
        REPORT.write_text(json.dumps(report,indent=2)+"\n");REPORT.chmod(0o644)
        os.sync()
        ATTEMPTED_CLEAR=True
        subprocess.run(["bootctl","--esp-path=/boot","set-oneshot",""],check=True)
        # These images are now backed up and have no active menu entry.
        for file in obsolete:
            file.unlink()
        os.sync()
    print("Installed one normal Linux boot entry with the sleep kernel and HP audio firmware.")
    print("Separate audio/sleep test entries are archived outside the active menu.")
    print("The original kernel and EFI boot files remain available for recovery; no reboot was requested.")
    print("Save work and reboot normally. Combined audio and sleep still need verification.")


def install():
    try:
        main()
    except BaseException:
        if ATTEMPTED_CLEAR and PREVIOUS_ONESHOT:
            subprocess.run(["bootctl","--esp-path=/boot","set-oneshot",PREVIOUS_ONESHOT],check=False)
        for directory in reversed(CREATED_DIRS):
            try:directory.rmdir()
            except OSError:pass
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sleep_work",type=Path,help="Previously built and short-tested sleep bundle")
    parser.add_argument("audio_module",type=Path,help="Locally built HP identity module")
    parser.add_argument("firmware_directory",type=Path,help="Private staged cirrus directory")
    arguments=parser.parse_args()
    SLEEP=arguments.sleep_work.resolve()
    CANDIDATE=arguments.audio_module.resolve()
    FIRMWARE_DIRECTORY=arguments.firmware_directory.resolve()
    try:install()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
