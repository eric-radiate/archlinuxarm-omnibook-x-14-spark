# Installing

These steps adjust a machine that already boots Arch Linux ARM with the pinned
N1X packages in `pins/packages.json`. They do not create partitions, copy a
root filesystem, or write a USB image.

The upstream installer in
[archlinuxarm-proart-p16](https://github.com/pfeifferj/archlinuxarm-proart-p16)
checks for the ASUS ProArt P16 and firmware H7607BA.300, then installs an
ACPI archive built from that laptop. On this HP, install the same package
tuple and command line, and use the scripts in this tree for the board.

Confirm the machine first:

```bash
python3 03-system/check/check-machine.py
```

Run package and initramfs steps as root. Run the speaker service as the
desktop user.

## 1. Hold the package tuple

Put the `IgnorePkg` line from [Hardware](hardware.md) in `/etc/pacman.conf`
before the next full upgrade. `nvidia-n1x-modules` requires the matching
`nvidia-utils` and `linux-n1x-nvidia-bin` versions.

## 2. Battery

Keep a boot entry whose initramfs does not contain the override. Then, from
this repository, on AC power:

```bash
sudo bash 01-platform/acpi/fix-hp-battery.sh
```

The script applies the exact-hash, length-preserving AML fix to the local
DSDT. It checks both override directories, reuses an identical existing table,
keeps recovery copies and rebuilds only the pinned preset. It does not require
iasl or a firmware download. See [ACPI](acpi.md) for checks and concrete recovery
steps before rebooting.

## 3. Camera

`h7607a-hardware` blacklists `uvcvideo` from
`/usr/lib/modprobe.d/60-h7607a-no-camera.conf`. A file with the same name
under `/etc/modprobe.d` replaces it:

```bash
sudo install -D -m 0644 03-system/policy/modprobe.d/60-h7607a-no-camera.conf \
  /etc/modprobe.d/60-h7607a-no-camera.conf
sudo modprobe uvcvideo
```

The internal camera is USB `30c9:00fb`.

## 4. Session packages and groups

```bash
sudo pacman -S --needed bluez bluez-utils alsa-utils rtkit
sudo systemctl enable --now bluetooth.service
sudo systemctl start rtkit-daemon.service
# Run from the intended desktop user's shell, before entering a root shell.
desktop_user=$(id -un)
sudo usermod -aG audio,video,lp,input "$desktop_user"
sudo bash 03-system/policy/install-wireless-regdb.sh
```

Log in again so the new groups apply. `install-wireless-regdb.sh` installs
`wireless-regdb` and `iw` and leaves the country unset. The Bluetooth
controller is USB `0e8d:8c38`.

## 5. Speakers and microphone

```bash
sudo bash 02-drivers/soundwire/match-two-amps.sh
sudo bash 03-system/input-audio/fix-hp-speakers.sh
```

Reboot after the amp match. Then follow [Audio](audio.md) for
`hp-audio-route.py` and, if you want the internal microphone, for
`hp-microphone.py`.

The route fixes do not install the CS35L56 OEM tuning. Matching files have
been identified in HP recovery media, but have not been loaded or qualified
on Linux. Read [Speaker tuning](speaker-tuning.md) for the source, per-amp
mapping, licensing limits and checks to perform on the HP before installation.

## 6. After reboot

```bash
bash 03-system/check/check-after-boot.sh
```

`01-platform/acpi/collect-acpi.sh DEST_DIR` copies DSDT, SSDT, and FACP tables for
inspection. It skips MSDM. Point `DEST_DIR` outside this repository.

## 7. Experimental sleep qualification

The upstream package ignores lid and suspend-key events. The original kernel
used around 14–16 W in our sleep tests. **Do not enable automatic lid suspend
as a stand-alone fix.** Review [Sleep](sleep.md), build/boot the complete trial,
and qualify power and wake on a ventilated desk first.

Only after qualification, the policy file below enables lid/suspend-key
handling; it provides no kernel or firmware power fix:

```bash
sudo install -D -m 0644 03-system/policy/logind/70-hp-enable-sleep.conf \
  /etc/systemd/logind.conf.d/70-hp-enable-sleep.conf
```

Leave the running logind alone. Restarting it drops DRM session control for
the live compositor. The file is read on a later boot. Verify the intended
kernel and all trial components after that boot. See [Limits](limits.md).

## 8. Driver memory mode

Optional. This does not resize the firmware reservation.

```bash
bash 02-drivers/nvidia-display/vram-mode.sh
sudo bash 02-drivers/nvidia-display/vram-mode.sh shared
```

`dedicated` returns to driver-managed mode. Reboot to apply. See
[Memory](memory.md).

## Desktop bar

Optional. This installs Waybar and the panel helpers from `04-desktop/`. It is
separate from the hardware steps above, and it does not use `iio-hyprland`.

```bash
bash 04-desktop/install-hyprbar.sh
```

See [Desktop bar](desktop.md).

## Fresh install

A from-scratch install still needs an Arch Linux ARM userland, the pinned N1X
kernel and NVIDIA packages, systemd-boot, and the upstream command line in
[Hardware](hardware.md). This repository does not perform that install. After
the system boots, the steps above are the HP layer.
