from prometheus_client import Counter, Gauge, Histogram, start_http_server

INFER_MS = Histogram(
    "safehaven_infer_ms",
    "Inference latency in milliseconds",
    buckets=(1, 5, 10, 20, 50, 100, 200, 500, 1000),
)
E2E_MS = Histogram(
    "safehaven_e2e_ms",
    "End-to-end latency in milliseconds",
    buckets=(5, 10, 20, 50, 100, 200, 500, 1000, 2000),
)
QUEUE_DEPTH = Gauge("safehaven_queue_depth", "Queue depth per camera", ["camera"])
DROPPED_SAMPLES = Counter("safehaven_dropped_samples", "Dropped stale samples", ["camera"])
SEMANTIC_EVENTS = Counter("safehaven_semantic_events", "Semantic events emitted", ["camera", "type"])


def start_metrics_server(port: int) -> None:
    start_http_server(port)
