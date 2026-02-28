#!/usr/bin/env bash
set -euo pipefail

ORANGEPI_HOST="${ORANGEPI_HOST:-192.168.1.46}"
ORANGEPI_USER="${ORANGEPI_USER:-orangepi}"
ORANGEPI_PASSWORD="${ORANGEPI_PASSWORD:-orangepi}"

expect -c '
  set timeout 60
  spawn ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '$ORANGEPI_USER'@'$ORANGEPI_HOST' "systemctl is-active go2rtc-host; systemctl --no-pager --full status go2rtc-host | sed -n \"1,25p\"; echo; systemctl is-active frigate-host; systemctl --no-pager --full status frigate-host | sed -n \"1,40p\"; echo; ss -lntp | grep :1984 || true; curl -sS --max-time 5 http://127.0.0.1:1984/api/streams || true"
  expect "*assword:*"
  send "'$ORANGEPI_PASSWORD'\r"
  expect eof
'
