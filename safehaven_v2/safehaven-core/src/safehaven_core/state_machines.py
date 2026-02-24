from dataclasses import dataclass
from enum import Enum


class ZoneState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass
class StateOutput:
    transition_event: str | None
    left_open_event: str | None


class DebouncedStateMachine:
    def __init__(
        self,
        zone_name: str,
        open_state_name: str,
        closed_state_name: str,
        open_event: str,
        close_event: str,
        left_open_event: str,
        left_open_seconds: float,
        open_required: int = 3,
        closed_required: int = 3,
    ) -> None:
        self.zone_name = zone_name
        self.open_state_name = open_state_name
        self.closed_state_name = closed_state_name
        self.open_event = open_event
        self.close_event = close_event
        self.left_open_event_name = left_open_event
        self.left_open_seconds = left_open_seconds
        self.open_required = open_required
        self.closed_required = closed_required

        self.state = ZoneState.UNKNOWN
        self._candidate: ZoneState | None = None
        self._candidate_count = 0
        self._open_since: float | None = None
        self._left_open_emitted = False

    def update(self, observed: ZoneState, ts: float) -> StateOutput:
        transition_event = None
        left_open_event = None

        if observed == ZoneState.UNKNOWN:
            if self._candidate == ZoneState.UNKNOWN:
                self._candidate_count += 1
            else:
                self._candidate = ZoneState.UNKNOWN
                self._candidate_count = 1
            return StateOutput(None, self._check_left_open(ts))

        if self._candidate == observed:
            self._candidate_count += 1
        else:
            self._candidate = observed
            self._candidate_count = 1

        required = self.open_required if observed == ZoneState.OPEN else self.closed_required
        if self._candidate_count >= required and self.state != observed:
            self.state = observed
            if observed == ZoneState.OPEN:
                self._open_since = ts
                self._left_open_emitted = False
                transition_event = self.open_event
            elif observed == ZoneState.CLOSED:
                self._open_since = None
                self._left_open_emitted = False
                transition_event = self.close_event

        left_open_event = self._check_left_open(ts)
        return StateOutput(transition_event, left_open_event)

    def _check_left_open(self, ts: float) -> str | None:
        if self.state != ZoneState.OPEN:
            return None
        if self._open_since is None:
            self._open_since = ts
            return None
        if self._left_open_emitted:
            return None
        if (ts - self._open_since) >= self.left_open_seconds:
            self._left_open_emitted = True
            return self.left_open_event_name
        return None
