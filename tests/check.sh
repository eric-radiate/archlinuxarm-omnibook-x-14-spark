#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python3 -m unittest discover -s tests -v
python3 01-platform/acpi/tests/test_battery_patch.py
python3 - <<'PY'
import ast
import json
from pathlib import Path
import subprocess
root = Path('.')
for path in root.rglob('*'):
    if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts:
        continue
    if path.suffix == '.py' or path.name == 'battery-sleep-log':
        ast.parse(path.read_text(), filename=str(path))
    if path.suffix in ('.sh', '.hook', '.install'):
        subprocess.run(['bash', '-n', str(path)], check=True)
    if path.suffix in ('.json', '.jsonc'):
        json.loads(path.read_text())
print('Python, shell and JSON syntax passed.')
PY
task_test_dir=$(mktemp -d)
trap 'rm -rf -- "$task_test_dir"' EXIT
cc -Wall -Wextra -Werror -fsanitize=address,undefined \
  01-platform/sleep/companion/test_sequence.c -o "$task_test_dir/lps0"
"$task_test_dir/lps0"
python3 tests/check_provenance.py
