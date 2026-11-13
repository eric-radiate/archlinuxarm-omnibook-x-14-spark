#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check published source hashes and prevent accidental binary/firmware inclusion."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "pins/source-files.json").read_text())
for name, expected in manifest.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Source hash mismatch: {name}")
for name in subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines():
    path = Path(name)
    if path.suffix in (".ko", ".o", ".aml", ".dsl", ".wmfw", ".bin", ".img", ".iso", ".pem", ".key") or path.name == "vmlinux":
        raise SystemExit(f"Unexpected binary, firmware or key in tracked tree: {name}")
print(f"Source hashes passed ({len(manifest)}); no tracked firmware, binaries or private keys.")
