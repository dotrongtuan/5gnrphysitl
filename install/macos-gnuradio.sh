#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_NAME="${VENV_NAME:-.venv-gr}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
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

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required for the automated macOS GNU Radio setup." >&2
  echo "Install Homebrew first: https://brew.sh/" >&2
  exit 1
fi

run_cmd brew install gnuradio

if [ "$DRY_RUN" -eq 0 ]; then
  if "$PYTHON_BIN" -c "import gnuradio" >/dev/null 2>&1; then
    :
  else
    echo "Current PYTHON_BIN does not see GNU Radio. Override PYTHON_BIN if needed." >&2
    echo "Example:" >&2
    echo "  PYTHON_BIN=\$(brew --prefix python@3.11)/bin/python3.11 install/macos-gnuradio.sh" >&2
    exit 1
  fi
fi

cd "$PROJECT_ROOT"
run_cmd "$PYTHON_BIN" -m venv --system-site-packages "$VENV_NAME"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install --upgrade pip
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install -r requirements.txt
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "from gnuradio import blocks, gr, qtgui; from gnuradio.fft import window; print('GNU Radio QT import OK')"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly; print('macOS GNU Radio environment OK')"
