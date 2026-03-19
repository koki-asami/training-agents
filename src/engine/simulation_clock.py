"""Simulation clock - scenario-interval-based time progression."""

import asyncio
from datetime import datetime, timedelta

from src.models.enums import DifficultyLevel


# How many real seconds correspond to 1 scenario-minute, by difficulty
# e.g., BEGINNER: 1 scenario-minute = 15 real seconds
DEFAULT_SECONDS_PER_SIM_MINUTE: dict[DifficultyLevel, float] = {
    DifficultyLevel.BEGINNER: 15.0,
    DifficultyLevel.INTERMEDIATE: 8.0,
    DifficultyLevel.ADVANCED: 4.0,
}

# Minimum real wait even for simultaneous events (0-minute gap)
MIN_WAIT_SECONDS = 2.0


class SimulationClock:
    """Scenario-interval-based simulation clock.

    Time progression follows the actual intervals between events in the
    uploaded scenario. The real wait time is proportional to the scenario
    time gap, scaled by `seconds_per_sim_minute`.

    Example with seconds_per_sim_minute=8:
      - Scenario gap 0 min (simultaneous) -> wait 2 sec (MIN_WAIT)
      - Scenario gap 2 min -> wait 16 sec
      - Scenario gap 4 min -> wait 32 sec

    The scale factor can be adjusted at runtime via the UI.
    """

    def __init__(
        self,
        sim_start_time: str = "06:00",
        seconds_per_sim_minute: float = 8.0,
    ):
        h, m = map(int, sim_start_time.split(":"))
        today = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        self._sim_start = today
        self._current_sim_time = today
        self._real_start: datetime | None = None
        self._seconds_per_sim_minute = seconds_per_sim_minute
        self._paused = False
        self._running = False

    @classmethod
    def from_difficulty(
        cls,
        difficulty: DifficultyLevel,
        sim_start_time: str = "06:00",
        seconds_per_sim_minute: float | None = None,
    ):
        scale = seconds_per_sim_minute or DEFAULT_SECONDS_PER_SIM_MINUTE[difficulty]
        return cls(sim_start_time=sim_start_time, seconds_per_sim_minute=scale)

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
    def seconds_per_sim_minute(self) -> float:
        return self._seconds_per_sim_minute

    @seconds_per_sim_minute.setter
    def seconds_per_sim_minute(self, value: float):
        self._seconds_per_sim_minute = max(0.5, value)

    # Keep backward compat with existing code that uses event_interval
    @property
    def event_interval(self) -> float:
        return self._seconds_per_sim_minute

    @event_interval.setter
    def event_interval(self, seconds: float):
        self._seconds_per_sim_minute = max(0.5, seconds)

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
        self._current_sim_time += timedelta(minutes=minutes)

    def pause(self) -> bool:
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
        h, m = map(int, sim_time_str.split(":"))
        target = self._sim_start.replace(hour=h, minute=m, second=0)
        return self._current_sim_time >= target

    def calc_wait_seconds(self, from_time: str, to_time: str) -> float:
        """Calculate real wait seconds based on scenario time gap.

        Args:
            from_time: Current event time (HH:MM)
            to_time: Next event time (HH:MM)

        Returns:
            Real seconds to wait, at least MIN_WAIT_SECONDS.
        """
        h1, m1 = map(int, from_time.split(":"))
        h2, m2 = map(int, to_time.split(":"))
        gap_minutes = (h2 * 60 + m2) - (h1 * 60 + m1)

        if gap_minutes <= 0:
            return MIN_WAIT_SECONDS

        return max(MIN_WAIT_SECONDS, gap_minutes * self._seconds_per_sim_minute)

    async def wait_for_gap(self, from_time: str, to_time: str):
        """Wait proportional to the scenario time gap. Respects pause."""
        total = self.calc_wait_seconds(from_time, to_time)
        elapsed = 0.0
        while elapsed < total:
            if not self._running:
                return
            if self._paused:
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0.5)
            elapsed += 0.5

    async def wait_interval(self):
        """Backward-compat: wait a fixed interval."""
        await self.wait_for_gap("00:00", f"00:{int(self._seconds_per_sim_minute):02d}")
