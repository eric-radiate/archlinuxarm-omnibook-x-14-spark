# SPDX-License-Identifier: MIT
"""Patch only the exact unsigned module in h7607a-hardware 1.0.0-4."""
import hashlib

ORIGINAL = "7162e23606a3bbcf4ff15fc2eada8662eee9962b88b5605d11f51e45e74b7d5f"
PATCHED = "5e91ec51a90ea348ab4c20d3a92e83f0cb1f6d50fcadf8108368f90a57dd933b"
OFFSET = 0xE758 + 0x7978 + 4


def patch(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED:
        return data
    if digest != ORIGINAL:
        raise ValueError("Unreviewed/signed/different module; use a source-built HP topology")
    result = bytearray(data)
    if result[OFFSET] != 4:
        raise ValueError("Unexpected machine table")
    result[OFFSET] = 2
    if hashlib.sha256(result).hexdigest() != PATCHED:
        raise ValueError("Patched module hash mismatch")
    return bytes(result)
