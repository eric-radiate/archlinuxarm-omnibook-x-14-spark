# Experimental HP sleep: evidence and porting

This is a source record of the tested Arch trial on HP OmniBook X 14-ks000,
8F22, F.05, Ramaxel RPEYJ1TBMNV1QWX/HPS1 (PCI 1e81:6d14). It is not a
qualified sleep release or an Omarchy installer. Changing logind lid policy
alone did not fix the power drain.

## Measured on Arch

Battery energy deltas cover the whole unplugged interval, including sleep
transitions. CLOCK_BOOTTIME minus CLOCK_MONOTONIC measures actual suspended
time. Both endpoints were on battery in the same boot.

| Trial | Sample / suspended seconds | Energy | Whole-interval average |
| --- | --- | --- | --- |
| Original idle path, LPS0 + SSD link policy | 608.90 / 603.78 | 2.636 Wh | 15.58 W |
| Firmware idle + LPS0/link, without full SSD suspend | 129.56 / 124.12 | 0.515 Wh | 14.31 W |
| Same + exact SSD simple_suspend quirk | 167.55 / 161.99 | 0.063 Wh | 1.35 W |
| Same + NVIDIA EINT wake patch, kernel #25 | 143.00 / 137.78 | 0.047 Wh | 1.18 W |

These are short samples, not an overnight discharge estimate or a physical
DRIPS-residency percentage. The firmware residency counter is 32-bit at
1GHz and wraps in 4.295 seconds; a single snapshot cannot establish residency.

The final short trial resumed, GPU and Wi-Fi returned, and no system units
failed. The kernel recorded IRQ90, the SYNA3536 internal touchpad wake route.
Lid-open was logged at resume, but opening the lid **alone** was not confirmed
as the trigger. The preceding trial needed the power button. Resume warnings
included an ieee80211 workqueue/suspend warning and SoundWire control-bus
clash `0x80000400`; these remain recorded limitations.

Long (at least 30–60 minutes, preferably over an hour) battery tests, repeated
cycles, and lid-only wake still need qualification. Closed-lid transport is
not qualified. The firmware thermal warning reported earlier establishes an
overheating event; the logs do not prove its precise cause.

## Required parts of the successful trial

All source is in [01-platform/sleep](../01-platform/sleep):

1. `hp-firmware-idle.patch` opts this exact DMI/BIOS into the existing
   firmware-coordinated flat LPI path with
   `processor.hp_n1x_firmware_idle=1`. FFH states get the tick-freezing
   s2idle callback. Ryan Hughes' 6610us DRIPS latency adjustment saturates
   at U32_MAX; the firmware minimum-residency sentinel is preserved.
   Do not call ELST(1) at boot or let ordinary runtime idle enter DRIPS
   while devices are active.
2. The GPL `companion/` supplies LPS0 entry 3,7,5 and exit 6,9,8,4, with
   pending-exit retry, late/early device ordering and 3 seconds of EC settling.
   It allows supported L1/PCI-PM L1.2 only on the reviewed SSD/root bridge.
   It refuses an already-configured unexpected link policy.
3. `nvme.quirks=1e81:6d14:simple_suspend` makes this SSD use full shutdown
   and PCI device suspend instead of its protocol D0 path. The large power
   reduction was observed after adding this parameter. The SSD's advertised
   4mW PS4 is not a measurement of system or actual SSD suspend power.
4. `1096-eint-wake.patch` is NVIDIA commit
   `0f0aeba492533b9dba991f131289d4a17c1f3c5d`, preserved verbatim. It
   synchronizes dynamic wake IRQs with MT8901's separate event mask,
   retains static ACPI wake pins, and restores masks on resume.
5. The tested battery DSDT override and the pinned NVIDIA/HP module tuple
   remain prerequisites. Rebuild **all stock modules and the companion
   against the exact kernel vmlinux**, because matching the release string
   alone does not match split BTF. Seven retained private modules passed
   1360 imported-symbol CRC checks and had no coupled BTF.

The successful mode was s2idle. The separate PSCI `deep` experiment resumed
after about half a second and is not a working alternative here. Extra USB
remote-wake changes from NVIDIA PR662 were reviewed but not applied or tested.

## Build and inspect locally

The recipe adapts Josephine Pfeiffer's pinned native Ubuntu build. Its MIT
notice is in [LICENSES](../LICENSES); kernel changes and companion are GPL.

Use a native AArch64 Ubuntu 24.04 build environment, without root, with
GCC 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1), binutils 2.42, pahole 1.25,
make, bc, bison, flex, libssl-dev, libelf-dev, libdw-dev, zlib1g-dev,
pkg-config, patch, kmod, xz-utils, zstd, gawk, python3 and dpkg-dev.
A rootless container can supply this environment.

