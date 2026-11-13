# One default boot for the reference HP

On 2026-11-13 the reference machine moved from separate trials to one normal
systemd-boot entry combining the previously short-tested #25 sleep kernel
with the HP audio identity patch and locally acquired OEM files. Both amps
loaded firmware 3.13.5, tuning and calibration. Stereo playback and internal
microphone speech were confirmed. A later unplugged test used 0.046 Wh over
183.652 seconds, with 178.251 seconds actually suspended: about **0.90 W**
over the whole interval. The owner confirmed lid-only wake and stereo audio
after resume. GPU and Wi-Fi returned with no failed system units.
This is one short test; sustained/repeated sleep and transport remain
unqualified. The earlier 1.18 W result is a separate measurement.

This is systemd-boot invoking an EFI shell, not GRUB.

| Component | Combined reference layout |
| --- | --- |
| Only visible normal Linux entry | `h7607a.conf` |
| EFI shell and script | `/boot/EFI/HP-OMNIBOOK/` |
| Kernel | `/boot/vmlinuz-hp-omnibook`, #25~hp-sleep-wake1 |
| Initramfs | `/boot/initramfs-hp-omnibook.img` |
| Matching modules | `/usr/local/lib/hp-sleep-wake-kernel/root/lib/modules/7.0.0-1022-nvidia` |
| Companion | Version 0.2, rebuilt against that kernel's vmlinux |
| Persistent preset | `/etc/mkinitcpio.d/hp-omnibook.preset` |
| Archived original entry | `/boot/loader/recovery/h7607a-original.conf` |

The normal script retains all three sleep arguments:

```text
processor.hp_n1x_firmware_idle=1 hp_spark_wake_trial=1 nvme.quirks=1e81:6d14:simple_suspend
```

The marker still selects the exact matching module bind mount and companion
service. Its name does not mean this boot is a one-shot selection. The
combined default is persistent and has no pending one-shot entry.

## Prepare after a successful one-boot trial

`01-platform/sleep/prepare-combined.py` adapts the local promotion procedure.
It requires the exact HP/F.05/Ramaxel layout, an existing checked sleep payload
from `prepare-oneboot.py`, and the **original #23 kernel** while preparing.
Finish a physical short trial first, then boot the original default to prepare
the promotion. Do not enable lid sleep on that original boot.

Build the identity module and stage the private firmware using
[Speaker tuning](speaker-tuning.md). Keep the full validated sleep work bundle
and its checksums. From this repository:

```bash
sudo python3 01-platform/sleep/prepare-combined.py \
  /path/to/sleep-work \
  "$HOME/hp-audio-private/module/mt8901-acp-sdw-legacy-mach.ko" \
  "$HOME/hp-audio-private/staged/cirrus"
```

The helper checks the full installed module tree against the validated bundle,
checks the new module's source version and imported-symbol CRCs, and validates
all three local firmware hashes. It saves a verified complete `/boot` archive
and changed-file copies under `/var/backups/hp-combined-boot/`.

It builds the new initramfs on the main filesystem before touching the ESP,
then extracts it to check the battery override, HP driver, firmware and module
bind hook. It retains the original kernel and EFI files, archives the separate
trial entries outside the active menu, and selects the existing default entry.
Unused trial images are removed only after verification and backup. It never
reboots. Build, image-verification and boot-variable failures have temporary-
filesystem rollback tests. The portable input wrapper has not undergone a
second full physical installation.

After a chosen reboot, run `check-trial-boot.py` for sleep admission and
`03-system/check/check-hp-audio.py` for audio. Verify actual stereo playback,
microphone capture, then unplugged sleep and wake on a ventilated desk.

## Preserve the kernel/module pair during maintenance

The combined preset explicitly uses the private module root:

```bash
ALL_config='/usr/local/lib/hp-sleep-wake-kernel/mkinitcpio.conf'
ALL_kver='/boot/vmlinuz-hp-omnibook'
PRESETS=('default')
default_image='/boot/initramfs-hp-omnibook.img'
default_options='-r /usr/local/lib/hp-sleep-wake-kernel/root'
```

The original preset is archived as
`/usr/local/lib/hp-sleep-wake-kernel/original-stock.preset` so `mkinitcpio -P`
does not mix the active #25 module mount with the frozen #23 recovery image.
The original-kernel battery, binary SoundWire and VRAM installers deliberately
refuse to rebuild while this trial module tree is active. Further changes
need a matching combined-image transaction, backup and embedded-file checks.

Do not erase the module payload while it is bind-mounted. Back up the current
combined initramfs before a later rebuild. The firmware filenames, including
`-spkid0`, must remain in the combined mkinitcpio configuration's `FILES`.

## Recovery

The original `/boot/vmlinuz-linux-n1x`, `/boot/initramfs-linux-n1x.img` and
`/boot/EFI/H7607A/` files are retained. The recovery directory is outside the
normal menu. In an EFI shell on the boot filesystem, restore the original
entry with:

```text
cp \loader\recovery\h7607a-original.conf \loader\entries\h7607a.conf
```

Restart afterward. That entry restores the original kernel, whose sleep is
not qualified. Power off for transport until the combined setup is restored.
For file rollback from a working environment, use the root-owned transaction
directory printed by the helper with `lib/hp_boot.py restore BACKUP_DIRECTORY`.
Full archives and per-file checksums remain in that directory.
