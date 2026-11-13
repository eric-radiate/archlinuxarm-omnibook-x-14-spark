#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Install the reviewed kernel as a one-shot boot; keep normal boot intact."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOOT = Path('/boot')
PAYLOAD = Path('/usr/local/lib/hp-sleep-wake-kernel')
RELEASE = '7.0.0-1022-nvidia'
DSDT_SHA256 = 'e4971160feb9cbc27b652a5f9fa10979834886ecfba06ed36ff5c2749c1a1e4e'

def require(condition, message):
    if not condition:
        raise SystemExit(message)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

require(os.geteuid() == 0, 'Run this script with sudo.')
require(os.uname().release == RELEASE, 'Unexpected running kernel.')
for key, value in (('vendor', '0x1e81'), ('device', '0x6d14')):
    require(Path('/sys/class/nvme/nvme0/device', key).read_text().strip() == value,
            'This trial is only for the reviewed Ramaxel SSD.')
for name, value in (('product_name','HP OmniBook X Laptop 14-ks000'),
                    ('board_name','8F22'),('bios_version','F.05')):
    require(Path('/sys/class/dmi/id',name).read_text().strip() == value,
            'Unexpected HP identity or BIOS; stopping.')
require(digest('/sys/firmware/acpi/tables/DSDT') == DSDT_SHA256,
        'The active HP DSDT differs from the reviewed battery fix.')
require(digest('/etc/initcpio/acpi_override/DSDT.aml') == DSDT_SHA256,
        'The saved HP DSDT override differs from the reviewed battery fix.')
subprocess.run(['sha256sum','--check','--strict','--quiet','TRIAL-SHA256SUMS'],
               cwd=HERE,check=True)
receipt = json.loads((HERE / 'validation.json').read_text())
require(receipt['all_passed'], 'The build/ABI validation did not pass.')
require(os.path.ismount(BOOT), '/boot is not mounted.')
normal_paths = [BOOT / 'vmlinuz-linux-n1x', BOOT / 'initramfs-linux-n1x.img',
                BOOT / 'EFI/H7607A/startup.nsh', BOOT / 'EFI/H7607A/Shell.efi',
                BOOT / 'loader/entries/h7607a.conf',
                BOOT / 'loader/loader.conf']
normal_hashes = {str(path):digest(path) for path in normal_paths}
require('default h7607a.conf' in (BOOT / 'loader/loader.conf').read_text().splitlines(),
        'The normal boot default has changed; inspect it before preparing this trial.')
image = HERE / 'build/arch/arm64/boot/Image'
trial_image = BOOT / 'vmlinuz-linux-n1x-hp-wake-test'
trial_initrd = BOOT / 'initramfs-linux-n1x-hp-wake-test.img'
shell = BOOT / 'EFI/HP-WAKE-TRIAL'
entry = BOOT / 'loader/entries/hp-wake-trial.conf'
unit = Path('/etc/systemd/system/hp-sleep-wake-kernel-trial.service')
for target in (PAYLOAD,trial_image,trial_initrd,shell,entry,unit,
               Path('/etc/initcpio/install/hp-sleep-wake-trial'),
               Path('/etc/initcpio/hooks/hp-sleep-wake-trial')):
    require(not target.exists(), f'{target} already exists; inspect it before replacing.')
require(shutil.disk_usage(BOOT).free > image.stat().st_size +
        (BOOT / 'initramfs-linux-n1x.img').stat().st_size * 2 + 64*1024**2,
        'Insufficient boot-partition space for an additional trial image.')
require((HERE / f'stage/lib/modules/{RELEASE}/modules.dep').is_file(),
        'Staged matching modules are missing.')
stage_size = sum(path.stat().st_size for path in (HERE / 'stage').rglob('*')
                 if path.is_file() and not path.is_symlink())
require(shutil.disk_usage('/usr/local/lib').free > stage_size + 1024**3,
        'Insufficient space for the separate trial module tree.')
