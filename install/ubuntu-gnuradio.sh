#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_NAME="${VENV_NAME:-.venv-gr}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
  esac
done

run_cmd() {
  echo "+ $*"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@"
  fi
}

run_cmd sudo apt update
run_cmd sudo apt install -y python3 python3-venv python3-pip gnuradio

cd "$PROJECT_ROOT"
run_cmd "$PYTHON_BIN" -m venv --system-site-packages "$VENV_NAME"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install --upgrade pip
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install -r requirements.txt
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "from gnuradio import blocks, gr, qtgui; from gnuradio.fft import window; print('GNU Radio QT import OK')"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly; print('Ubuntu GNU Radio environment OK')"
