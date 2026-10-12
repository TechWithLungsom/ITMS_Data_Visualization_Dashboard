#!/bin/zsh
set -e
cd "$(dirname "$0")"
export MODEL_PATH="${MODEL_PATH:-$HOME/Downloads/best (1).pt}"
export YOLO_CONFIG_DIR="$PWD/.venv/yolo-config"
export MPLCONFIGDIR="$PWD/.venv/matplotlib"
if [[ ! -x .venv/bin/python ]]; then
  if [[ -x ../../work/venv/bin/python ]]; then
    exec ../../work/venv/bin/python backend/app.py
  fi
  echo 'Creating Python environment (Python 3.10–3.13 recommended)…'
  python3 -m venv .venv
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
exec .venv/bin/python backend/app.py
