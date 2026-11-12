# Memory

The RTX Spark N1X in this laptop has one DRAM pool. There is no separate VRAM
chip. `nvidia-smi` reports memory size as N/A.

Two settings show up in boot logs and in the driver, and they are different:

- The firmware reservation is how much of the pool the firmware keeps out of
  the OS memory map. It is visible on the kernel `Memory:` line
  (`present` and `reserved`) before `nvidia.ko` loads.
- `NVreg_CoherentGPUMemoryMode` selects how the NVIDIA driver manages the
  memory it can see. `driver` is driver-managed coherent GPU memory.
  `numa` is NUMA mode.

`02-drivers/nvidia-display/vram-mode.sh` writes only the module option:

| Command | Module option |
| --- | --- |
| `sudo bash 02-drivers/nvidia-display/vram-mode.sh dedicated` | `NVreg_CoherentGPUMemoryMode=driver` and `uvm_disable_sam_migration=1` |
| `sudo bash 02-drivers/nvidia-display/vram-mode.sh shared` | `NVreg_CoherentGPUMemoryMode=numa` and `uvm_disable_sam_migration=0` |

The file is `/etc/modprobe.d/hp-omnibook-vram.conf`. The script rebuilds the
initramfs with `mkinitcpio -P` and applies the mode on the next boot. With no
arguments it prints the running mode, the saved mode, and `MemTotal`.

`shared` does not move the firmware reservation. Check the kernel `Memory:`
line and `MemTotal` after reboot before treating the pool size as changed.

One boot of a 14-ks000 reported about 61 GiB to Linux and to CUDA, with about
66 GiB reserved from about 128 GiB present. A later boot of that machine
reported about 120 GiB `MemTotal` while `CoherentGPUMemoryMode` was `numa`.
This repository does not include a tool that changes the firmware reservation.
On Windows the NVIDIA app reservation slider is the documented size control.
