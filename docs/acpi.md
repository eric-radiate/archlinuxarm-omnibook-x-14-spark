# Battery ACPI override and recovery

HP F.05's `BAT0._STA` calls `\\_SB.FFA0.RBUF`. That method creates an unused
400-bit DATA field at bit 208 in a 64-byte buffer. It exceeds the buffer and
aborts shared battery, AC-status and thermal methods with
`AE_AML_BUFFER_LIMIT`.

The hardware-tested fix removes that unused CreateField using 15 AML Noops.
It preserves every table offset and all sleep methods, increments the OEM
revision, and recalculates the ACPI checksum. It does not enlarge the buffer
or recompile the firmware table. The old ASL-widening experiment and its
synthetic fixture remain for reference in `fix-hp-battery.py`; the installer
does not use that experiment.

`battery_aml.py` accepts only these complete DSDT SHA256 values:

| Input | SHA256 |
| --- | --- |
| Original F.05 | `66e0fc9c32649797f117e7f13cff321808075f0704223ca29b8e2f717654eec0` |
| Tested override | `e4971160feb9cbc27b652a5f9fa10979834886ecfba06ed36ff5c2749c1a1e4e` |

Matching the board and BIOS string alone is insufficient: a different table
hash is refused. No table is distributed or written to firmware flash.

## Install

Keep a bootable Arch ARM USB or a separately copied kernel/initramfs boot
entry available. A fallback rebuilt with the same override hook is not an
independent recovery image. Run on AC power from the repository root:

```bash
sudo bash 01-platform/acpi/fix-hp-battery.sh
```

The installer requires the pinned Arch preset and upstream `acpi_override`
hook. It checks **both** `/etc/initcpio/acpi_override/` and
`/usr/lib/initcpio/acpi_override/`. It refuses unrelated or multiple AML files
before changing anything. One existing override with the exact tested hash
is reused, whatever its filename; another is not stacked beside it.

The installer saves each original file, the previous initramfs, hashes and
existence flags in a new root-only directory under
`/var/lib/hp-omnibook/transactions/`. It prints that directory, adds the hook
to the recognized upstream HOOKS array, and rebuilds only the pinned preset.
It restores saved files and the old image if the operation fails. Previous
backup directories are retained.

After reboot, confirm BAT0 and ADP1 exist under `/sys/class/power_supply` and
inspect the kernel log for Table Upgrade and any `AE_AML_BUFFER_LIMIT`.
This installer revision has fixture/read-only verification; it has not been
run through a new physical installation during this repository review.

## Recover

While Linux still runs, use the exact directory printed by the installer:

```bash
sudo python3 lib/hp_boot.py restore /var/lib/hp-omnibook/transactions/PRINTED-DIRECTORY
```

This checksum-checks backups and restores the saved configuration, override
state and original initramfs. It does not rebuild or reboot. Restore the
most recent transaction first if several operations changed the same files.

If the installed system cannot boot, boot the ARM recovery USB, mount its
root at `/mnt`, mount its EFI/boot partition at `/mnt/boot`, and confirm the
mounts with `findmnt`. Use the actual partition identifiers from that system.
Then enter it with `arch-chroot /mnt`, change to this repository, and run the
restore command above. The saved absolute paths then refer to the installed
system. Reboot using the original entry. Do not delete all AML files or
rebuild every preset as a first recovery step.

`collect-acpi.sh DEST_DIR` saves local tables for review and skips MSDM.
Use a destination outside this repository; do not publish those dumps.
