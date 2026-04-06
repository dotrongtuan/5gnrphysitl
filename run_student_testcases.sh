#!/usr/bin/env sh
set -eu

PYTHON_BIN="python"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

exec "$PYTHON_BIN" run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases "$@"
