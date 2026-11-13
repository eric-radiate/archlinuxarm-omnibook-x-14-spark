#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage three owner-supplied HP files privately; never install or download them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'pins/hp-speaker-firmware.json'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage(driver, output, manifest):
    driver = Path(driver).resolve()
    output = Path(output).absolute()
    require(not output.resolve().is_relative_to(REPO),
            'Keep proprietary inputs and output outside the source repository.')
    require(not output.exists() and not output.is_symlink(), 'Output already exists; choose a new private directory.')
    files = manifest['files']
    require(len(files) == 3, 'Expected one firmware and two tuning files.')
    for row in files:
        relative, name = Path(row['source']), Path(row['target'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                name.name == str(name) and name.name not in ('', '.', '..'), 'Unexpected firmware path.')
        source = driver / relative
        require(source.is_file() and not source.is_symlink(), 'Missing regular local input: ' + str(source))
        require(source.stat().st_size == row['bytes'] and digest(source) == row['sha256'],
                'Unreviewed HP input; no output created: ' + str(source))
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.hp-firmware-', dir=output.parent))
    try:
        cirrus = temporary / 'cirrus'
        cirrus.mkdir(mode=0o700)
        for row in files:
            target = cirrus / row['target']
            shutil.copyfile(driver / row['source'], target)
            target.chmod(0o600)
            require(digest(target) == row['sha256'], 'Input changed while staging; no output installed.')
        (temporary / 'firmware-map.json').write_text(json.dumps(manifest, indent=2) + '\n')
        require(not output.exists() and not output.is_symlink(), 'Output appeared during staging.')
        os.rename(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver_directory', type=Path, help='Locally acquired extension DriverStore directory')
    parser.add_argument('output', type=Path, help='New private directory outside this repository')
    args = parser.parse_args()
    output = stage(args.driver_directory, args.output, json.loads(MANIFEST.read_text()))
    print('Verified all three HP inputs; staged under', output)
    print('No system configuration, firmware device, initramfs or boot selection was changed.')
    print('Local possession and a matching hash do not grant redistribution rights.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit(str(error))
