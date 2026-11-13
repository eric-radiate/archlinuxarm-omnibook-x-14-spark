#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Transactional compatibility fix for the pinned legacy Arch package only."""
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from hp_boot import IMAGE, RELEASE, atomic_copy, guard, rebuild, require, sha256, transaction
from patch_module import PATCHED, patch


def verify_image():
    # lsinitcpio extracts into the current directory; never extract into / or the repo.
    with tempfile.TemporaryDirectory(prefix="hp-initramfs-check-") as directory:
        subprocess.run(["lsinitcpio", "-x", str(IMAGE)], cwd=directory,
                       stdout=subprocess.DEVNULL, check=True)
        modules = list(Path(directory).rglob("soundwire-mtk.ko*"))
        require(len(modules) == 1, "Expected one SoundWire module in the rebuilt image")
        module = modules[0]
        if module.suffix == ".zst":
            data = subprocess.check_output(["zstd", "-dc", str(module)])
        elif module.suffix == ".xz":
            import lzma
            data = lzma.decompress(module.read_bytes())
        else:
            data = module.read_bytes()
        import hashlib
        require(hashlib.sha256(data).hexdigest() == PATCHED,
                "Rebuilt initramfs still contains a different SoundWire module")


def main():
    guard()
    installed = subprocess.check_output(
        ["pacman", "-Q", "h7607a-hardware"], text=True).strip()
    require(installed == "h7607a-hardware 1.0.0-4", "Unsupported hardware package")
    module = Path("/usr/lib/modules", RELEASE, "updates/h7607a/soundwire-mtk.ko")
    require(not module.is_symlink(), "Unexpected module symlink")
    data = patch(module.read_bytes())
    with transaction([module, IMAGE]) as saved:
        candidate = saved / "soundwire-candidate.local"
        candidate.write_bytes(data)
        candidate.chmod(0o644)
        atomic_copy(candidate, module)
        rebuild()
        verify_image()
    print("Verified the two-amp module in the rebuilt initramfs. Reboot to apply.")
    print("This workaround is for the legacy Arch package; Omarchy has a source topology patch.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error))
