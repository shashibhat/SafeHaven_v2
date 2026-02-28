#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${INSTALL_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
FRIGATE_SRC="${FRIGATE_SRC:-${INSTALL_ROOT}/frigate-source}"
VENV_DIR="${VENV_DIR:-${INSTALL_ROOT}/.venv}"
CONFIG_FILE="${CONFIG_FILE:-/config/config.yml}"

export CONFIG_FILE
export PYTHONPATH="${FRIGATE_SRC}${PYTHONPATH:+:${PYTHONPATH}}"
export PATH="/usr/local/go2rtc/bin:${PATH}"
export PYTHONUNBUFFERED=1

exec "${VENV_DIR}/bin/python" -m frigate "$@"