PAYLOAD.mkdir(mode=0o755,parents=True)
shutil.copytree(HERE / 'stage',PAYLOAD / 'root',symlinks=True)
shutil.copyfile(HERE / 'companion/hp_n1x_sleep.ko',PAYLOAD / 'hp_n1x_sleep.ko')
shutil.copyfile(HERE / 'validation.json',PAYLOAD / 'validation.json')
shutil.copyfile(HERE / 'PROVENANCE.txt',PAYLOAD / 'PROVENANCE.txt')
for path in (PAYLOAD / 'hp_n1x_sleep.ko',PAYLOAD / 'validation.json',PAYLOAD / 'PROVENANCE.txt'):
    path.chmod(0o644)
logger = Path('/usr/lib/systemd/system-sleep/battery-sleep-log')
if logger.exists():
    shutil.copyfile(logger,PAYLOAD / 'battery-sleep-log.before')
shutil.copyfile(HERE / 'battery-sleep-log',logger)
logger.chmod(0o755)

for source, destination in (
    ('hp-sleep-wake-trial.install','/etc/initcpio/install/hp-sleep-wake-trial'),
    ('hp-sleep-wake-trial.hook','/etc/initcpio/hooks/hp-sleep-wake-trial')):
    target = Path(destination)
    require(not target.exists(), f'{target} already exists; stopping.')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE / source,target)
    target.chmod(0o755)
config = PAYLOAD / 'mkinitcpio.conf'
config.write_text(Path('/etc/mkinitcpio.conf').read_text() + '\nHOOKS+=(hp-sleep-wake-trial)\n')
shutil.copyfile(image,trial_image)
subprocess.run(['mkinitcpio','-k',RELEASE,'-r',str(PAYLOAD / 'root'),
                '-c',str(config),'-g',str(trial_initrd),'--nopost'],check=True)
with tempfile.TemporaryDirectory(prefix='hp-trial-initrd-') as directory:
    subprocess.run(['lsinitcpio','--early','--extract',str(trial_initrd)],
                   cwd=directory,check=True,stdout=subprocess.DEVNULL)
    require(digest(Path(directory) / 'kernel/firmware/acpi/DSDT.aml') == DSDT_SHA256,
            'The trial initramfs does not contain the reviewed HP DSDT.')
contents = subprocess.check_output(['lsinitcpio','--cpio','--list',str(trial_initrd)],
                                   text=True)
require('hooks/hp-sleep-wake-trial' in contents,
        'The trial initramfs is missing its separate-module-tree hook.')

shell.mkdir(exist_ok=True)
shutil.copyfile(BOOT / 'EFI/H7607A/Shell.efi',shell / 'Shell.efi')
startup = (BOOT / 'EFI/H7607A/startup.nsh').read_text()
startup = startup.replace('vmlinuz-linux-n1x','vmlinuz-linux-n1x-hp-wake-test')
startup = startup.replace('initramfs-linux-n1x.img',trial_initrd.name)
lines = startup.splitlines()
modified = 0
for i,line in enumerate(lines):
    if line.startswith('%homefilesystem%\\vmlinuz-linux-n1x-hp-wake-test '):
        lines[i] += ' processor.hp_n1x_firmware_idle=1 hp_spark_wake_trial=1 nvme.quirks=1e81:6d14:simple_suspend'
        modified += 1
require(modified == 1, 'Could not identify the kernel invocation in the boot script.')
(shell / 'startup.nsh').write_text('\n'.join(lines) + '\n')
entry.write_text('title Arch Linux ARM - HP wake and SSD sleep trial (one boot)\n'
                 'efi /EFI/HP-WAKE-TRIAL/Shell.efi\noptions -startup -delay 0\n')
require(not unit.exists(), 'A sleep trial unit already exists; stopping.')
shutil.copyfile(HERE / unit.name,unit)
unit.chmod(0o644)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable',unit.name],check=True)
require(all(digest(path) == value for path,value in normal_hashes.items()),
        'A normal boot file changed unexpectedly; do not reboot.')
(PAYLOAD / 'normal-boot-hashes.json').write_text(json.dumps(normal_hashes,indent=2)+'\n')
os.sync()
subprocess.run(['bootctl','--esp-path=/boot','set-oneshot',entry.name],check=True)
print('HP sleep trial prepared for ONE boot. No reboot was requested.')
print('The original kernel, initramfs, boot script, entry and default are unchanged.')
print('Save your work, then reboot when ready. Run check-trial-boot.py before any supervised desk test.')
print('If the trial fails to boot, restart; the original HP entry remains the default.')
