"""Difficulty profiles and modifiers for the simulation."""

from dataclasses import dataclass

from src.models.enums import DifficultyLevel


@dataclass
class DifficultyProfile:
    level: DifficultyLevel
    time_compression_ratio: float
    allow_pause: bool
    event_count_target: int  # Approximate number of events
    concurrent_events_max: int
    response_window_multiplier: float  # Applied to base response window
    hint_enabled: bool
    information_quality: str  # clear, mixed, fragmented
    resource_availability: str  # adequate, limited, severe
    resident_cooperation: str  # cooperative, mixed, non_cooperative
    communication_failures: bool
    media_pressure: bool
    description_ja: str


DIFFICULTY_PROFILES: dict[DifficultyLevel, DifficultyProfile] = {
    DifficultyLevel.BEGINNER: DifficultyProfile(
        level=DifficultyLevel.BEGINNER,
        time_compression_ratio=2.0,
        allow_pause=True,
        event_count_target=10,
        concurrent_events_max=1,
        response_window_multiplier=2.0,
        hint_enabled=True,
        information_quality="clear",
        resource_availability="adequate",
        resident_cooperation="cooperative",
        communication_failures=False,
        media_pressure=False,
        description_ja="体制構築訓練（初級）: 明確な情報、十分なリソース、ヒント付き",
    ),
    DifficultyLevel.INTERMEDIATE: DifficultyProfile(
        level=DifficultyLevel.INTERMEDIATE,
        time_compression_ratio=3.0,
        allow_pause=False,
        event_count_target=20,
        concurrent_events_max=3,
        response_window_multiplier=1.0,
        hint_enabled=False,
        information_quality="mixed",
        resource_availability="limited",
        resident_cooperation="mixed",
        communication_failures=False,
        media_pressure=False,
        description_ja="指揮判断訓練（中級）: 一部未確認情報、リソース制約あり",
    ),
    DifficultyLevel.ADVANCED: DifficultyProfile(
        level=DifficultyLevel.ADVANCED,
        time_compression_ratio=4.0,
        allow_pause=False,
        event_count_target=30,
        concurrent_events_max=5,
        response_window_multiplier=0.75,
        hint_enabled=False,
        information_quality="fragmented",
        resource_availability="severe",
        resident_cooperation="non_cooperative",
        communication_failures=True,
        media_pressure=True,
        description_ja="指揮判断訓練（上級）: 断片的情報、深刻なリソース不足、時間切れ判断",
    ),
}
