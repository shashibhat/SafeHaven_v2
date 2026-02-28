#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ORANGEPI_HOST="${ORANGEPI_HOST:-192.168.1.46}"
ORANGEPI_USER="${ORANGEPI_USER:-orangepi}"
ORANGEPI_PASSWORD="${ORANGEPI_PASSWORD:-orangepi}"
REMOTE_DIR="${REMOTE_DIR:-/home/${ORANGEPI_USER}/frigate_orangepi_jammy}"
VOYAGE_PIP_PACKAGE="${VOYAGE_PIP_PACKAGE:-voyageai}"

ARCHIVE="$(mktemp /tmp/frigate_orangepi_jammy.XXXXXX.tgz)"
tar -C "$(dirname "${LOCAL_DIR}")" -czf "${ARCHIVE}" "$(basename "${LOCAL_DIR}")"

expect -c '
  set timeout 60
  spawn scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '$ARCHIVE' '$ORANGEPI_USER'@'$ORANGEPI_HOST':/tmp/frigate_orangepi_jammy.tgz
  expect "*assword:*"
  send "'$ORANGEPI_PASSWORD'\r"
  expect eof
'

expect -c '
  set timeout 1800
  spawn ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '$ORANGEPI_USER'@'$ORANGEPI_HOST' "rm -rf '$REMOTE_DIR' && mkdir -p '$REMOTE_DIR' && tar -xzf /tmp/frigate_orangepi_jammy.tgz -C '$REMOTE_DIR' --strip-components=1 && SUDO_PASSWORD='$ORANGEPI_PASSWORD' VOYAGE_PIP_PACKAGE='$VOYAGE_PIP_PACKAGE' bash '$REMOTE_DIR'/scripts/install_remote.sh"
  expect "*assword:*"
  send "'$ORANGEPI_PASSWORD'\r"
  expect eof
'

rm -f "${ARCHIVE}"

echo "Deployment complete."