Put the original source tarball, vendor diff and modules .deb named in
`build.sh` into SOURCE_CACHE. The canonical Ubuntu pool is
<https://ports.ubuntu.com/ubuntu-ports/pool/main/l/linux-nvidia-7.0/>.
Removed inputs were also published in Josephine's
[inputs-1 release](https://github.com/pfeifferj/archlinuxarm-proart-p16/releases/tag/inputs-1).
Every input must match the pinned hash; a mirror is not an independently
verified upstream signature. No kernel binaries are supplied here.

Inside that environment, using absolute paths and a new work directory:

```bash
SOURCE_CACHE=/path/to/inputs bash 01-platform/sleep/build.sh /path/to/new-work 8
python3 01-platform/sleep/stage.py /path/to/new-work /path/to/verified-private-modules
```

The private directory must contain the seven exact local modules listed in
`retained-modules.json` (including the two-amp SoundWire correction).
Mount the installed directory read-only if using a container. Staging
rechecks hashes and imported CRCs, builds the companion against this vmlinux,
checks the complete stock-module set and writes a local trial manifest.

The source patches and compiler harnesses were checked against the already
built/tested source. The portable build/stage wrappers are new and have not
been run through another full build and physical deployment. Historical
output hashes are in `pins/sleep-results.json`; generated keys and environment
details can change fresh binary hashes. Do not overwrite a live module tree
with files merely sharing the same kernel release.

## Optional one-boot deployment, for maintainers

The staged bundle includes `prepare-oneboot.py`, not a general installer.
It requires this exact hardware, SSD, kernel release, DSDT override, upstream
preset and systemd-boot/EFI-shell layout with `h7607a.conf` as the default.
Review the script locally before running it as root from the work directory.
It refuses pre-existing trial paths; it does not upgrade or remove an older
trial installation.

It installs a separate kernel/initramfs and module tree, a marker-gated
initramfs bind mount under `/sysroot`, and a marker-gated companion service.
The original kernel, initramfs, boot script, entry and default are hash-checked
unchanged. The one-shot entry is selected only at the end. It does not reboot.
An interrupted preparation can leave unused trial files; keep the original
entry and inspect those files before retrying. Cancel a prepared one-shot
with `sudo bootctl --esp-path=/boot set-oneshot ''`.

After a chosen reboot, run the bundle's `check-trial-boot.py`; all admission
checks must pass before a supervised desk test. If the trial fails to boot,
restart into the original default. For rollback while in the trial, choose
the original entry on the next boot. Never remove the trial module tree
while it is bind-mounted by that running kernel.

The original default is not made permanent by this procedure. On the
reference machine a later ordinary reboot returned to the original kernel;
the short sleep result does not establish that every subsequent boot has
the fixes active. On 2026-11-13 the reference machine was subsequently moved
to a [single combined default](combined-boot.md), retaining that same kernel
and matching modules while adding the verified OEM audio setup. Its boot
admission checks pass and stereo playback and microphone capture work.
Physical sleep with the new audio set has not yet been tested; the measured
1.18 W above remains the earlier trial's result.

`prepare-combined.py` records the later promotion workflow, including full
boot backup, off-ESP image generation, embedded module/firmware verification,
archiving test entries, and keeping the original recovery files. Its portable
input wrapper has temporary-filesystem recovery tests; it has not been used
for another fresh physical installation. It does not rerun on an already
promoted machine or qualify its inputs automatically.

For a future drive replacement, see [SSD migration](nvme-migration.md).
The helper pauses sleep until the new SSD has been qualified; it does not
apply the Ramaxel quirk to another vendor/device ID.

`battery-sleep-log` is an optional systemd system-sleep logger. It records
local battery and timing data without changing sleep policy. Keep raw logs
local; they contain boot IDs, timestamps and wake-source information.
Do not copy a measurement from a charging session or different boot into
a claimed discharge rate.

## Omarchy port review (2026-11-12)

Reviewed omarchy-pkgs at `3c267816022a47d8240ef8e081ef3c763d913305`
and omarchy quattro at `ac6cb9c712848741f994d7ecbaccdbab90b526e8`.
The current recipe is newer than the tested 7.0 kernel.

| Mechanism | What a port must establish |
| --- | --- |
| HP audio topology | Recipe already lists 1061, a separate two-amp HP-compatible topology that preserves the four-amp entry. Do not use this repo's legacy binary edit on it. |
| LPI tick/DRIPS, PCI-PM L1.2 | Omarchy carries N1x changes; compare their current semantics with the exact HP trial. |
| EINT wake | Recipe carries NVIDIA 1096; avoid applying a second copy. |
| HP firmware-coordinated path | The exact opt-in change here is for vendor 7.0; review and rebase for Omarchy's LPI implementation. |
| LPS0 | Recipe carries 1111 using noirq callbacks. Our successful s2idle trial used late/early callbacks plus EC settling. Review this difference and firmware eligibility; never duplicate notifications with this companion. |
| SSD full suspend | The 7.3 base source provides `nvme.quirks` and the `simple_suspend` name. Confirm that the built kernel retains it and this drive reports the quirk active; HP runtime power/wake remains untested there. |
| DSDT override | Provide the tested minimal HP fix through Omarchy's own initramfs/UKI mechanism. This Arch hook installer does not implement that port. |
| Boot and rescue | Omarchy uses Limine/UKIs; the Arch EFI-shell one-boot installer does not apply. |

Omarchy has not been installed or physically tested on this machine.
The patches identify mechanisms to port; they do not justify saying Omarchy
sleep works. ASUS SSPM-unhiding and laptop-specific tuning, or DGX Spark
desktop power settings, are not substitutes for HP firmware qualification.

Sources: [Josie's pinned tree](https://github.com/pfeifferj/archlinuxarm-proart-p16/tree/3484cc008a9ee00b34c086c729e28e935cbc3430),
[NVIDIA LPS0 PR656](https://github.com/NVIDIA/NV-Kernels/pull/656),
[Omarchy P16 timing PR1958](https://github.com/omacom/omarchy-pkgs/pull/1958),
[7.3 NVMe parameter](https://github.com/torvalds/linux/blob/v7.3/drivers/nvme/host/pci.c),
[7.3 NVMe quirk names](https://github.com/torvalds/linux/blob/v7.3/drivers/nvme/host/nvme.h),
[reviewed kernel recipe](https://github.com/omacom/omarchy-pkgs/blob/3c267816022a47d8240ef8e081ef3c763d913305/pkgbuilds/linux-omarchy-aarch64/PKGBUILD).
