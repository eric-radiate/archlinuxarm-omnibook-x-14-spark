# Hardware

| Field | Value |
| --- | --- |
| Product | HP OmniBook X Laptop 14-ks000 |
| Board | HP 8F22 |
| SKU | E4KN9AV |
| Firmware | AMI F.05, 09/29/2026 |
| SoC / GPU | NVIDIA RTX Spark N1X, 6144 CUDA cores, PCI `10de:2e03` subsystem `103c:8f22` |
| Panel | 2880x1800 at 120 Hz on the reference machine |
| Wi-Fi | MediaTek MT7925, PCI `14c3:7925` subsystem `103c:8c94` |
| Bluetooth | MediaTek USB `0e8d:8c38` |
| Audio | SoundWire card `HP-HPOmniBookXLaptop14_ks000-8F22` (`mt8901-soundwire`), CS42L43 and two CS35L56 amplifiers |
| Camera | HP 5MP Camera, USB `30c9:00fb` |
| Keyboard | I2C HID ITE `048D:8987` (`MKB0001:00`), bound to `hid-lenovo` |

Other I2C HID devices enumerated on the reference machine: ELAN `04F3:4664`
(`ELAN2513:00`) and Synaptics `06CB:CFC5` (`SYNA3536:00`). This tree does not
configure them.

## Packages

The reference install uses the upstream tuple in `pins/packages.json`:

| Package | Version |
| --- | --- |
| `linux-n1x-nvidia-bin` | 7.0.0.1022.23-3 |
| `nvidia-n1x-modules` | 615.78.08-4 |
| `nvidia-utils` | 615.78.08-1 |
| `nvidia-n1x-userspace-fix` | 615.78.08-1 |
| `h7607a-hardware` | 1.0.0-4 |
| `power-profiles-daemon-n1x` | 0.30.nvidia3001c25-2 |
| `linux-firmware-mediatek` | 20260916-1 |
| `linux-firmware-cirrus` | 20260916-1 |
| `linux-firmware-whence` | 20260916-1 |

Kernel release: `7.0.0-1022-nvidia`. Driver: NVIDIA UNIX Open Kernel Module
aarch64 615.78.08.

`/etc/pacman.conf` on the reference machine holds that set:

```
IgnorePkg = h7607a-hardware linux-firmware-cirrus linux-firmware-mediatek linux-firmware-whence linux-n1x-nvidia-bin nvidia-n1x-modules nvidia-n1x-userspace-fix nvidia-utils power-profiles-daemon-n1x
```

## Boot

Boot is UEFI on AArch64, Secure Boot off, systemd-boot, with the upstream
EDK2 shell entry. The reference entry is `h7607a.conf`. The kernel command
line used for hardware bring-up, apart from the root device, is:

```
rw rootwait console=tty0 acpi=nospcr thermal.tzp=100 mem_sleep_default=s2idle initcall_blacklist=simpledrm_platform_driver_init fbcon=font:TER16x32 log_buf_len=4M loglevel=3
```

The reference root is ext4. `zswap.enabled=0` is set on that install.

The `acpi_override` mkinitcpio hook shipped with the N1X kernel package loads
every `*.aml` file from `/etc/initcpio/acpi_override/` and
`/usr/lib/initcpio/acpi_override/` into the early initramfs. The battery
script uses that hook.

## What works on the reference machine

- Display at 2880x1800, 120 Hz, through the NVIDIA driver.
- Wi-Fi through `linux-firmware-mediatek`.
- CUDA initialization with driver 615.78.08. `nvidia-smi` reports memory size
  as N/A because the GPU uses the shared DRAM pool.
- CPPC initialization and `power-profiles-daemon-n1x` from the upstream package.
- Battery and AC sysfs (`BAT0`, `ADP1`) after the HP DSDT override.
- Internal camera after the `uvcvideo` blacklist is cleared.
- Bluetooth with BlueZ after `bluez` and `bluez-utils` are installed.
- Speaker playback after the route in [Audio](audio.md). The amps still need
  HP tuning firmware; see [Limits](limits.md).
