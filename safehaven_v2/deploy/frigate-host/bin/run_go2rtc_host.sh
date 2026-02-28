#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${INSTALL_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
FRIGATE_SRC="${FRIGATE_SRC:-${INSTALL_ROOT}/frigate-source}"
VENV_DIR="${VENV_DIR:-${INSTALL_ROOT}/.venv}"
CONFIG_FILE="${CONFIG_FILE:-/config/config.yml}"
GO2RTC_BIN="${GO2RTC_BIN:-/usr/local/go2rtc/bin/go2rtc}"

mkdir -p /run/safehaven /dev/shm
FRIGATE_SRC="${FRIGATE_SRC}" CONFIG_FILE="${CONFIG_FILE}" \
  "${VENV_DIR}/bin/python" \
  "${FRIGATE_SRC}/docker/main/rootfs/usr/local/go2rtc/create_config.py"

exec "${GO2RTC_BIN}" -config /dev/shm/go2rtc.yaml
