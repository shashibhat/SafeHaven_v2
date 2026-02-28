#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INSTALL_ROOT="${INSTALL_ROOT:-/opt/frigate-host}"
FRIGATE_SRC="${FRIGATE_SRC:-${INSTALL_ROOT}/frigate-source}"
VENV_DIR="${VENV_DIR:-${INSTALL_ROOT}/.venv}"
CONFIG_DIR="${CONFIG_DIR:-/config}"
MEDIA_DIR="${MEDIA_DIR:-/media/frigate}"
FRIGATE_BRANCH="${FRIGATE_BRANCH:-dev}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VOYAGE_PIP_PACKAGE="${VOYAGE_PIP_PACKAGE:-voyageai}"
GO2RTC_VERSION="${GO2RTC_VERSION:-1.9.13}"
GO2RTC_DIR="${GO2RTC_DIR:-/usr/local/go2rtc}"
SUDO_PASSWORD="${SUDO_PASSWORD:-}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required on the target host." >&2
  exit 1
fi

sudo_cmd() {
  if [ -n "${SUDO_PASSWORD}" ]; then
    printf '%s\n' "${SUDO_PASSWORD}" | sudo -S -p '' "$@"
  else
    sudo "$@"
  fi
}

sudo_cmd apt-get update
sudo_cmd apt-get install -y \
  git \
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

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but not installed on host. Install ffmpeg and rerun." >&2
  exit 1
fi

sudo_cmd mkdir -p "${INSTALL_ROOT}"
sudo_cmd chown -R "${USER}:${USER}" "${INSTALL_ROOT}"

if [ ! -d "${FRIGATE_SRC}/.git" ]; then
  git clone --depth 1 --branch "${FRIGATE_BRANCH}" https://github.com/blakeblackshear/frigate.git "${FRIGATE_SRC}"
else
  git -C "${FRIGATE_SRC}" fetch origin "${FRIGATE_BRANCH}" --depth 1
  git -C "${FRIGATE_SRC}" reset --hard "origin/${FRIGATE_BRANCH}"
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel

REQ_TMP="$(mktemp)"
cp "${FRIGATE_SRC}/docker/main/requirements-wheels.txt" "${REQ_TMP}"
# Orange Pi Jammy host run: skip heavy/ABI-specific deps not needed for metis-based detection.
sed -i -e '/^tensorflow/d' -e '/^tflite_runtime[[:space:]]@/d' "${REQ_TMP}"
# Python 3.10 compatibility on Jammy arm64.
sed -i -e '/^scipy[[:space:]]*==/d' "${REQ_TMP}"
echo 'scipy==1.15.3' >> "${REQ_TMP}"
echo 'ai-edge-litert>=1.2,<2.0' >> "${REQ_TMP}"
"${VENV_DIR}/bin/pip" install -r "${REQ_TMP}"
rm -f "${REQ_TMP}"

# Frigate source checkout does not provide a pip-installable package layout.
# Run from source via PYTHONPATH and ensure version module exists.
COMMIT_HASH="$(git -C "${FRIGATE_SRC}" rev-parse --short HEAD)"
cat > "${FRIGATE_SRC}/frigate/version.py" <<EOF
VERSION = "${FRIGATE_BRANCH}-${COMMIT_HASH}"
EOF

# Jammy's ffprobe (FFmpeg 4.4 / libavformat 58) fails RTSP probing with "-timeout"
# by entering listen mode; use "-stimeout" in Frigate's ffprobe helper.
sed -i 's/"-timeout"/"-stimeout"/' "${FRIGATE_SRC}/frigate/util/services.py"

# Avoid loading sqlite-vec extension when semantic search is disabled.
sed -i 's/load_vec_extension=True,/load_vec_extension=config.semantic_search.enabled,/' \
  "${FRIGATE_SRC}/frigate/embeddings/maintainer.py"

install -m 0644 "${REPO_DIR}/assets/metis.py" "${FRIGATE_SRC}/frigate/detectors/plugins/metis.py"

