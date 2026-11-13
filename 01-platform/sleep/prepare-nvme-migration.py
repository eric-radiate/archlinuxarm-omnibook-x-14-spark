#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare this HP's existing installation for an offline NVMe clone.

Default --check is read-only. --prepare saves verified backups and pauses
sleep/hibernate plus the Ramaxel sleep companion. No disk is cloned, formatted
or resized. Boot entries, initramfs files and audio configuration are preserved.
--restore BACKUP cancels preparation only while the original SSD is installed.
After replacing the SSD, keep the guard until its sleep behavior is qualified.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path("/")
BACKUPS = "/var/backups/hp-nvme-migration"
STATE = "/var/lib/hp-nvme-migration/prepared.json"
TARGETS = ("sleep.target", "suspend.target", "hibernate.target",
           "hybrid-sleep.target", "suspend-then-hibernate.target")
SERVICES = ("hp-sleep-kernel-trial.service", "hp-sleep-wake-kernel-trial.service")
DROPIN = "99-hp-nvme-migration.conf"


def path(name):
    return ROOT / name.lstrip("/")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(name):
    try:
        return path(name).read_text().strip()
    except OSError:
        return None


def digest(file):
    with Path(file).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args):
    return subprocess.run(args, text=True, capture_output=True, check=True).stdout.strip()


def efivar(name):
    for file in path("/sys/firmware/efi/efivars").glob(name + "-*"):
        try:
            return file.read_bytes()[4:].decode("utf-16-le").rstrip("\0")
        except OSError:
            return "unreadable"
    return None


def report():
    source = run(["findmnt", "-n", "-o", "SOURCE", "--target", "/"])
    source = source.split("[", 1)[0]
    disk = run(["lsblk", "-ndo", "PKNAME", source])
    require(bool(re.fullmatch(r"nvme[0-9]+n[0-9]+", disk)),
            "The running root filesystem is not directly on an NVMe partition; review manually.")
    controller = (path("/sys/class/block") / disk / "device").resolve().name
    require(bool(re.fullmatch(r"nvme[0-9]+", controller)), "Cannot identify the root NVMe controller.")
    prefix = "/sys/class/nvme/" + controller
    ssd = {key: read(prefix + "/" + filename) for key, filename in
           (("model", "model"), ("serial", "serial"), ("firmware", "firmware_rev"),
            ("vendor", "device/vendor"), ("device", "device/device"))}
    block = json.loads(run(["lsblk", "--json", "-p", "-b", "-o",
                            "NAME,TYPE,SIZE,FSTYPE,UUID,PARTUUID,MODEL,MOUNTPOINTS"]))
    uuids = {}
    def visit(nodes):
        for item in nodes:
            if item.get("uuid"):
                uuids.setdefault(item["uuid"], []).append(item["name"])
            visit(item.get("children", []))
    visit(block["blockdevices"])
    return {"recorded_utc": datetime.now(timezone.utc).isoformat(),
            "dmi": {key: read("/sys/class/dmi/id/" + key)
                    for key in ("sys_vendor", "product_name", "board_name", "bios_version")},
            "root_source": source, "root_disk": "/dev/" + disk, "ssd": ssd,
            "kernel_release": os.uname().release, "kernel_version": os.uname().version,
            "command_line": read("/proc/cmdline"), "block_devices": block,
            "duplicate_filesystem_uuids": {k: v for k, v in uuids.items() if len(v) > 1},
            "boot": {name: efivar(name) for name in
                     ("LoaderInfo", "LoaderEntryDefault", "LoaderEntrySelected", "LoaderEntryOneShot")},
            "migration_prepared": path(STATE).is_file()}


def snapshot(file, backup, number):
    record = {"target": str(file.relative_to(ROOT))}
    if file.is_symlink():
        record.update(kind="symlink", link=os.readlink(file))
    elif file.is_file():
        saved = backup / ("file-" + str(number))
        shutil.copy2(file, saved)
        record.update(kind="file", saved=saved.name, sha256=digest(saved),
                      mode=stat.S_IMODE(file.stat().st_mode))
    else:
        require(not file.exists(), f"Unexpected file type: {file}")
        record["kind"] = "absent"
    return record


def current(file):
    if file.is_symlink():
        return {"kind": "symlink", "link": os.readlink(file)}
    if file.is_file():
        return {"kind": "file", "sha256": digest(file)}
    require(not file.exists(), f"Unexpected file type: {file}")
    return {"kind": "absent"}


