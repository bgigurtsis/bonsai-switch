#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .runtime/python/bin/python ]]; then
  echo "Run Install.command first."; exit 1
fi
exec .runtime/python/bin/python launcher.py
