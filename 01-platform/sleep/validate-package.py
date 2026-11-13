#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Validate the complete trial payload before making it available for root install."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path(__file__).resolve().parent
release = '7.0.0-1022-nvidia'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
expected = {
    'linux-nvidia-7.0_7.0.0.orig.tar.gz':'c6343795c8c7e4feff55f5b309365c8e0eaf49cd6abcb412e32315313f149536',
    'linux-nvidia-7.0_7.0.0-1022.23~24.04.1.diff.gz':'6dbf6661592f7b6053253eea6b5411e21974627d9b76d4d3e105653c243d7718',
}
for name,value in expected.items():
    assert sha(root/name) == value,name
assert sha(root/'allocator.patch') == '0ababbaed19c7108e8564916fac1b8fecc44010e7f3e4b419c34d01c66049e19'
image = root/'build/arch/arm64/boot/Image'
raw = image.read_bytes()
assert raw[:2] == b'MZ' and raw[56:60] == b'ARMd','Invalid arm64 EFI image header'
assert b'HP N1X trial: using firmware-coordinated LPI' in raw,'HP patch marker absent'
assert b'hp-sleep-wake1' in raw,'Wake-trial build marker absent'
assert (root/'build/include/config/kernel.release').read_text().strip() == release
abi = json.loads((root/'abi-validation.json').read_text())
assert abi['all_passed'] and len(abi['modules']) == 7,'Missing retained-module checks'
order = (root/'build/modules.order').read_text().splitlines()
assert len(order) > 1000,'Incomplete stock-module build'
module_dir = root/f'stage/lib/modules/{release}'
installed_order = (module_dir/'modules.order').read_text().splitlines()
expected_order = []
for name in order:
    # Linux 7 records object names in the build list, then installs .ko files.
    relative = Path('kernel')/Path(name).with_suffix('.ko')
    expected_order.append(str(relative))
    base = module_dir/relative
    assert any(Path(str(base)+suffix).is_file() for suffix in ('','.zst','.xz','.gz')),name
assert installed_order == expected_order,'Installed module order differs from the full build'
assert (module_dir/'modules.dep').is_file()
private_names = ('nvidia','nvidia_modeset','nvidia_drm','nvidia_uvm',
                 'hid_asus','mt8901_acp_sdw_legacy_mach','soundwire_mtk')
selected_modules = {}
for name in (*private_names,'nvme','xhci_pci','xhci_plat_hcd','i2c_hid_acpi'):
    location = subprocess.check_output(
        ['modinfo','-b',str(root/'stage'),'-k',release,'-n',name],text=True).strip()
    if location == '(builtin)':
        assert name not in private_names,(name,location)
        selected_modules[name] = location
        continue
    selected = Path(location)
    assert selected.is_file(),name
    expected_dir = module_dir/('updates/h7607a' if name in private_names else 'kernel')
    assert selected.resolve().is_relative_to(expected_dir.resolve()),(name,selected)
    selected_modules[name] = str(selected.relative_to(root/'stage'))
version = subprocess.check_output(['modinfo','-F','vermagic',str(root/'companion/hp_n1x_sleep.ko')],text=True)
assert version.startswith(release+' ')
subprocess.run(['python3',str(root/'tests/test-hp-idle.py'),str(root/'linux')],check=True)
subprocess.run(['python3',str(root/'tests/test-eint-wake.py'),str(root/'linux')],check=True)
patch = (root/'1096-eint-wake.patch').read_bytes()
assert hashlib.sha1(f'blob {len(patch)}\0'.encode()+patch).hexdigest() == '8f488083d7b0f35770925867edab2f38a85f210e'
subprocess.run(['patch','--dry-run','--reverse','--fuzz=0','-p1','-i',str(root/'1096-eint-wake.patch')],
               cwd=root/'linux',check=True,stdout=subprocess.DEVNULL)
assert '.has_event_mask = true' in (root/'linux/drivers/pinctrl/mediatek/pinctrl-mt8901.c').read_text()
subprocess.run(['systemd-analyze','verify','--man=no',str(root/'hp-sleep-wake-kernel-trial.service')],check=True)
def normalized_config(path):
    return [line for line in path.read_text().splitlines()
            if not re.match(r'^CONFIG_(RUSTC_VERSION|RUSTC_LLVM_VERSION|RUST_IS_AVAILABLE|RUSTC_HAS_SLICE_AS_FLATTENED)=',line)]
assert normalized_config(root/'original.config') == normalized_config(root/'build/.config')
record = {
    'all_passed':True, 'kernel_release':release,
    'image_sha256':sha(image),'hp_patch_sha256':sha(root/'hp-firmware-idle.patch'),
    'nvidia_wake_patch_sha256':sha(root/'1096-eint-wake.patch'),
    'configuration_matches_original':True,'stock_modules_checked':len(order),
    'module_resolution':selected_modules,
    'retained_module_abi':abi,'companion_sha256':sha(root/'companion/hp_n1x_sleep.ko'),
    'scope':'Compile, source-function tests, package completeness, EFI header and module ABI. Physical HP boot/sleep still pending.',
}
(root/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
files = [image,root/'companion/hp_n1x_sleep.ko',root/'validation.json',
         root/'prepare-oneboot.py',root/'hp-sleep-wake-trial.install',root/'hp-sleep-wake-trial.hook',
         root/'hp-sleep-wake-kernel-trial.service',root/'battery-sleep-log',root/'PROVENANCE.txt',
         root/'check-trial-boot.py',root/'hp-firmware-idle.patch']
files += [root/'1096-eint-wake.patch',root/'tests/test-eint-wake.py']
files += sorted(path for path in (root/'stage').rglob('*') if path.is_file() and not path.is_symlink())
(root/'TRIAL-SHA256SUMS').write_text(''.join(f'{sha(path)}  {path.relative_to(root)}\n' for path in files))
print(f'Trial validated: {len(order)} stock modules, 7 retained drivers, EFI image and source tests.')