def atomic_write(file, data, mode=0o644):
    file.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".nvme-migration-", dir=file.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, file)
    finally:
        Path(temporary).unlink(missing_ok=True)


def restore_files(backup, records):
    for record in records:
        if record["kind"] == "file":
            require(digest(backup / record["saved"]) == record["sha256"],
                    "A backup checksum differs; no restore attempted.")
    for record in reversed(records):
        target = path("/" + record["target"])
        if record["kind"] == "absent":
            target.unlink(missing_ok=True)
        elif record["kind"] == "symlink":
            target.unlink(missing_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(record["link"])
        else:
            atomic_write(target, (backup / record["saved"]).read_bytes(), record["mode"])


def archive_boot(backup):
    boot = path("/boot")
    require(boot.is_dir() and any(boot.iterdir()), "The mounted /boot is empty.")
    files = [p for p in boot.rglob("*") if p.is_file() and not p.is_symlink()]
    needed = sum(p.stat().st_size for p in files)
    require(shutil.disk_usage(backup).free > needed + 128 * 1024**2,
            "Insufficient space for the complete boot backup.")
    manifest = {str(p.relative_to(ROOT)): digest(p) for p in files}
    archive = backup / "boot.tar"
    with tarfile.open(archive, "w", dereference=False) as out:
        out.add(boot, arcname="boot")
    with tarfile.open(archive) as saved:
        for name, expected in manifest.items():
            with saved.extractfile(name) as stream:
                require(hashlib.file_digest(stream, "sha256").hexdigest() == expected,
                        "Boot archive verification failed.")
    return manifest


def prepare(info):
    require(info["dmi"]["sys_vendor"] == "HP" and
            info["dmi"]["product_name"] == "HP OmniBook X Laptop 14-ks000" and
            info["dmi"]["board_name"] == "8F22", "This script is scoped to the HP 8F22.")
    ssd = info["ssd"]
    require(ssd["vendor"] == "0x1e81" and ssd["device"] == "0x6d14" and
            ssd["model"] == "RPEYJ1TBMNV1QWX" and bool(ssd["serial"]),
            "Preparation must run on the original Ramaxel installation. Use --check after replacing it.")
    require(not info["boot"]["LoaderEntryOneShot"],
            "A one-boot trial is pending. Finish or cancel that trial before preparing a clone.")
    require(not info["duplicate_filesystem_uuids"],
            "Duplicate filesystem UUIDs are attached. Disconnect the clone during preparation.")
    require(not path(STATE).exists(), "Migration is already prepared; use --check to inspect it.")
    require(os.path.ismount(path("/boot")), "Mount the real EFI/boot partition first.")
    # Refuse newly introduced autoload paths that this script cannot neutralize.
    for base in ("/etc/modules-load.d", "/etc/modprobe.d", "/etc/mkinitcpio.conf.d"):
        for file in path(base).glob("*.conf"):
            require("hp_n1x_sleep" not in file.read_text(),
                    f"An additional sleep-module autoload setting needs review: {file}")
    plan = []
    for target in TARGETS:
        file = path("/etc/systemd/system/" + target)
        require(not (file.exists() or file.is_symlink()) or
                (file.is_symlink() and os.readlink(file) == "/dev/null"),
                f"Custom target definition would be replaced: {file}")
        plan.append((file, None))
    for service in SERVICES:
        if any(path(folder + "/" + service).is_file()
               for folder in ("/etc/systemd/system", "/usr/lib/systemd/system")):
            file = path("/etc/systemd/system/" + service + ".d/" + DROPIN)
            require(not file.exists() and not file.is_symlink(), f"Already present: {file}")
            plan.append((file, ("[Unit]\nConditionPathExists=!" + STATE + "\n").encode()))
    marker = path(STATE)
    backup_base = path(BACKUPS)
    backup_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"),
                                   dir=backup_base))
    backup.chmod(0o700)
    boot_manifest = archive_boot(backup)
    # Keep configuration locally; never include personal logs/keys in a public report.
    config = backup / "configuration.tar"
    roots = [path(p) for p in ("/etc/fstab", "/etc/crypttab", "/etc/kernel/cmdline",
                               "/etc/default/grub", "/etc/mkinitcpio.conf", "/etc/mkinitcpio.d",
                               "/etc/mkinitcpio.conf.d", "/etc/modprobe.d", "/etc/modules-load.d",
                               "/etc/systemd/logind.conf.d", "/etc/systemd/sleep.conf.d")]
    with tarfile.open(config, "w", dereference=False) as saved:
        for file in roots:
            if file.exists() or file.is_symlink():
                saved.add(file, arcname=str(file.relative_to(ROOT)))
    records = [snapshot(file, backup, index) for index, (file, _) in enumerate(plan)]
    records.append(snapshot(marker, backup, len(records)))
    receipt = {"version": 1, "source": info, "changes": records,
               "boot_manifest": boot_manifest, "boot_tar_sha256": digest(backup / "boot.tar"),
               "configuration_tar_sha256": digest(config)}
    atomic_write(backup / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode(), 0o600)
    try:
        for file, data in plan:
            if data is None:
                if not file.is_symlink():
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.symlink_to("/dev/null")
            else:
                atomic_write(file, data)
        marker.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        atomic_write(marker, (json.dumps({"backup": str(backup), "source_ssd": ssd,
                                        "sleep_requalification_required": True}, indent=2) + "\n").encode(), 0o600)
        run(["systemctl", "daemon-reload"])
        for target in TARGETS:
            require(run(["systemctl", "show", "-p", "LoadState", "--value", target]) == "masked",
                    "The sleep guard was not loaded: " + target)
        require(all(digest(path("/" + name)) == value for name, value in boot_manifest.items()),
                "Boot files changed concurrently; preparation rolled back.")
        receipt["installed"] = {str(file.relative_to(ROOT)): current(file)
                                for file, _ in plan}
        receipt["installed"][str(marker.relative_to(ROOT))] = current(marker)
        atomic_write(backup / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode(), 0o600)
        os.sync()
    except BaseException:
        restore_files(backup, records)
        run(["systemctl", "daemon-reload"])
        raise
    print("Preparation complete. Verified backup:", backup)
    print("Boot files, kernel modules, initramfs and audio settings were preserved.")
    print("Sleep and hibernation are paused; the old sleep companions will be skipped on the next boot.")
    print("Shut down for the SSD swap/transport. Use an offline full-disk clone that preserves identifiers.")
    print("After swapping, run --check and qualify the new SSD's power/wake before removing the guard.")
    print("To cancel while the original SSD is still installed: --restore", backup)


