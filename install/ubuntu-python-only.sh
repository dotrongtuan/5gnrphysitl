#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_NAME="${VENV_NAME:-.venv}"
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

if [ "$DRY_RUN" -eq 0 ]; then
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY
fi

run_cmd sudo apt update
run_cmd sudo apt install -y python3 python3-venv python3-pip

cd "$PROJECT_ROOT"
run_cmd "$PYTHON_BIN" -m venv "$VENV_NAME"
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install --upgrade pip
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -m pip install -r requirements.txt
run_cmd "$PROJECT_ROOT/$VENV_NAME/bin/python" -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly, numpy, scipy, pandas, yaml; print('Ubuntu Python-only environment OK')"
