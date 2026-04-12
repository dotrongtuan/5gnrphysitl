#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_NAME="${VENV_NAME:-.venv}"
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
  echo "Homebrew is required for the automated macOS setup." >&2
  echo "Install Homebrew first: https://brew.sh/" >&2
  exit 1
fi

run_cmd brew install python@3.11

if [ "$PYTHON_BIN" = "python3" ]; then
  BREW_PY="$(brew --prefix python@3.11)/bin/python3.11"
  if [ -x "$BREW_PY" ]; then
    PYTHON_BIN="$BREW_PY"
  fi
fi

if [ "$DRY_RUN" -eq 0 ]; then
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY
fi

cd "$PROJECT_ROOT"
run_cmd "$PYTHON_BIN" -m venv "$VENV_NAME"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install --upgrade pip
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install -r requirements.txt
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly, numpy, scipy, pandas, yaml; print('macOS Python-only environment OK')"
