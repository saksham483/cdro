#!/usr/bin/env bash
set -e
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
echo "Running CDRO Pytest Suite..."
.venv/bin/pytest -v
