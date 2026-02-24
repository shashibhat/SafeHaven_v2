import logging
from pathlib import Path

import requests

LOGGER = logging.getLogger(__name__)


class FrigateApi:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_event(
        self,
        camera: str,
        label: str,
        sub_label: str,
        score: float | None = None,
        duration: int | None = None,
        include_recording: bool = True,
        draw: dict | None = None,
    ) -> str | None:
        url = f"{self.base_url}/api/events/{camera}/{label}/create"
        payload = {"sub_label": sub_label}
        if score is not None:
            payload["score"] = float(score)
        if duration is not None:
            payload["duration"] = int(duration)
        payload["include_recording"] = bool(include_recording)
        if draw is not None:
            payload["draw"] = draw

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code >= 300:
                LOGGER.warning("Create Event failed url=%s status=%s body=%s", url, resp.status_code, resp.text)
                return None
            LOGGER.info("Create Event success url=%s payload=%s status=%s", url, payload, resp.status_code)
            try:
                data = resp.json()
                return data.get("event_id")
            except Exception:
                return None
        except requests.RequestException as exc:
            LOGGER.warning("Create Event request error url=%s err=%s", url, exc)
            return None

    def fetch_event_media(self, event_id: str, out_dir: str) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for media, ext in (("snapshot.jpg", "jpg"), ("clip.mp4", "mp4")):
            url = f"{self.base_url}/api/events/{event_id}/{media}"
            path = out / f"{event_id}.{ext}"
            try:
                resp = requests.get(url, timeout=max(self.timeout, 10))
                if resp.status_code == 200 and resp.content:
                    path.write_bytes(resp.content)
                    LOGGER.info("Saved event media %s", path)
                else:
                    LOGGER.info("Event media unavailable yet url=%s status=%s", url, resp.status_code)
            except requests.RequestException as exc:
                LOGGER.info("Event media fetch failed url=%s err=%s", url, exc)
