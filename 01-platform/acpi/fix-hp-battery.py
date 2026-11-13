#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Legacy ASL experiment: NOT the default or hardware-tested installer.

Enlarge the HP OmniBook FFA0.RBUF buffer that ACPI rejects.

The kernel reports:

  Field [DATA] at bit offset/length 208/400 exceeds size of target Buffer (512 bits)

512 bits is 64 bytes. Bits 208..607 need 76 bytes. This rewrites the
decompiled ASL, and only that buffer, then bumps the table revision so
the kernel will accept the override.

The input is a disassembly of the machine's own DSDT. This program does not
embed firmware tables.
"""

from __future__ import annotations

import re
import sys

NEED_BITS = 208 + 400  # 608
NEW_BYTES = 0x50  # 80 bytes, 640 bits


def parse_int(text: str) -> int:
    return int(text, 16) if text.lower().startswith("0x") else int(text)


def find_data_field(text: str) -> re.Match[str] | None:
    pattern = re.compile(
        r"CreateField\s*\(\s*([\\A-Za-z0-9_.]+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*DATA\s*\)"
    )
    found = None
    for match in pattern.finditer(text):
        if parse_int(match.group(2)) == 208 and parse_int(match.group(3)) == 400:
            if found is not None:
                raise SystemExit("more than one DATA field at bit 208 length 400")
            found = match
    return found


def buffer_patterns(source: str) -> list[re.Pattern[str]]:
    name = re.escape(source.split(".")[-1])
    return [
        re.compile(
            rf"(Name\s*\(\s*{name}\s*,\s*Buffer\s*\(\s*)(0x[0-9A-Fa-f]+|\d+)(\s*\))"
        ),
        re.compile(
            rf"(^\s*{name}\s*=\s*Buffer\s*\(\s*)(0x[0-9A-Fa-f]+|\d+)(\s*\))",
            re.M,
        ),
    ]


def bump_revision(text: str) -> str:
    match = re.search(r"DefinitionBlock\s*\((.*?)\)", text, re.S)
    if match is None:
        raise SystemExit("DefinitionBlock not found")
    body = match.group(1)
    numbers = list(re.finditer(r"0x[0-9A-Fa-f]+|\d+", body))
    if not numbers:
        raise SystemExit("DefinitionBlock has no revision")
    last = numbers[-1]
    value = parse_int(last.group()) + 1
    new_body = body[: last.start()] + f"0x{value:08X}" + body[last.end() :]
    return text[: match.start(1)] + new_body + text[match.end(1) :]


def patch(text: str) -> tuple[str, str]:
    field = find_data_field(text)
    if field is None:
        return text, "no-field"
    source = field.group(1)
    matches: list[re.Match[str]] = []
    pattern = None
    for candidate in buffer_patterns(source):
        matches = list(candidate.finditer(text))
        if matches:
            pattern = candidate
            break
    if pattern is None or len(matches) != 1:
        raise SystemExit(
            f"DATA is created from {source}, but its Buffer size was not a single "
            f"Buffer(N) declaration ({len(matches)} found)"
        )
    size = parse_int(matches[0].group(2))
    if size * 8 >= NEED_BITS:
        return text, f"already {size} bytes"
    if size != 64:
        raise SystemExit(
            f"refusing to resize {source}: buffer is {size} bytes, expected 64"
        )

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}0x{NEW_BYTES:02X}{match.group(3)}"

    updated = pattern.sub(repl, text, count=1)
    updated = bump_revision(updated)
    return updated, f"{source}: 64 bytes -> {NEW_BYTES} bytes"


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} IN.dsl OUT.dsl", file=sys.stderr)
        return 2
    original = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    updated, note = patch(original)
    if note == "no-field":
        print("no-field")
        return 3
    if note.startswith("already"):
        print(note)
        return 4
    open(sys.argv[2], "w", encoding="utf-8").write(updated)
    print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
