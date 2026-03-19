"""Event scheduler - manages the timed delivery of scenario events."""


import heapq
from datetime import datetime

import structlog

from src.models.scenario import ScenarioEvent

logger = structlog.get_logger()


class EventScheduler:
    """Priority queue of scenario events, dispatched based on simulation clock.

    Events are ordered by scheduled_time (HH:MM).
    The scheduler checks the clock and yields events whose time has been reached.
    """

    def __init__(self):
        # Use a monotonic sequence to avoid comparing ScenarioEvent objects when
        # multiple events share the same scheduled_time.
        self._queue: list[tuple[str, int, ScenarioEvent]] = []
        self._injected_events: list[ScenarioEvent] = []
        self._pending_dynamic: list[ScenarioEvent] = []
        self._seq = 0

    def load_events(self, events: list[ScenarioEvent]):
        """Load pre-generated scenario events into the queue."""
        self._seq = 0
        self._queue = []
        for e in events:
            self._seq += 1
            self._queue.append((e.scheduled_time, self._seq, e))
        heapq.heapify(self._queue)
        logger.info("events_loaded", count=len(events))

    def add_dynamic_event(self, event: ScenarioEvent):
        """Add a dynamically generated event to the queue."""
        self._seq += 1
        heapq.heappush(self._queue, (event.scheduled_time, self._seq, event))
        self._pending_dynamic.append(event)
        logger.info(
            "dynamic_event_added",
            event_id=event.event_id,
            time=event.scheduled_time,
        )

    def get_due_events(self, current_sim_time_str: str) -> list[ScenarioEvent]:
        """Get all events whose scheduled time has been reached.

        Args:
            current_sim_time_str: Current simulation time in HH:MM format.
        """
        due = []
        while self._queue and self._queue[0][0] <= current_sim_time_str:
            time_str, _seq, event = heapq.heappop(self._queue)
            if not event.injected:
                event.injected = True
                event.injected_at = datetime.now()
                due.append(event)
                self._injected_events.append(event)

        return due

    def peek_next_event_time(self) -> str | None:
        """Return the scheduled time of the next event, or None if empty."""
        if self._queue:
            return self._queue[0][0]
        return None

    @property
    def remaining_count(self) -> int:
        return len(self._queue)

    @property
    def injected_count(self) -> int:
        return len(self._injected_events)

    def get_injected_events(self) -> list[ScenarioEvent]:
        return self._injected_events

    def get_unresponded_events(self) -> list[ScenarioEvent]:
        """Get events that were injected but haven't received a response."""
        return [e for e in self._injected_events if not e.response_received]
