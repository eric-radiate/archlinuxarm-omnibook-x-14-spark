#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Summarize trial admission and driver readiness after the one-time boot."""
import json
from pathlib import Path
import subprocess
import os

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return f'unavailable: {error}'

cmdline = Path('/proc/cmdline').read_text().strip()
result = {'release':os.uname().release,'version':os.uname().version,
          'trial_boot':'hp_spark_wake_trial=1' in cmdline,
          'idle_path_opt_in':'processor.hp_n1x_firmware_idle=1' in cmdline,
          'mem_sleep':Path('/sys/power/mem_sleep').read_text().strip()}
service = subprocess.run(['systemctl','is-active','hp-sleep-wake-kernel-trial.service'],
                         capture_output=True,text=True)
result['companion_service'] = service.stdout.strip()
version = Path('/sys/module/hp_n1x_sleep/version')
result['companion_version'] = version.read_text().strip() if version.is_file() else None
result['cpu0_idle_states'] = {}
for state in sorted(Path('/sys/devices/system/cpu/cpu0/cpuidle').glob('state*')):
    result['cpu0_idle_states'][state.name] = {
        key:(state/key).read_text().strip() for key in ('name','desc','latency','residency')
        if (state/key).is_file()}
result['nvidia_power'] = read('/proc/driver/nvidia/gpus/000f:01:00.0/power')
result['battery'] = {key:read(Path('/sys/class/power_supply/BAT0',key))
                     for key in ('status','capacity','energy_now','power_now')}
result['admission_log'] = subprocess.run(
    ['journalctl','-k','-b','--no-pager','-g',
     'HP N1X trial|hierarchical LPI|Invalid FFH|Invalid PSCI|hp-n1x-sleep'],
    capture_output=True,text=True).stdout
result['failed_units'] = subprocess.run(['systemctl','--failed','--no-pager'],
                                        capture_output=True,text=True).stdout
module_path = '/usr/lib/modules/7.0.0-1022-nvidia'
expected_root = '/usr/local/lib/hp-sleep-wake-kernel/root/lib/modules/7.0.0-1022-nvidia'
result['module_mount_roots'] = [row[3] for line in Path('/proc/self/mountinfo').read_text().splitlines()
                               if len(row := line.split()) > 4 and row[4] == module_path]
gpu = Path('/sys/bus/pci/devices/000f:01:00.0/driver')
result['gpu_driver'] = gpu.resolve().name if gpu.is_symlink() else None
result['trial_checks'] = {
    'trial_command_line':result['trial_boot'] and result['idle_path_opt_in'],
    'trial_kernel_version':'hp-sleep-wake1' in result['version'],
    'matching_module_tree':expected_root in result['module_mount_roots'],
    's2idle_selected': '[s2idle]' in result['mem_sleep'],
    'companion_ready':result['companion_service'] == 'active' and result['companion_version'] == '0.2',
    'firmware_idle_admitted':'HP N1X trial: using firmware-coordinated LPI' in result['admission_log'],
    'flat_deep_state_present':len(result['cpu0_idle_states']) > 2 and any(
        state.get('residency') == '4294967295' for state in result['cpu0_idle_states'].values()),
    'nvidia_bound':result['gpu_driver'] == 'nvidia',
}
result['ready_for_short_lid_test'] = all(result['trial_checks'].values())
result['nvme_quirks'] = read('/sys/class/nvme/nvme0/quirks')
result['nvme_quirks_parameter'] = read('/sys/module/nvme/parameters/quirks')
result['trial_checks']['nvme_full_suspend'] = (
    'simple_suspend' in result['nvme_quirks'] and
    result['nvme_quirks_parameter'] == '1e81:6d14:simple_suspend')
result['ready_for_short_lid_test'] = all(result['trial_checks'].values())
result['physical_low_power_sleep_verified'] = False
print(json.dumps(result,indent=2))
