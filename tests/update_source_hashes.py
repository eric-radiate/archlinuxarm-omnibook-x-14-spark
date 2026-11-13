#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refresh hashes after reviewing intentional source or notice changes."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                                cwd=root, text=True).splitlines()
selected = {}
for name in sorted(set(paths)):
    path = root / name
    if not path.is_file():
        continue
    if (path.suffix in (".py", ".sh", ".c", ".h", ".patch", ".hook", ".install")
            or name.startswith("LICENSE") or name == "NOTICE"
            or name.startswith("01-platform/sleep/")):
        selected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
(root / "pins/source-files.json").write_text(json.dumps(selected, indent=2) + "\n")
print(f"Recorded {len(selected)} source/notice hashes.")
