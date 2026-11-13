# Arch Linux ARM on the HP OmniBook X (14-ks000)

Device enablement for Arch Linux ARM on the HP OmniBook X Laptop 14-ks000:
NVIDIA N1X, AArch64, board 8F22, SKU E4KN9AV, BIOS F.05. The repository name
is `archlinuxarm-omnibook-x-14-spark` so this N1X model is distinct from the
other OmniBook X 14 laptops.

The N1X kernel, NVIDIA modules, power-profile daemon, and the Archinstall
adapter come from Josephine Pfeiffer's ASUS ProArt P16 project. This
repository is the HP layer on top of that work: a battery ACPI override built
from the laptop's own tables, speaker routing for this SoundWire topology, and
the device-policy files the ASUS package does not apply on this board.

This tree does not build a USB image and does not partition a disk. It adjusts
a system that already boots with the pinned N1X packages. Read
[Limits and known issues](docs/limits.md) before changing a machine.

The notes describe one 14-ks000 on BIOS F.05. Package versions in `pins/`
were taken from that system.

| Hardware / feature | Status on the reference Arch system |
| --- | --- |
| NVIDIA display and unified memory | Running with the pinned stack; driver memory mode selectable |
| Battery, AC and thermal methods | Tested minimal, exact-hash local DSDT fix |
| Speakers / microphone | HP routes work; genuine HP speaker-protection tuning is missing |
| Keyboard, touchpad, Wi-Fi, Bluetooth, UVC camera | Observed on the reference system; see hardware notes |
| Keyboard backlight | Firmware F10 key; no Linux LED control in this kernel |
| Sleep | Patched-kernel short test: about 1.18 W; sustained sleep and lid-only wake unqualified |
| Omarchy | Source/integration review only; not installed or physically tested |

Sleep needs the complete experimental kernel, LPS0, SSD and wake changes in
[Sleep](docs/sleep.md). Enabling lid policy alone does not provide low-power
sleep. An ordinary reboot into the original kernel does not activate the trial.

HP, OmniBook, ASUS, ProArt, and NVIDIA names identify the hardware and the
upstream project. This repository is not published by those companies.

## Documentation

| Page | Contents |
| --- | --- |
| [Installing](docs/install.md) | What to run on a booted system, and what a fresh install still needs |
| [Hardware](docs/hardware.md) | Board, packages, boot, and the devices this tree covers |
| [ACPI](docs/acpi.md) | The battery override, built on the machine |
| [Audio](docs/audio.md) | Speaker route for the HP SoundWire card |
| [Memory](docs/memory.md) | The shared DRAM pool and the driver mode switch |
| [Sleep](docs/sleep.md) | Tested source changes, measurements, recovery and Omarchy port gaps |
| [Limits](docs/limits.md) | Firmware pin, missing pieces, unverified behavior |
| [Upstream](docs/upstream.md) | The ASUS project this tree builds on |
| [Licensing](docs/legal.md) | License scope, retained notices and redistribution limits |
| [Desktop bar](docs/desktop.md) | Optional Waybar, panel, and presence config |

## Layout

The numbered stages follow the upstream tree. Each directory here is a piece
this repository actually ships. Upstream stages that build the kernel, the
NVIDIA modules, Archinstall, and the USB image stay in that project.

| Directory | Contents |
| --- | --- |
| `01-platform/acpi/` | Battery override built from this machine's tables, the table collector, and the patcher test |
| `01-platform/sleep/` | Experimental sleep kernel patches, GPL companion, build/trial helpers and failure tests |
| `02-drivers/nvidia-display/` | Coherent GPU memory mode switch. No NVIDIA modules |
| `02-drivers/soundwire/` | Two-amp match for the installed `soundwire-mtk` machine table |
| `03-system/input-audio/` | Speaker route, microphone route, PipeWire udev rule, and user services |
| `03-system/policy/` | Camera modprobe override, logind suspend policy, and the Wi-Fi regulatory database |
| `03-system/check/` | Read-only identity check and the post-boot report |
| `04-desktop/` | Optional Waybar, SwayNC, hypridle, and panel scripts |
| `pins/` | Board identity, package/source hashes, signature records and sanitized sleep evidence |
| `tests/` | Host-only regression, syntax and provenance checks used by CI |
| `docs/` | The pages above |

Image assembly and the base installer remain upstream. The experimental sleep
build is a separate source recipe, not a fresh-install image builder.

Generate ACPI output on the laptop. Compiled tables, firmware blobs, and disk
images stay out of git. See `.gitignore`.

## Check a running system

```bash
python3 03-system/check/check-machine.py
```

The checker compares DMI, the kernel release, and the pinned packages. It
prints power supplies and `MemTotal` for context. It does not write
configuration. A mismatch exits 1.

Run host-only validation with `bash tests/check.sh`. It exercises rollback,
override conflicts and LPS0 failure recovery without changing the machine.
After an intentional source or notice edit, review it and refresh the recorded
hashes with `python3 tests/update_source_hashes.py` before running checks.

## License

Independent helpers, unit files and documentation are MIT under [LICENSE](LICENSE).
The sleep companion and kernel patches retain GPL-2.0-only. See [NOTICE](NOTICE)
and [LICENSES](LICENSES) for the exact scope and full upstream notices, including
Josephine Pfeiffer's MIT copyright and permission notice.

Upstream material keeps its own license. NVIDIA's open kernel modules are dual
MIT/GPL-2.0. NVIDIA's userspace
driver is NVIDIA's license. `h7607a-hardware`, `power-profiles-daemon-n1x`,
and the Arch Linux ARM packages come from their publishers. ACPI tables dumped
from the firmware, and any override compiled from them, are not in this
repository.
