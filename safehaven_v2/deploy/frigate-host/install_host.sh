#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/safehaven-frigate-host}"
FRIGATE_SRC="${INSTALL_ROOT}/frigate-source"
VENV_DIR="${INSTALL_ROOT}/.venv"
ENV_FILE="${ENV_FILE:-/etc/default/safehaven-frigate-host}"
CONFIG_FILE="${CONFIG_FILE:-/config/config.yml}"
CONFIG_DIR="$(dirname "${CONFIG_FILE}")"
MEDIA_DIR="${MEDIA_DIR:-/media/frigate}"
GO2RTC_BIN="${GO2RTC_BIN:-/usr/local/go2rtc/bin/go2rtc}"
GO2RTC_VERSION="${GO2RTC_VERSION:-1.9.13}"
SERVICE_PREFIX="${SERVICE_PREFIX:-safehaven}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_USER="${SUDO_USER:-$USER}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required" >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  rsync \
  nginx \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  pkg-config \
  libopenblas-dev \
  liblapack-dev \
  libatlas-base-dev \
  libgl1 \
  libglib2.0-0 \
  libsndfile1 \
  libgomp1 \
  curl

sudo mkdir -p "${INSTALL_ROOT}" "${CONFIG_DIR}" "${MEDIA_DIR}" /var/log/safehaven /run/safehaven
sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_ROOT}" "${CONFIG_DIR}" "${MEDIA_DIR}" /var/log/safehaven /run/safehaven

rsync -a --delete \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  "${REPO_ROOT}/frigate-source/" "${FRIGATE_SRC}/"
mkdir -p "${INSTALL_ROOT}/bin"
install -m 0755 "${REPO_ROOT}/deploy/frigate-host/bin/run_frigate_host.sh" "${INSTALL_ROOT}/bin/run_frigate_host.sh"
install -m 0755 "${REPO_ROOT}/deploy/frigate-host/bin/run_go2rtc_host.sh" "${INSTALL_ROOT}/bin/run_go2rtc_host.sh"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
REQ_TMP="$(mktemp)"
cp "${FRIGATE_SRC}/docker/main/requirements-wheels.txt" "${REQ_TMP}"
sed -i -e '/^tensorflow/d' -e '/^tflite_runtime[[:space:]]@/d' "${REQ_TMP}"
sed -i -e '/^scipy[[:space:]]*==/d' "${REQ_TMP}"
echo 'scipy==1.15.3' >> "${REQ_TMP}"
echo 'ai-edge-litert>=1.2,<2.0' >> "${REQ_TMP}"
"${VENV_DIR}/bin/pip" install -r "${REQ_TMP}"
rm -f "${REQ_TMP}"
"${VENV_DIR}/bin/pip" install ruamel.yaml

if [ ! -x "${GO2RTC_BIN}" ]; then
  TMP_DIR="$(mktemp -d)"
  TAR_PATH="${TMP_DIR}/go2rtc.tgz"
  curl -fsSL "https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_arm64.tar.gz" -o "${TAR_PATH}"
  tar -xzf "${TAR_PATH}" -C "${TMP_DIR}"
  sudo mkdir -p "$(dirname "${GO2RTC_BIN}")"
  sudo install -m 0755 "${TMP_DIR}/go2rtc" "${GO2RTC_BIN}"
  rm -rf "${TMP_DIR}"
fi

if [ ! -f "${CONFIG_FILE}" ]; then
  install -m 0644 "${REPO_ROOT}/deploy/frigate-host/config/frigate-host.yml" "${CONFIG_FILE}"
fi
install -m 0644 "${FRIGATE_SRC}/labelmap.txt" "${CONFIG_DIR}/labelmap.txt"
if ! grep -q 'labelmap_path:' "${CONFIG_FILE}"; then
  printf '\nmodel:\n  labelmap_path: %s/labelmap.txt\n' "${CONFIG_DIR}" >> "${CONFIG_FILE}"
fi
if [ ! -f "${ENV_FILE}" ]; then
  sudo install -m 0644 "${REPO_ROOT}/deploy/frigate-host/env.example" "${ENV_FILE}"
fi

cat > /tmp/${SERVICE_PREFIX}-go2rtc.service <<UNIT
[Unit]
Description=SafeHaven go2rtc host service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
EnvironmentFile=-${ENV_FILE}
ExecStart=${INSTALL_ROOT}/bin/run_go2rtc_host.sh
Restart=always
RestartSec=2
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT
sudo install -m 0644 /tmp/${SERVICE_PREFIX}-go2rtc.service /etc/systemd/system/${SERVICE_PREFIX}-go2rtc.service

cat > /tmp/${SERVICE_PREFIX}-frigate-host.service <<UNIT
[Unit]
Description=SafeHaven Frigate host service
After=network-online.target ${SERVICE_PREFIX}-go2rtc.service
Wants=network-online.target
Requires=${SERVICE_PREFIX}-go2rtc.service

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${FRIGATE_SRC}
EnvironmentFile=-${ENV_FILE}
ExecStart=${INSTALL_ROOT}/bin/run_frigate_host.sh
Restart=always
RestartSec=2
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT
sudo install -m 0644 /tmp/${SERVICE_PREFIX}-frigate-host.service /etc/systemd/system/${SERVICE_PREFIX}-frigate-host.service

cat > /tmp/${SERVICE_PREFIX}-nginx.conf <<'NGINX'
server {
    listen 5000;
    listen [::]:5000;
    server_name _;

    client_max_body_size 20M;

    location /api/ {
        rewrite ^/api(/.*)$ $1 break;
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location ~ ^/live/(mse|webrtc)/api/ws$ {
        proxy_pass http://127.0.0.1:1984/api/ws$is_args$args;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:5002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location /vod/ {
        proxy_pass http://127.0.0.1:5001/vod/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location /clips/ {
        proxy_pass http://127.0.0.1:5001/clips/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    location /recordings/ {
        proxy_pass http://127.0.0.1:5001/recordings/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    location /exports/ {
        proxy_pass http://127.0.0.1:5001/exports/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    root INSTALL_ROOT_PLACEHOLDER/frigate-source/web/dist;

    location / {
        try_files $uri $uri.html $uri/ /index.html;
    }
}
NGINX
sed -i "s#INSTALL_ROOT_PLACEHOLDER#${INSTALL_ROOT}#g" /tmp/${SERVICE_PREFIX}-nginx.conf
sudo install -m 0644 /tmp/${SERVICE_PREFIX}-nginx.conf /etc/nginx/sites-available/${SERVICE_PREFIX}-frigate-host.conf
sudo ln -sfn /etc/nginx/sites-available/${SERVICE_PREFIX}-frigate-host.conf /etc/nginx/sites-enabled/${SERVICE_PREFIX}-frigate-host.conf
if [ -e /etc/nginx/sites-enabled/default ]; then
  sudo rm -f /etc/nginx/sites-enabled/default
fi

CONFIG_FILE="${CONFIG_FILE}" PYTHONPATH="${FRIGATE_SRC}" "${VENV_DIR}/bin/python" -m frigate --validate-config
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now nginx ${SERVICE_PREFIX}-go2rtc.service ${SERVICE_PREFIX}-frigate-host.service

cat <<MSG
Installed SafeHaven Frigate host path.
Edit ${ENV_FILE} and ${CONFIG_FILE} for your camera and Metis network, then restart:
  sudo systemctl restart ${SERVICE_PREFIX}-go2rtc.service ${SERVICE_PREFIX}-frigate-host.service
MSG
