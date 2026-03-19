"""Simulation clock - event-driven with configurable interval between events."""

import asyncio
from datetime import datetime, timedelta

from src.models.enums import DifficultyLevel


# Default interval between events (real seconds)
DEFAULT_EVENT_INTERVALS: dict[DifficultyLevel, float] = {
    DifficultyLevel.BEGINNER: 60.0,      # 60 seconds between events
    DifficultyLevel.INTERMEDIATE: 30.0,  # 30 seconds
    DifficultyLevel.ADVANCED: 15.0,      # 15 seconds
}


class SimulationClock:
    """Event-driven simulation clock with configurable interval.

    Instead of continuous time compression, the clock advances to the next
    event's scheduled time after a configurable real-time interval.

    This gives participants a fixed amount of real time to respond to each event,
    regardless of the gap between scenario timestamps.
    """

    def __init__(
        self,
        sim_start_time: str = "06:00",
        event_interval_seconds: float = 30.0,
    ):
        h, m = map(int, sim_start_time.split(":"))
        today = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        self._sim_start = today
        self._current_sim_time = today
        self._real_start: datetime | None = None
        self._event_interval = event_interval_seconds
        self._paused = False
        self._running = False

    @classmethod
    def from_difficulty(
        cls,
        difficulty: DifficultyLevel,
        sim_start_time: str = "06:00",
        event_interval_seconds: float | None = None,
    ):
        interval = event_interval_seconds or DEFAULT_EVENT_INTERVALS[difficulty]
        return cls(sim_start_time=sim_start_time, event_interval_seconds=interval)

    def start(self):
        self._real_start = datetime.now()
        self._running = True

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def current_sim_time(self) -> datetime:
        return self._current_sim_time

    @property
    def sim_time_str(self) -> str:
        return self._current_sim_time.strftime("%H:%M")

    @property
    def event_interval(self) -> float:
        return self._event_interval

    @event_interval.setter
    def event_interval(self, seconds: float):
        self._event_interval = max(1.0, seconds)

    @property
    def elapsed_real_minutes(self) -> float:
        if not self._real_start:
            return 0.0
        return (datetime.now() - self._real_start).total_seconds() / 60

    def advance_to(self, sim_time_str: str):
        """Advance simulation time to a specific HH:MM."""
        h, m = map(int, sim_time_str.split(":"))
        self._current_sim_time = self._current_sim_time.replace(hour=h, minute=m, second=0)

    def advance_by_minutes(self, minutes: int):
        """Advance simulation time by N minutes."""
        self._current_sim_time += timedelta(minutes=minutes)

    def pause(self) -> bool:
        """Pause the simulation. Always allowed at any difficulty."""
        if not self._running or self._paused:
            return False
        self._paused = True
        return True

    def resume(self) -> bool:
        if not self._paused:
            return False
        self._paused = False
        return True

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self):
        self._running = False

    def has_reached(self, sim_time_str: str) -> bool:
        """Check if simulation has reached the given time (HH:MM)."""
        h, m = map(int, sim_time_str.split(":"))
        target = self._sim_start.replace(hour=h, minute=m, second=0)
        return self._current_sim_time >= target

    async def wait_interval(self):
        """Wait for the configured event interval (real seconds).
        Checks pause state every 0.5s so pause is responsive.
        """
        elapsed = 0.0
        while elapsed < self._event_interval:
            if not self._running:
                return
            if self._paused:
                await asyncio.sleep(0.5)
                continue  # Don't count paused time
            await asyncio.sleep(0.5)
            elapsed += 0.5
