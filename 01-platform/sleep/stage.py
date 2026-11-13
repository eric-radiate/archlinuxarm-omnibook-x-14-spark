#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage a full native Ubuntu build, retain only hash/ABI-verified private modules."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def require(value, message):
    if not value:
        raise SystemExit(message)

def main():
    require(len(sys.argv) == 3, "Usage: stage.py WORK PRIVATE_MODULES_DIRECTORY")
    require(os.geteuid() != 0, "Build and stage without root.")
    recipe = Path(__file__).resolve().parent
    work = Path(sys.argv[1]).resolve()
    private = Path(sys.argv[2]).resolve()
    release = "7.0.0-1022-nvidia"
    require((work / "build/vmlinux").is_file(), "Complete build first; BTF requires its vmlinux.")
    require(not (work / "stage").exists(), "Refusing to overwrite a staged module tree.")
    pins = json.loads((recipe / "retained-modules.json").read_text())
    for row in pins["modules"]:
        path = private / row["module"]
        raw = (subprocess.check_output(["zstd", "-q", "-dc", str(path)])
               if path.suffix == ".zst" else path.read_bytes())
        require(hashlib.sha256(raw).hexdigest() == row["uncompressed_sha256"],
                f"Unreviewed private module: {path}")
    env = dict(os.environ, KBUILD_BUILD_USER="h7607a", KBUILD_BUILD_HOST="hp-sleep-wake-trial",
               KBUILD_BUILD_TIMESTAMP="2026-11-11 20:00:00 UTC",
               KBUILD_BUILD_VERSION="25~hp-sleep-wake1")
    args = ["make", "-C", str(work / "linux"), f"O={work / 'build'}", "ARCH=arm64",
            "CC=aarch64-linux-gnu-gcc-13", "HOSTCC=aarch64-linux-gnu-gcc-13",
            f"KERNELRELEASE={release}"]
    subprocess.run(args + ["-j8", f"INSTALL_MOD_PATH={work / 'stage'}",
                          "INSTALL_MOD_STRIP=1", "DEPMOD=true", "modules_install"],
                   check=True, env=env)
    modules = work / "stage/lib/modules" / release
    destination = modules / "updates/h7607a"
    destination.mkdir(parents=True)
    for row in pins["modules"]:
        shutil.copy2(private / row["module"], destination)
    shutil.copyfile(work / "build/arch/arm64/boot/Image", modules / "vmlinuz")
    for name in ("build", "source"):
        (modules / name).unlink(missing_ok=True)
    subprocess.run(["depmod", "-b", str(work / "stage"), "-F",
                    str(work / "build/System.map"), release], check=True)
    companion = work / "companion"
    shutil.copytree(recipe / "companion", companion)
    subprocess.run(["make", "-C", str(work / "build"), f"M={companion}", "ARCH=arm64",
                    "CC=aarch64-linux-gnu-gcc-13", "HOSTCC=aarch64-linux-gnu-gcc-13",
                    f"KERNELRELEASE={release}", "W=1", "CFLAGS_MODULE=-DPKG_ABI=1022",
                    "modules"], check=True, env=env)
    result = subprocess.check_output(
        ["python3", str(recipe / "verify-modules.py"), str(work / "build/Module.symvers"),
         *[str(destination / row["module"]) for row in pins["modules"]]], text=True)
    (work / "abi-validation.json").write_text(result)
    for path in recipe.iterdir():
        if path.is_file() and path.name not in ("original.config",):
            shutil.copy2(path, work / path.name)
    shutil.copytree(recipe / "tests", work / "tests")
    subprocess.run(["python3", str(work / "validate-package.py")], check=True)
    print(f"Local trial bundle staged in {work}; no system files or boot settings changed.")

if __name__ == "__main__":
    main()
