# Frigate Host Deployment for Orange Pi (Jammy, non-Docker)

This repo deploys Frigate directly on Ubuntu Jammy (`aarch64`) with a Python venv, patches in a `metis` detector plugin, and installs an optional Voyage SDK package in the same environment.

Target validated via SSH:
- Host: `192.168.1.46`
- User: `orangepi`
- OS: `Orange Pi 1.2.0 Jammy` (`Ubuntu 22.04`)
- Arch: `aarch64`

## What it sets up

- Frigate source at `/opt/frigate-host/frigate-source`
- Venv at `/opt/frigate-host/.venv`
- Frigate config at `/config/config.yml`
- Media dir at `/media/frigate`
- Nginx reverse proxy at `:5000` (includes `/live/*` websocket proxy to go2rtc)
- go2rtc binary at `/usr/local/go2rtc/bin/go2rtc`
- Helper script at `/opt/frigate-host/go2rtc-host-start.sh`
- Systemd unit: `go2rtc-host.service`
- Systemd unit: `frigate-host.service`
- Metis plugin at `frigate/detectors/plugins/metis.py`

## Deploy from this machine

```bash
cd /Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/frigate_orangepi_jammy
ORANGEPI_PASSWORD=orangepi VOYAGE_PIP_PACKAGE=voyageai ./scripts/deploy_and_start.sh
```

## Check remote service

```bash
cd /Users/bytedance/personal/hackathon/security-system/SafeHaven_v2/frigate_orangepi_jammy
ORANGEPI_PASSWORD=orangepi ./scripts/check_remote.sh
```

## Directly on Orange Pi

If the repo already exists on the Orange Pi:

```bash
cd ~/frigate_orangepi_jammy
VOYAGE_PIP_PACKAGE=voyageai ./scripts/install_remote.sh
```

## Notes

- The installer uses upstream Frigate `requirements-wheels.txt` but removes TensorFlow and `tflite_runtime` host pins, then adds `ai-edge-litert` for ARM compatibility.
- Default `VOYAGE_PIP_PACKAGE` is `voyageai`. Override if your SDK package name differs.
- Edit `/config/config.yml` with your cameras and metis endpoint.
- Follow logs with:

```bash
sudo journalctl -u go2rtc-host -f
sudo journalctl -u frigate-host -f
```
