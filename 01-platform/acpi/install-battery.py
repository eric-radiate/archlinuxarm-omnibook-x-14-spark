#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install the exact locally derived, hardware-tested HP F.05 battery fix."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from hp_boot import IMAGE, atomic_copy, guard, rebuild, require, sha256, transaction
from battery_aml import PATCHED, patch

OVERRIDES = (Path("/etc/initcpio/acpi_override"),
             Path("/usr/lib/initcpio/acpi_override"))


def check_overrides(directories=OVERRIDES):
    tables = [p for directory in directories for p in directory.glob("*.aml")]
    require(len(tables) <= 1, "Multiple AML overrides found; inspect both override directories.")
    if tables:
        require(not tables[0].is_symlink() and sha256(tables[0]) == PATCHED,
                f"Conflicting AML override: {tables[0]}; no files changed.")
        return tables[0]
    return Path("/etc/initcpio/acpi_override/DSDT.aml")


def hook_config(text):
    matches = list(re.finditer(r"^HOOKS=\(([^)\n]*)\)\s*$", text, re.M))
    require(len(matches) == 1, "Expected one single-line HOOKS array; inspect manually.")
    match = matches[0]
    hooks = match[1].split()
    require(hooks and hooks[0] == "h7607a-preload", "Unexpected hook order.")
    if "acpi_override" not in hooks:
        hooks.insert(1, "acpi_override")
    return text[:match.start()] + "HOOKS=(" + " ".join(hooks) + ")\n" + text[match.end():]


def main():
    guard()
    require(Path("/usr/lib/initcpio/install/acpi_override").is_file(),
            "Missing upstream acpi_override hook; this is not an Omarchy installer.")
    for dropin in Path("/etc/mkinitcpio.conf.d").glob("*.conf"):
        require(not re.search(r"^\s*HOOKS", dropin.read_text(), re.M),
                f"HOOKS override in {dropin}; inspect before proceeding.")
    target = check_overrides()
    data = patch(Path("/sys/firmware/acpi/tables/DSDT").read_bytes())
    conf = Path("/etc/mkinitcpio.conf")
    updated = hook_config(conf.read_text())
    with transaction([target, conf, IMAGE]) as saved:
        local = saved / "tested-battery.aml"
        local.write_bytes(data)
        local.chmod(0o644)
        atomic_copy(local, target)
        conf.write_text(updated)
        rebuild()
        with tempfile.TemporaryDirectory(prefix="hp-acpi-image-check-") as directory:
            subprocess.run(["lsinitcpio", "--early", "--extract", str(IMAGE)],
                           cwd=directory, check=True, stdout=subprocess.DEVNULL)
            tables = list((Path(directory) / "kernel/firmware/acpi").glob("*.aml"))
            require(len(tables) == 1 and sha256(tables[0]) == PATCHED,
                    "Rebuilt initramfs does not contain exactly the tested DSDT")
    print("Installed the tested minimal battery override. Reboot, then check BAT0/ADP1.")
    print("Keep the recovery directory; see docs/acpi.md for restore instructions.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error))
