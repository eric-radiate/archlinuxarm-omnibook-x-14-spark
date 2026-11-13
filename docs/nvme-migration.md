# Preparing for a replacement SSD

The measured sleep result applies to Ramaxel `RPEYJ1TBMNV1QWX`, firmware
HPS1, PCI `1e81:6d14`. Its `simple_suspend` quirk is selected by that exact
vendor/device ID. The companion also checks the current storage link. A
future SN8100 or another drive needs a separate power/wake test; do not copy
the Ramaxel quirk to its PCI identity without evidence.

`01-platform/sleep/prepare-nvme-migration.py` is preparation for an **offline
clone**, not a cloning tool. Its default is a read-only check:

```bash
python3 01-platform/sleep/prepare-nvme-migration.py --check
```

The report contains local disk serials, UUIDs and boot details; keep it private.
No preparation is needed just to continue using the current SSD.

## Before the actual clone

When the replacement and cloning process have been identified, run preparation
on the original Ramaxel installation, with `/boot` mounted and no clone with
duplicate filesystem UUIDs attached:

```bash
sudo python3 01-platform/sleep/prepare-nvme-migration.py --prepare
```

It verifies the reference HP and source SSD, refuses a pending one-shot trial,
backs up and hash-checks all boot files, saves relevant configuration and
records every changed file under `/var/backups/hp-nvme-migration/`. It masks
sleep/hibernate targets and adds conditions to the known sleep-companion
services. It does not clone, format, resize, rewrite boot entries, alter the
initramfs, or change audio settings. It does not unload the live companion.

After preparation, use an offline full-disk clone that preserves the intended
boot/root identifiers. Choose actual source and destination devices only
after identifying both physically; this helper does not pick them. Shut down
for the swap. Avoid booting with two copies of the same filesystem UUID.

The cloned system retains its audio and matching kernel setup, with sleep
intentionally paused. Run `--check` after swapping. Requalify the new SSD's
power and wake behavior and adapt the storage policy before removing the
guard. This procedure does not promise automatic low-power SN8100 suspend.

## Cancel while the original SSD is still installed

Use the backup path printed by preparation:

```bash
sudo python3 01-platform/sleep/prepare-nvme-migration.py --restore /var/backups/hp-nvme-migration/TIMESTAMP
```

Restore checks the original SSD identity and that the prepared files have not
been changed since. It preserves pre-existing masks and refuses to re-enable
the old policy on a replacement drive. Temporary-filesystem tests cover
prepare/cancel, failed activation rollback, pending trials, custom targets
and a changed SSD. The helper has not been used for a physical SSD swap.