def require_private_backup(backup):
    require(backup.stat().st_uid == 0 and not backup.stat().st_mode & 0o022,
            "Restore requires a root-owned private backup.")


def restore(backup, info):
    backup = Path(backup).resolve()
    require_private_backup(backup)
    require(path(STATE).is_file() and
            json.loads(path(STATE).read_text()).get("backup")==str(backup),
            "That backup does not belong to the active migration preparation.")
    receipt = json.loads((backup / "receipt.json").read_text())
    original = receipt["source"]["ssd"]
    require(all(info["ssd"].get(key) == original.get(key) for key in
                ("serial", "model", "vendor", "device")),
            "The SSD has changed. Keep the sleep guard; review the replacement before re-enabling sleep.")
    allowed = {"etc/systemd/system/" + target for target in TARGETS}
    allowed.update("etc/systemd/system/" + service + ".d/" + DROPIN for service in SERVICES)
    allowed.add(STATE.lstrip("/"))
    require({row["target"] for row in receipt["changes"]} <= allowed, "Unexpected restore targets.")
    for name, expected in receipt.get("installed", {}).items():
        require(current(path("/" + name)) == expected,
                "A prepared file was subsequently changed; refusing to overwrite it: " + name)
    restore_files(backup, receipt["changes"])
    run(["systemctl", "daemon-reload"])
    os.sync()
    print("Migration guards restored to their previous state. Boot/audio files were not rewritten.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="read-only inventory (default)")
    modes.add_argument("--prepare", action="store_true", help="back up and pause sleep before offline cloning")
    modes.add_argument("--restore", metavar="BACKUP", help="cancel preparation on the original SSD")
    args = parser.parse_args()
    if args.prepare or args.restore:
        require(os.geteuid() == 0, "Run the requested change with sudo.")
    info = report()
    if args.prepare:
        prepare(info)
    elif args.restore:
        restore(args.restore, info)
    else:
        print(json.dumps(info, indent=2))
        print("\nRead-only check; no settings were changed.")
        if info["migration_prepared"]:
            print("Sleep remains paused pending replacement-drive qualification.")
        if info["boot"]["LoaderEntryOneShot"]:
            print("A one-boot trial is selected; finish it before clone preparation.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
