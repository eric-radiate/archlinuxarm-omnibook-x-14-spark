#!/usr/bin/env python3
"""The battery patcher widens one synthetic buffer and bumps the revision."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

PATCHER = Path(__file__).resolve().parents[1] / "fix-hp-battery.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rbuf.asl"


def run_patch(src: Path, dst: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PATCHER), str(src), str(dst)],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "patched.dsl"
        first = run_patch(FIXTURE, out)
        if first.returncode != 0:
            print(first.stdout)
            print(first.stderr, file=sys.stderr)
            return 1
        text = out.read_text(encoding="utf-8")
        if "Buffer (0x50)" not in text:
            print("buffer was not widened to 80 bytes", file=sys.stderr)
            return 1
        if "0x00000002" not in text:
            print("table revision was not bumped", file=sys.stderr)
            return 1
        if "CreateField (RBUF, 0xD0, 0x190, DATA)" not in text:
            print("DATA field was rewritten", file=sys.stderr)
            return 1
        second = run_patch(out, Path(tmp) / "again.dsl")
        if second.returncode != 4:
            print(second.stdout)
            print("second run should report the buffer is already large enough", file=sys.stderr)
            return 1
    untouched = FIXTURE.read_text(encoding="utf-8")
    if "Buffer (0x40)" not in untouched:
        print("fixture was modified", file=sys.stderr)
        return 1
    print("battery patcher fixture ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
