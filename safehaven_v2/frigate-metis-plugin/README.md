# Frigate Metis Detector Plugin (`type: metis`)

Single-file Frigate detector plugin that forwards detection to `metis-detector` over HTTP.

Status:
- provides the stock-Frigate HTTP sidecar path
- direct `frigate-host` integration lives in `frigate-source/frigate/detectors/plugins/metis.py`

## Install (bind mount)

Mount `metis_http.py` into Frigate plugin path:

- `/opt/frigate/frigate/detectors/plugins/metis.py`

Example compose volume:

```yaml
volumes:
  - ./frigate-metis-plugin/metis_http.py:/opt/frigate/frigate/detectors/plugins/metis.py:ro
```

## Frigate config snippet

```yaml
detectors:
  metis0:
    type: metis
    execution: http
    endpoint: http://metis-detector:8090/detect
    timeout_ms: 200
```

## Contract

`detect_raw(tensor_input)` posts JPEG bytes to Metis service and expects JSON detections:

`[class_id, score, x1, y1, x2, y2]` (normalized)

The plugin converts this to Frigate's detector format:
`[class_id, score, y_min, x_min, y_max, x_max]`.

Returns `np.ndarray` with shape `(20, 6)` to Frigate.