if [ -n "${VOYAGE_PIP_PACKAGE}" ]; then
  if ! "${VENV_DIR}/bin/pip" install "${VOYAGE_PIP_PACKAGE}"; then
    echo "warning: failed to install ${VOYAGE_PIP_PACKAGE}; continuing" >&2
  fi
fi

if ! "${VENV_DIR}/bin/python" -c "import ruamel.yaml" >/dev/null 2>&1; then
  "${VENV_DIR}/bin/pip" install ruamel.yaml
fi

GO2RTC_BIN="${GO2RTC_DIR}/bin/go2rtc"
if [ ! -x "${GO2RTC_BIN}" ]; then
  GO2RTC_TMP_DIR="$(mktemp -d)"
  GO2RTC_TAR="${GO2RTC_TMP_DIR}/go2rtc.tgz"
  GO2RTC_URL="https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_arm64.tar.gz"
  curl -fsSL "${GO2RTC_URL}" -o "${GO2RTC_TAR}"
  tar -xzf "${GO2RTC_TAR}" -C "${GO2RTC_TMP_DIR}"
  sudo_cmd mkdir -p "${GO2RTC_DIR}/bin"
  sudo_cmd install -m 0755 "${GO2RTC_TMP_DIR}/go2rtc" "${GO2RTC_BIN}"
  rm -rf "${GO2RTC_TMP_DIR}"
fi

sudo_cmd mkdir -p "${CONFIG_DIR}" "${MEDIA_DIR}"
sudo_cmd chown -R "${USER}:${USER}" "${CONFIG_DIR}" "${MEDIA_DIR}"

if [ ! -f "${CONFIG_DIR}/config.yml" ]; then
  install -m 0644 "${REPO_DIR}/config/config.yml" "${CONFIG_DIR}/config.yml"
fi
install -m 0644 "${FRIGATE_SRC}/labelmap.txt" "${CONFIG_DIR}/labelmap.txt"
if ! grep -q "labelmap_path:" "${CONFIG_DIR}/config.yml"; then
  printf "\nmodel:\n  labelmap_path: /config/labelmap.txt\n" >> "${CONFIG_DIR}/config.yml"
fi
if ! grep -q "^ffmpeg:" "${CONFIG_DIR}/config.yml"; then
  printf "\nffmpeg:\n  path: /usr\n" >> "${CONFIG_DIR}/config.yml"
fi
if ! grep -q "^semantic_search:" "${CONFIG_DIR}/config.yml"; then
  printf "\nsemantic_search:\n  enabled: false\n" >> "${CONFIG_DIR}/config.yml"
fi

