#!/usr/bin/env bash
# Run every repository check. Exit code is non-zero on any failure.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 tests/check_contract.py
python3 -m unittest discover -s tests -p 'test_*.py'
