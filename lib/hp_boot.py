#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared guards and file rollback for the pinned Arch N1X installers."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

RELEASE = "7.0.0-1022-nvidia"
IMAGE = Path("/boot/initramfs-linux-n1x.img")
PRESET = Path("/etc/mkinitcpio.d/linux-n1x-nvidia-bin.preset")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guard():
    require(os.geteuid() == 0, "Run with sudo.")
    for key, value in (("product_name", "HP OmniBook X Laptop 14-ks000"),
                       ("board_name", "8F22"), ("bios_version", "F.05")):
        require(Path("/sys/class/dmi/id", key).read_text().strip() == value,
                f"Unsupported {key}; this installer is pinned to HP 8F22/F.05.")
    require(os.uname().release == RELEASE, "Unsupported kernel release.")
    require("#23~24.04.1" in os.uname().version,
            "Use the original pinned kernel for this installer, not a sleep-trial kernel.")
    require("hp_spark_" not in Path("/proc/cmdline").read_text(),
            "Trial module mounts must not be used to rebuild the original boot image.")
    expected = {"ALL_kver='/boot/vmlinuz-linux-n1x'", "PRESETS=('default')",
                "default_image='/boot/initramfs-linux-n1x.img'"}
    lines = {s.strip() for s in PRESET.read_text().splitlines()
             if s.strip() and not s.lstrip().startswith("#")}
    require(lines == expected, "Unexpected mkinitcpio preset; inspect manually.")
    require(os.path.ismount("/boot") and IMAGE.is_file(),
            "Mount /boot and retain a working initramfs before proceeding.")
    require(not IMAGE.is_symlink(), "Unexpected initramfs symlink.")
    require(shutil.disk_usage("/boot").free > IMAGE.stat().st_size * 2 + 64 * 1024**2,
            "Insufficient /boot space for rebuild and recovery.")


def atomic_copy(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".hp-restore-", dir=target.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        with open(temporary, "rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore(directory):
    directory = Path(directory)
    require(os.geteuid() == 0 and directory.stat().st_uid == 0,
            "Recovery requires root and a root-owned backup.")
    _restore_files(directory)


def _restore_files(directory):
    receipt = json.loads((directory / "files.json").read_text())
    for record in receipt:
        if record["existed"]:
            require(sha256(directory / record["backup"]) == record["sha256"],
                    "Backup checksum mismatch; refusing recovery.")
    for record in receipt:
        target = Path(record["target"])
        if record["existed"]:
            atomic_copy(directory / record["backup"], target)
        else:
            target.unlink(missing_ok=True)


@contextmanager
def transaction(paths, base=Path("/var/lib/hp-omnibook/transactions")):
    """Save source files and the old image; restore even a partial build."""
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(
        prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=base))
    directory.chmod(0o700)
    paths = list(dict.fromkeys(Path(p) for p in paths))
    needed = sum(p.stat().st_size for p in paths if p.is_file())
    require(shutil.disk_usage(base).free > needed + 64 * 1024**2,
            "Insufficient space for recovery copies.")
    records = []
    for number, path in enumerate(paths):
        require(not path.is_symlink(), f"Refusing symlink: {path}")
        require(not path.exists() or path.is_file(), f"Not a regular file: {path}")
        record = {"target": str(path), "existed": path.exists()}
        if path.exists():
            saved = directory / str(number)
            shutil.copy2(path, saved)
            record.update(backup=str(number), sha256=sha256(saved))
        records.append(record)
    (directory / "files.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Recovery copies: {directory}", flush=True)
    try:
        yield directory
    except BaseException:
        _restore_files(directory)
        print("Restored previous files and initramfs; backup retained.", flush=True)
        raise


def rebuild():
    subprocess.run(["mkinitcpio", "-p", "linux-n1x-nvidia-bin"], check=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["guard"]:
        guard()
    else:
        require(len(sys.argv) == 3 and sys.argv[1] == "restore",
                "Usage: sudo python3 lib/hp_boot.py restore BACKUP_DIRECTORY")
        restore(sys.argv[2])
        print("Restored saved files. No rebuild or reboot was performed.")
