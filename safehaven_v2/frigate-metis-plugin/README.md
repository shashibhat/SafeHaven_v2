# Frigate Metis Detector Plugin (`type: metis`)

Single-file Frigate detector plugin that forwards detection to `metis-detector` over HTTP.

## Install (bind mount)

Mount `metis_http.py` into Frigate plugin path:

- `/opt/frigate/frigate/detectors/plugins/metis_http.py`

Example compose volume:

```yaml
volumes:
  - ./frigate-metis-plugin/metis_http.py:/opt/frigate/frigate/detectors/plugins/metis_http.py:ro
```

## Frigate config snippet

```yaml
detectors:
  metis0:
    type: metis
    endpoint: http://metis-detector:8090/detect
    timeout_ms: 100
```

## Contract

`detect_raw(tensor_input)` posts JPEG bytes to Metis service and expects JSON detections:

`[class_id, score, x1, y1, x2, y2]` (normalized)

Returns `np.ndarray` with shape `(N, 6)` to Frigate.
