"""Simulation clock - manages real-time to simulation-time mapping."""


import asyncio
from datetime import datetime, timedelta

from src.models.enums import DifficultyLevel


# Time compression ratios by difficulty
DIFFICULTY_RATIOS: dict[DifficultyLevel, float] = {
    DifficultyLevel.BEGINNER: 2.0,
    DifficultyLevel.INTERMEDIATE: 3.0,
    DifficultyLevel.ADVANCED: 4.0,
}


class SimulationClock:
    """Maps real time to simulation time with configurable compression.

    For a 3:1 ratio: 1 real minute = 3 simulated minutes.
    A 12-hour simulated disaster runs in 4 real hours.
    """

    def __init__(
        self,
        sim_start_time: str = "06:00",
        ratio: float = 3.0,
        allow_pause: bool = False,
    ):
        h, m = map(int, sim_start_time.split(":"))
        today = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        self._sim_start = today
        self._real_start: datetime | None = None
        self._ratio = ratio
        self._allow_pause = allow_pause
        self._paused = False
        self._paused_at: datetime | None = None
        self._total_paused_seconds: float = 0.0
        self._running = False

    @classmethod
    def from_difficulty(cls, difficulty: DifficultyLevel, sim_start_time: str = "06:00"):
        ratio = DIFFICULTY_RATIOS[difficulty]
        allow_pause = difficulty == DifficultyLevel.BEGINNER
        return cls(sim_start_time=sim_start_time, ratio=ratio, allow_pause=allow_pause)

    def start(self):
        self._real_start = datetime.now()
        self._running = True

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def current_sim_time(self) -> datetime:
        if not self._real_start:
            return self._sim_start

        real_elapsed = (datetime.now() - self._real_start).total_seconds()
        real_elapsed -= self._total_paused_seconds
        if self._paused and self._paused_at:
            real_elapsed -= (datetime.now() - self._paused_at).total_seconds()

        sim_elapsed_seconds = real_elapsed * self._ratio
        return self._sim_start + timedelta(seconds=sim_elapsed_seconds)

    @property
    def sim_time_str(self) -> str:
        return self.current_sim_time.strftime("%H:%M")

    @property
    def elapsed_real_minutes(self) -> float:
        if not self._real_start:
            return 0.0
        return (datetime.now() - self._real_start).total_seconds() / 60

    def pause(self) -> bool:
        if not self._allow_pause or self._paused:
            return False
        self._paused = True
        self._paused_at = datetime.now()
        return True

    def resume(self) -> bool:
        if not self._paused or not self._paused_at:
            return False
        self._total_paused_seconds += (datetime.now() - self._paused_at).total_seconds()
        self._paused = False
        self._paused_at = None
        return True

    def stop(self):
        self._running = False

    def has_reached(self, sim_time_str: str) -> bool:
        """Check if simulation has reached the given time (HH:MM)."""
        h, m = map(int, sim_time_str.split(":"))
        target = self._sim_start.replace(hour=h, minute=m, second=0)
        return self.current_sim_time >= target

    def sim_time_to_real_wait(self, sim_time_str: str) -> float:
        """How many real seconds until simulation reaches the given time."""
        h, m = map(int, sim_time_str.split(":"))
        target = self._sim_start.replace(hour=h, minute=m, second=0)
        sim_remaining = (target - self.current_sim_time).total_seconds()
        if sim_remaining <= 0:
            return 0.0
        return sim_remaining / self._ratio

    async def wait_until(self, sim_time_str: str):
        """Async wait until simulation reaches the given time."""
        wait_seconds = self.sim_time_to_real_wait(sim_time_str)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
