#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Compile the actual HP gate/latency functions with mocked platform queries."""
from pathlib import Path
import subprocess
import tempfile
import difflib

import sys
root = Path(sys.argv[1]).resolve()
source = (root / 'drivers/acpi/processor_idle.c').read_text()

def function(name):
    import re
    match = re.search(r'static (?:bool|void) ' + name + r'\([^;]*?\n\{', source, re.S)
    if not match:
        raise RuntimeError(f'Missing production function {name}')
    start = match.start()
    cursor = match.end()
    depth = 1
    while depth:
        char = source[cursor]
        depth += (char == '{') - (char == '}')
        cursor += 1
    return source[start:cursor]

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#define U32_MAX UINT32_MAX
#define ACPI_CSTATE_FFH 2
#define CONFIG_ACPI_PROCESSOR 1
#define IS_BUILTIN(value) (value)
#define pr_info_once(...) ((void)0)
enum {DMI_PRODUCT_NAME, DMI_BOARD_NAME, DMI_BIOS_VERSION};
static const char *identity[] = {"HP OmniBook X Laptop 14-ks000", "8F22", "F.05"};
static bool hp_n1x_firmware_idle;
static bool osc_os_lpi_support_confirmed = true;
static bool osi = true;
static bool dmi_match(int field, const char *value) { return !strcmp(identity[field],value); }
static bool acpi_processor_ffh_lpi_hierarchy_supported(void) { return osi; }
struct cpuidle_device;
struct cpuidle_driver;
static int acpi_idle_lpi_enter_direct(struct cpuidle_device *dev,
                                    struct cpuidle_driver *drv, int index)
{ (void)dev; (void)drv; return index; }
struct acpi_lpi_state { uint32_t min_residency; unsigned int entry_method; };
struct cpuidle_state {
 uint32_t exit_latency;
 int (*enter_s2idle)(struct cpuidle_device *, struct cpuidle_driver *, int);
};
'''
main = r'''
int main(void) {
 const char *original;
 struct acpi_lpi_state lpi={.min_residency=U32_MAX,.entry_method=ACPI_CSTATE_FFH};
 struct cpuidle_state state={.exit_latency=966};
 const uint32_t inputs[]={966,U32_MAX,U32_MAX-1,U32_MAX-6609,U32_MAX-6610,0};
 const uint32_t expected[]={7576,U32_MAX,U32_MAX,U32_MAX,U32_MAX,6610};
 assert(!hp_n1x_firmware_idle_requested());
 assert(acpi_lpi_can_coordinate());
 hp_n1x_prepare_flat_lpi_state(&lpi,&state,1);
 assert(state.exit_latency==966 && !state.enter_s2idle);
 hp_n1x_firmware_idle=true;
 assert(hp_n1x_firmware_idle_requested());
 assert(!acpi_lpi_can_coordinate());
 for(unsigned int i=0;i<3;i++) {
   original=identity[i]; identity[i]="other";
   assert(!hp_n1x_firmware_idle_requested());
   assert(acpi_lpi_can_coordinate());
   state=(struct cpuidle_state){.exit_latency=966};
   hp_n1x_prepare_flat_lpi_state(&lpi,&state,1);
   assert(state.exit_latency==966 && !state.enter_s2idle);
   identity[i]=original;
 }
 for(unsigned int i=0;i<sizeof(inputs)/sizeof(inputs[0]);i++) {
   state=(struct cpuidle_state){.exit_latency=inputs[i]};
   hp_n1x_prepare_flat_lpi_state(&lpi,&state,1);
   assert(state.exit_latency==expected[i]);
   assert(state.enter_s2idle==acpi_idle_lpi_enter_direct);
   assert(lpi.min_residency==U32_MAX);
 }
 state=(struct cpuidle_state){.exit_latency=966};
 hp_n1x_prepare_flat_lpi_state(&lpi,&state,0);
 assert(state.exit_latency==966 && !state.enter_s2idle);
 lpi.entry_method=0;
 hp_n1x_prepare_flat_lpi_state(&lpi,&state,1);
 assert(state.exit_latency==966 && !state.enter_s2idle);
 lpi.entry_method=ACPI_CSTATE_FFH; lpi.min_residency=1500;
 hp_n1x_prepare_flat_lpi_state(&lpi,&state,1);
 assert(state.exit_latency==966 && state.enter_s2idle==acpi_idle_lpi_enter_direct);
 hp_n1x_firmware_idle=false; osi=false;
 assert(!acpi_lpi_can_coordinate());
 osi=true; osc_os_lpi_support_confirmed=false;
 assert(!acpi_lpi_can_coordinate());
 puts("Production-code HP admission, opt-out, overflow boundaries and tick callbacks passed");
 return 0;
}
'''
body = '\n\n'.join(function(name) for name in (
    'hp_n1x_firmware_idle_requested', 'acpi_lpi_can_coordinate',
    'hp_n1x_prepare_flat_lpi_state'))
with tempfile.TemporaryDirectory(prefix='hp-idle-test-') as directory:
    harness = Path(directory) / 'harness.c'
    binary = Path(directory) / 'harness'
    harness.write_text(prefix + body + main)
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-o',str(binary),str(harness)], check=True)
    subprocess.run([str(binary)],check=True)
