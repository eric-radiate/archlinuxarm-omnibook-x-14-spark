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
  calibration for this board.
- The NPU, the fingerprint reader, and the touchscreen are not set up here.
  Internal microphone capture is the long-running route in [Audio](audio.md).
- Suspend and wake are unverified. The logind drop-in sets lid and
  suspend-key handling to suspend. That policy was saved on the reference
  machine and was not exercised with a suspend cycle.
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
  Reinstalling that module brings back the four-amp link-0 count until the
  script is run again.
- `CoherentGPUMemoryMode` selects driver memory management. It does not change
  the firmware DRAM reservation. See [Memory](memory.md). This tree does not
  write EFI memory-reservation variables.
- Held packages in `IgnorePkg` receive no updates, including security fixes,
  until a new pinned tuple is installed on purpose.
