#!/usr/bin/env bash
set -euo pipefail

SERVICE_PREFIX="${SERVICE_PREFIX:-safehaven}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/safehaven-frigate-host}"
ENV_FILE="${ENV_FILE:-/etc/default/safehaven-frigate-host}"
CONFIG_FILE="${CONFIG_FILE:-/config/config.yml}"
VENV_DIR="${VENV_DIR:-${INSTALL_ROOT}/.venv}"

if [ -f "${ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
fi

systemctl --no-pager --full status "${SERVICE_PREFIX}-go2rtc.service" "${SERVICE_PREFIX}-frigate-host.service" nginx || true
printf '\n--- validate config ---\n'
CONFIG_FILE="${CONFIG_FILE}" INSTALL_ROOT="${INSTALL_ROOT}" "${VENV_DIR}/bin/python" - <<'PY'
import os
import sys
from pathlib import Path
repo_root = Path(os.environ["INSTALL_ROOT"]) / "frigate-source"
sys.path.insert(0, str(repo_root))
from frigate.config import FrigateConfig
FrigateConfig.load(install=True)
print("config: ok")
PY
printf '\n--- frigate ---\n'
curl -fsS http://127.0.0.1:5001/api/version
printf '\n--- go2rtc ---\n'
curl -fsS http://127.0.0.1:1984/api/streams
printf '\n'
