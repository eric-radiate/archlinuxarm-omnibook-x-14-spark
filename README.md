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
| [Limits](docs/limits.md) | Firmware pin, missing pieces, unverified behavior |
| [Upstream](docs/upstream.md) | The ASUS project this tree builds on |
| [Desktop bar](docs/desktop.md) | Optional Waybar, panel, and presence config |

## Layout

The numbered stages follow the upstream tree. Each directory here is a piece
this repository actually ships. Upstream stages that build the kernel, the
NVIDIA modules, Archinstall, and the USB image stay in that project.

| Directory | Contents |
| --- | --- |
| `01-platform/acpi/` | Battery override built from this machine's tables, the table collector, and the patcher test |
| `02-drivers/nvidia-display/` | Coherent GPU memory mode switch. No NVIDIA modules |
| `02-drivers/soundwire/` | Two-amp match for the installed `soundwire-mtk` machine table |
| `03-system/input-audio/` | Speaker route, microphone route, PipeWire udev rule, and user services |
| `03-system/policy/` | Camera modprobe override, logind suspend policy, and the Wi-Fi regulatory database |
| `03-system/check/` | Read-only identity check and the post-boot report |
| `04-desktop/` | Optional Waybar, SwayNC, hypridle, and panel scripts |
| `pins/` | Board identity and the package versions recorded on the reference machine |
| `docs/` | The pages above |

There is no `05-development/`, `06-installation/`, `07-build/`, or
`08-documentation/`. Those stages belong to the ProArt image build. This tree
does not hash-lock component manifests, because nothing here assembles an
image from them.

Generate ACPI output on the laptop. Compiled tables, firmware blobs, and disk
images stay out of git. See `.gitignore`.

## Check a running system

```bash
python3 03-system/check/check-machine.py
```

The checker compares DMI, the kernel release, and the pinned packages. It
prints power supplies and `MemTotal` for context. It does not write
configuration. A mismatch exits 1.

## License

The scripts, unit files, and documentation in this repository are under the
MIT license in `LICENSE`.

Upstream material keeps its own license. The N1X kernel and its patches are
GPL-2.0. NVIDIA's open kernel modules are dual MIT/GPL-2.0. NVIDIA's userspace
driver is NVIDIA's license. `h7607a-hardware`, `power-profiles-daemon-n1x`,
and the Arch Linux ARM packages come from their publishers. ACPI tables dumped
from the firmware, and any override compiled from them, are not in this
repository.
