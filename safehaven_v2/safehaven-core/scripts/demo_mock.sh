#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

python3 scripts/generate_demo_video.py >/dev/null
python3 scripts/mock_frigate_server.py &
MOCK_FRIGATE_PID=$!

cleanup() {
  kill "$MOCK_FRIGATE_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

export CAMERAS='[{"name":"demo_cam","stream_url":"./demo.mp4","rois":{"garage":{"x":0.05,"y":0.25,"w":0.28,"h":0.58},"gate":{"x":0.39,"y":0.25,"w":0.26,"h":0.58},"latch":{"x":0.68,"y":0.25,"w":0.25,"h":0.58}}}]'
export FRIGATE_BASE_URL="http://127.0.0.1:5001"
export METIS_DETECTOR_URL="http://127.0.0.1:8090/detect"
export SAMPLE_FPS=1
export LEFT_OPEN_MINUTES=1
export QUEUE_MAX=5
export METRICS_PORT=9108

if ! curl -fsS http://127.0.0.1:8090/healthz >/dev/null 2>&1; then
  echo "metis-detector is not running on :8090. Start it with MOCK=1 first."
  echo "Example: cd ../metis-detector && pip install -r requirements.txt && MOCK=1 uvicorn app:app --host 0.0.0.0 --port 8090"
  exit 1
fi

echo "Running safehaven-core demo. Watch for [mock-frigate] POST /api/events/... logs."
PYTHONPATH=src python3 -m safehaven_core.main
