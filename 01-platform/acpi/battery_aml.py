# SPDX-License-Identifier: MIT
"""Exact F.05 DSDT fix; no firmware image is embedded or redistributed."""
import hashlib
import struct

ORIGINAL = "66e0fc9c32649797f117e7f13cff321808075f0704223ca29b8e2f717654eec0"
PATCHED = "e4971160feb9cbc27b652a5f9fa10979834886ecfba06ed36ff5c2749c1a1e4e"
OFFSET = 73309
FIELD = bytes.fromhex("5b13425546460ad00b900144415441")


def edit(data):
    """Length-preserving edit; caller first establishes the exact input hash."""
    if data[:4] != b"DSDT" or len(data) != 148362:
        raise ValueError("Unexpected DSDT signature or length")
    if struct.unpack_from("<I", data, 4)[0] != len(data) or sum(data) % 256:
        raise ValueError("Invalid ACPI length/checksum")
    if data[OFFSET:OFFSET + len(FIELD)] != FIELD:
        raise ValueError("Expected unused CreateField is absent")
    if struct.unpack_from("<I", data, 24)[0] != 0x01072009:
        raise ValueError("Unexpected OEM revision")
    result = bytearray(data)
    result[OFFSET:OFFSET + len(FIELD)] = b"\xa3" * len(FIELD)
    struct.pack_into("<I", result, 24, 0x0107200A)
    result[9] = 0
    result[9] = (-sum(result)) & 255
    return bytes(result)


def patch(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED:
        return data
    if digest != ORIGINAL:
        raise ValueError("Unreviewed DSDT hash; refusing to patch this firmware")
    result = edit(data)
    if hashlib.sha256(result).hexdigest() != PATCHED:
        raise ValueError("Patched DSDT hash does not match the hardware-tested fix")
    return result