NGINX_SITE_TMP="$(mktemp)"
cat > "${NGINX_SITE_TMP}" <<EOF
server {
    listen 5000;
    listen [::]:5000;
    server_name _;

    client_max_body_size 20M;

    location /api/ {
        rewrite ^/api(/.*)$ \$1 break;
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location ~ ^/live/(mse|webrtc)/api/ws$ {
        proxy_pass http://127.0.0.1:1984/api/ws\$is_args\$args;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location ~ ^/live/jsmpeg/(.+)$ {
        proxy_pass http://127.0.0.1:1984/api/ws?src=\$1;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:5002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location /vod/ {
        proxy_pass http://127.0.0.1:5001/vod/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
        proxy_read_timeout 600s;
    }

    location /clips/ {
        proxy_pass http://127.0.0.1:5001/clips/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    location /recordings/ {
        proxy_pass http://127.0.0.1:5001/recordings/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    location /exports/ {
        proxy_pass http://127.0.0.1:5001/exports/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header remote-user viewer;
        proxy_set_header remote-role admin;
    }

    root /opt/frigate-host/web/dist;

    location / {
        try_files \$uri \$uri.html \$uri/ /index.html;
    }
}
EOF
sudo_cmd install -m 0644 "${NGINX_SITE_TMP}" /etc/nginx/sites-available/frigate-host.conf
rm -f "${NGINX_SITE_TMP}"
sudo_cmd ln -sfn /etc/nginx/sites-available/frigate-host.conf /etc/nginx/sites-enabled/frigate-host.conf
if [ -e /etc/nginx/sites-enabled/default ]; then
  sudo_cmd rm -f /etc/nginx/sites-enabled/default
fi
sudo_cmd nginx -t
sudo_cmd systemctl enable --now nginx
sudo_cmd systemctl reload nginx

GO2RTC_START_TMP="$(mktemp)"
cat > "${GO2RTC_START_TMP}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="\${CONFIG_FILE:-${CONFIG_DIR}/config.yml}"
FRIGATE_SRC="\${FRIGATE_SRC:-${FRIGATE_SRC}}"
VENV_DIR="\${VENV_DIR:-${VENV_DIR}}"
GO2RTC_BIN="\${GO2RTC_BIN:-${GO2RTC_BIN}}"
GO2RTC_CREATE="\${FRIGATE_SRC}/docker/main/rootfs/usr/local/go2rtc/create_config.py"

mkdir -p "${CONFIG_DIR}"
if [ ! -f "${CONFIG_DIR}/go2rtc_homekit.yml" ]; then
  printf '{}\n' > "${CONFIG_DIR}/go2rtc_homekit.yml"
fi

rm -f /dev/shm/go2rtc.yaml
PYTHONPATH="\${FRIGATE_SRC}" FRIGATE_SRC="\${FRIGATE_SRC}" CONFIG_FILE="\${CONFIG_FILE}" LIBAVFORMAT_VERSION_MAJOR="\${LIBAVFORMAT_VERSION_MAJOR:-58}" \
  "\${VENV_DIR}/bin/python" "\${GO2RTC_CREATE}"

exec "\${GO2RTC_BIN}" -config="${CONFIG_DIR}/go2rtc_homekit.yml" -config=/dev/shm/go2rtc.yaml
EOF
install -m 0755 "${GO2RTC_START_TMP}" "${INSTALL_ROOT}/go2rtc-host-start.sh"
rm -f "${GO2RTC_START_TMP}"

GO2RTC_UNIT_TMP="$(mktemp)"
cat > "${GO2RTC_UNIT_TMP}" <<EOF
[Unit]
Description=go2rtc (host mode for Frigate)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
Environment=CONFIG_FILE=${CONFIG_DIR}/config.yml
Environment=FRIGATE_SRC=${FRIGATE_SRC}
Environment=VENV_DIR=${VENV_DIR}
Environment=LIBAVFORMAT_VERSION_MAJOR=58
ExecStart=${INSTALL_ROOT}/go2rtc-host-start.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo_cmd install -m 0644 "${GO2RTC_UNIT_TMP}" /etc/systemd/system/go2rtc-host.service
rm -f "${GO2RTC_UNIT_TMP}"

UNIT_TMP="$(mktemp)"
cat > "${UNIT_TMP}" <<EOF
[Unit]
Description=Frigate (host mode, non-Docker)
After=network-online.target go2rtc-host.service
Wants=network-online.target go2rtc-host.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${FRIGATE_SRC}
Environment=CONFIG_FILE=${CONFIG_DIR}/config.yml
Environment=PYTHONPATH=${FRIGATE_SRC}
Environment=PYTHONUNBUFFERED=1
Environment=LIBAVFORMAT_VERSION_MAJOR=58
ExecStart=${VENV_DIR}/bin/python -m frigate
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo_cmd install -m 0644 "${UNIT_TMP}" /etc/systemd/system/frigate-host.service
rm -f "${UNIT_TMP}"

sudo_cmd systemctl daemon-reload
sudo_cmd systemctl enable --now go2rtc-host
sudo_cmd systemctl enable --now frigate-host
sleep 2
sudo_cmd systemctl --no-pager --full status go2rtc-host | sed -n '1,40p'
echo
sudo_cmd systemctl --no-pager --full status frigate-host | sed -n '1,60p'

echo
echo "Frigate host service deployed."
echo "Logs: sudo journalctl -u frigate-host -f"
echo "Config: ${CONFIG_DIR}/config.yml"
