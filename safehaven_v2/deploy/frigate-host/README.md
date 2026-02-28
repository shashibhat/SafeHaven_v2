# Direct Frigate Host Deployment

This directory packages the cloned `frigate-source` path for Orange Pi / Ubuntu Jammy host deployments where Voyager SDK access must stay outside Docker.

What it installs:
- `safehaven-go2rtc.service`
- `safehaven-frigate-host.service`
- nginx reverse proxy on `:5000`
- Frigate config at `/config/config.yml`
- environment file at `/etc/default/safehaven-frigate-host`

## Required inputs

Edit `/etc/default/safehaven-frigate-host` after install:
- `FRIGATE_RTSP_USER`
- `FRIGATE_RTSP_PASSWORD`
- `FRIGATE_CAMERA_HOST`
- `FRIGATE_RECORD_PATH`
- `FRIGATE_DETECT_PATH`
- `FRIGATE_METIS_VOYAGER_PYTHON`
- `FRIGATE_METIS_VOYAGER_SDK_ROOT`
- `FRIGATE_METIS_NETWORK`

Edit `/config/config.yml` if camera names, roles, or detect geometry differ.

## Install on host

Run from a checkout of `safehaven_v2` on the Orange Pi:

```bash
cd safehaven_v2
./deploy/frigate-host/install_host.sh
```

## Validate

```bash
./deploy/frigate-host/check_host.sh
```

## Deployment note

Rollout depends on a healthy Voyager SDK and responsive Metis device on the target host. If hardware bring-up fails, the Frigate service layer will remain unavailable until the accelerator runtime is operational.
