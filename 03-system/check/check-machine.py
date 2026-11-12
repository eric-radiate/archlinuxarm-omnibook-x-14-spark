#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only identity check for the HP OmniBook X Spark.

Compares DMI, kernel, and the pinned N1X package set with pins/.
Prints a short status report. Does not write system configuration.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pins" / "machine.json").is_file():
            return parent
    raise SystemExit("pins/machine.json was not found above this script")


ROOT = repo_root()
PINS = ROOT / "pins"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return f"(unreadable: {exc.strerror or exc})"


def load_pin(name: str) -> dict:
    return json.loads((PINS / name).read_text(encoding="utf-8"))


def pacman_version(package: str) -> str | None:
    try:
        out = subprocess.run(
            ["pacman", "-Q", package],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    parts = out.stdout.split()
    return parts[1] if len(parts) >= 2 else None


def meminfo_kib(key: str) -> str:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(key + ":"):
                return line.split()[1]
    except OSError:
        pass
    return ""


def gib(kib: str) -> str:
    try:
        return f"{int(kib) / 1024 / 1024:.1f} GiB"
    except ValueError:
        return "unknown"


def main() -> int:
    machine = load_pin("machine.json")
    packages = load_pin("packages.json")
    failures: list[str] = []

    dmi = {
        "product_name": read_text(Path("/sys/class/dmi/id/product_name")),
        "board_vendor": read_text(Path("/sys/class/dmi/id/board_vendor")),
        "board_name": read_text(Path("/sys/class/dmi/id/board_name")),
        "product_sku": read_text(Path("/sys/class/dmi/id/product_sku")),
        "bios_vendor": read_text(Path("/sys/class/dmi/id/bios_vendor")),
        "bios_version": read_text(Path("/sys/class/dmi/id/bios_version")),
        "bios_date": read_text(Path("/sys/class/dmi/id/bios_date")),
    }
    print("HP OmniBook X Spark check")
    for key, expected in dmi.items():
        wanted = machine[key]
        mark = "ok" if expected == wanted else "DIFF"
        print(f"  {mark:4} {key}: {expected}")
        if expected != wanted:
            failures.append(f"{key} is {expected!r}, pin is {wanted!r}")

    kernel = read_text(Path("/proc/sys/kernel/osrelease"))
    mark = "ok" if kernel == machine["kernel_release"] else "DIFF"
    print(f"  {mark:4} kernel: {kernel}")
    if kernel != machine["kernel_release"]:
        failures.append(f"kernel is {kernel!r}")

    print("packages:")
    for name, wanted in packages["packages"].items():
        got = pacman_version(name)
        mark = "ok" if got == wanted else "DIFF"
        print(f"  {mark:4} {name} {got or '(not installed)'}")
        if got != wanted:
            failures.append(f"{name} is {got!r}, pin is {wanted!r}")

    supplies = sorted(p.name for p in Path("/sys/class/power_supply").glob("*")) if Path("/sys/class/power_supply").is_dir() else []
    print("power supplies:", " ".join(supplies) or "(none)")
    print("MemTotal:", gib(meminfo_kib("MemTotal")))
    params = Path("/proc/driver/nvidia/params")
    mode = ""
    if params.is_file():
        for line in params.read_text(encoding="utf-8", errors="replace").splitlines():
            if "CoherentGPUMemoryMode" in line:
                mode = line.strip()
                break
    print("coherent mode:", mode or "(unread)")

    if failures:
        print(f"{len(failures)} pin mismatch(es).")
        return 1
    print("Identity and package pins match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
