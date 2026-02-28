import logging

import requests

LOGGER = logging.getLogger(__name__)


class FrigateApi:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def create_event(
        self,
        camera: str,
        label: str,
        sub_label: str,
        score: float | None = None,
        duration: int | None = None,
    ) -> bool:
        url = f"{self.base_url}/api/events/{camera}/{label}/create"
        payload = {"sub_label": sub_label}
        if score is not None:
            payload["score"] = float(score)
        if duration is not None:
            payload["duration"] = int(duration)

        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            if resp.status_code >= 300:
                LOGGER.warning("Create Event failed url=%s status=%s body=%s", url, resp.status_code, resp.text)
                return False
            return True
        except requests.RequestException as exc:
            LOGGER.warning("Create Event request error url=%s err=%s", url, exc)
            return False
