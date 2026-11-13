# Limits and known issues

Recorded on one HP OmniBook X Laptop 14-ks000, board 8F22, SKU E4KN9AV, AMI
BIOS F.05 (09/29/2026).

The battery builder refuses any other board, product name, or BIOS version.
The speaker route refuses any other board.

## Out of scope

- There is no USB image builder and no disk partitioner in this tree.
- The upstream Archinstall adapter accepts the ASUS ProArt P16 on firmware
  H7607BA.300. A fresh OmniBook install still needs a base Arch Linux ARM
  system that already boots the pinned N1X packages.
- Firmware ACPI tables and compiled overrides are produced on the machine.
  They are not committed.
- CS35L56 speaker tuning firmware for board 8F22 is not included. On
  2026-11-02 the amps logged `FIRMWARE_MISSING` and stayed on ROM firmware
  3.4.4. The ASUS tuning files belong to the ProArt and are the wrong
  calibration for this board. On 2026-11-13 both amps loaded the matching HP
  firmware 3.13.5, separate tuning and factory calibration on the reference
  machine, and the owner confirmed stereo playback. No controlled comparison
  of loudness, bass, distortion or protection was performed. See
  [Speaker tuning](speaker-tuning.md) for the source and mapping.
- The NPU, the fingerprint reader, and the touchscreen are not set up here.
  Internal microphone capture is the long-running route in [Audio](audio.md).
- The complete experimental Arch sleep kernel passed a short low-power
  suspend/resume test (about 1.18 W over 143 seconds). Sustained sleep,
  repeated cycles, lid-only wake and Omarchy remain unqualified. The original
  kernel consumed about 14–16 W during sleep. The logind drop-in alone does
  not fix this. See [Sleep](sleep.md) for evidence and required components.
- The reference default now combines that sleep kernel with OEM audio.
  The previous short power result predates the audio firmware change; a
  physical sleep/power test with the combined audio set remains pending.
- The current sleep companion and NVMe quirk are scoped to the Ramaxel SSD.
  A replacement needs its own power/wake qualification. The
  [migration helper](nvme-migration.md) backs up the setup and pauses sleep;
  it does not clone a disk or establish SN8100 compatibility.
- The desktop bar in [Desktop](desktop.md) is optional. Installing it
  overwrites the user's Waybar, SwayNC, hypridle, and panel-helper files.
  Walk-away blanking reads the camera presence sensor directly.
  `iio-hyprland` is not part of this tree.
- Keyboard backlight has no Linux LED device. The EC toggles it from the
  keyboard. On this SKU that key is F10 once Linux is running. BIOS setup
  has a timeout (Never, 30 seconds, or 3 minutes). Kernel
  `7.0.0-1022-nvidia` has no `CONFIG_ACPI_WMI` and no `hp-wmi`.

## Known issues

- `h7607a-hardware` still ships the ASUS device policy: `uvcvideo` is
  blacklisted, capture is restricted, and logind ignores lid and suspend-key
  events. The files in `03-system/policy/` and
  `03-system/input-audio/udev/` are the HP replacements. They live under
  `/etc` so a reinstall of the package can put the ASUS policy back beside
  them. Check both paths after a package reinstall.
- The UCM files in `h7607a-hardware` describe the ASUS speaker path. Playback
  on this HP uses the route in [Audio](audio.md). A package update can mute
  the amps again until `hp-audio-route.py` runs.
- `02-drivers/soundwire/match-two-amps.sh` edits `soundwire-mtk.ko` on disk.
  It accepts only the reviewed unsigned legacy module, rebuilds and verifies
  its initramfs copy, and keeps recovery files. Reinstalling the package
  replaces the edit. Omarchy already carries a separate two-amp source
  topology; this binary workaround must not be used there.
- `CoherentGPUMemoryMode` selects driver memory management. It does not change
  the firmware DRAM reservation. See [Memory](memory.md). This tree does not
  write EFI memory-reservation variables.
- Held packages in `IgnorePkg` receive no updates, including security fixes,
  until a new pinned tuple is installed on purpose.
