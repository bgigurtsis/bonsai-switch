#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "This installer supports Apple Silicon macOS only."; exit 1
fi
if [[ ! -d '/Applications/LM Studio.app' ]]; then
  echo "Install and open LM Studio from https://lmstudio.ai/download first."; exit 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Apple Command Line Tools are required for Git. Install them with xcode-select --install, then rerun."; exit 1
fi
mkdir -p .runtime/bin
export UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python-downloads"
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
UV="$PWD/.runtime/bin/uv"
if [[ ! -x "$UV" ]]; then
  echo "Installing pinned uv from Astral into this project..."
  bootstrap="$(mktemp)"
  trap 'rm -f "$bootstrap"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 \
    https://astral.sh/uv/0.12.16/install.sh -o "$bootstrap"
  UV_INSTALL_DIR="$PWD/.runtime/bin" UV_NO_MODIFY_PATH=1 sh "$bootstrap"
  rm -f "$bootstrap"
  trap - EXIT
fi
"$UV" python install 3.12
"$UV" run --python 3.12 --no-project python installer.py "$@"
