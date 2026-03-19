"""Load scenarios from training-scenario-generator output (Excel/JSON)."""


import json
from pathlib import Path

import structlog

from src.models.enums import SOURCE_TO_AGENT, AgentRole, DifficultyLevel
from src.models.scenario import ScenarioConfig, ScenarioEvent

logger = structlog.get_logger()

# Column name mapping from training-scenario-generator Excel output
EXCEL_COLUMN_MAP = {
    "付与番号": "event_id",
    "付与内容": "title",
    "時間": "scheduled_time",
    "情報源": "source",
    "内容_管理用詳細": "content_admin",
    "内容_訓練者向け": "content_trainee",
    "狙い": "training_objective",
    "訓練の効果": "training_effect",
    "期待される対応行動": "expected_actions",
    "想定される課題": "expected_issues",
    "地形情報や想定される被害の特徴": "terrain_info",
    "水位状況": "water_level_status",
    "想定される二次災害のリスク": "secondary_disaster_risks",
}

# Response window adjustments by difficulty
RESPONSE_WINDOW_MULTIPLIERS = {
    DifficultyLevel.BEGINNER: 2.0,
    DifficultyLevel.INTERMEDIATE: 1.0,
    DifficultyLevel.ADVANCED: 0.75,
}


def _resolve_target_agent(source: str) -> AgentRole:
    """Map 情報源 to the agent that originates this event."""
    for key, role in SOURCE_TO_AGENT.items():
        if key in source:
            return role
    return AgentRole.GENERAL_AFFAIRS


def load_scenario_from_json(path: str | Path, difficulty: DifficultyLevel) -> ScenarioConfig:
    """Load a scenario from a JSON file."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = []
    response_multiplier = RESPONSE_WINDOW_MULTIPLIERS[difficulty]

    for item in data.get("events", data if isinstance(data, list) else []):
        event = ScenarioEvent(
            event_id=str(item.get("付与番号", item.get("event_id", ""))),
            title=item.get("付与内容", item.get("title", "")),
            scheduled_time=item.get("時間", item.get("scheduled_time", "00:00")),
            source=item.get("情報源", item.get("source", "")),
            content_admin=item.get("内容_管理用詳細", item.get("content_admin", "")),
            content_trainee=item.get("内容_訓練者向け", item.get("content_trainee", "")),
            training_objective=item.get("狙い", item.get("training_objective", "")),
            training_effect=item.get("訓練の効果", item.get("training_effect", "")),
            expected_actions=item.get("期待される対応行動", item.get("expected_actions", "")),
            expected_issues=item.get("想定される課題", item.get("expected_issues", "")),
            terrain_info=item.get(
                "地形情報や想定される被害の特徴", item.get("terrain_info", "")
            ),
            water_level_status=item.get("水位状況", item.get("water_level_status", "")),
            secondary_disaster_risks=item.get(
                "想定される二次災害のリスク", item.get("secondary_disaster_risks", "")
            ),
            response_window_minutes=int(10 * response_multiplier),
        )
        event.target_agent = _resolve_target_agent(event.source)
        events.append(event)

    # Sort by scheduled time
    events.sort(key=lambda e: e.scheduled_time)

    config = ScenarioConfig(
        municipality=data.get("municipality", path.stem),
        difficulty=difficulty,
        events=events,
        alert_timeline=data.get("alert_timeline", []),
    )

    logger.info("scenario_loaded", path=str(path), event_count=len(events))
    return config


def load_scenario_from_excel(
    path: str | Path, difficulty: DifficultyLevel
) -> ScenarioConfig:
    """Load a scenario from an Excel file (training-scenario-generator output)."""
    import openpyxl

    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    # Read headers from first row
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    events = []
    response_multiplier = RESPONSE_WINDOW_MULTIPLIERS[difficulty]

    for row in ws.iter_rows(min_row=2, values_only=True):
        row_data = dict(zip(headers, row))
        if not row_data.get("付与番号") and not row_data.get("event_id"):
            continue

        event = ScenarioEvent(
            event_id=str(row_data.get("付与番号", row_data.get("event_id", ""))),
            title=str(row_data.get("付与内容", row_data.get("title", ""))),
            scheduled_time=str(row_data.get("時間", row_data.get("scheduled_time", "00:00"))),
            source=str(row_data.get("情報源", row_data.get("source", ""))),
            content_admin=str(
                row_data.get("内容_管理用詳細", row_data.get("content_admin", ""))
            ),
            content_trainee=str(
                row_data.get("内容_訓練者向け", row_data.get("content_trainee", ""))
            ),
            training_objective=str(
                row_data.get("狙い", row_data.get("training_objective", ""))
            ),
            expected_actions=str(
                row_data.get("期待される対応行動", row_data.get("expected_actions", ""))
            ),
            expected_issues=str(
                row_data.get("想定される課題", row_data.get("expected_issues", ""))
            ),
            terrain_info=str(
                row_data.get(
                    "地形情報や想定される被害の特徴", row_data.get("terrain_info", "")
                )
            ),
            water_level_status=str(
                row_data.get("水位状況", row_data.get("water_level_status", ""))
            ),
            secondary_disaster_risks=str(
                row_data.get(
                    "想定される二次災害のリスク",
                    row_data.get("secondary_disaster_risks", ""),
                )
            ),
            response_window_minutes=int(10 * response_multiplier),
        )
        event.target_agent = _resolve_target_agent(event.source)
        events.append(event)

    wb.close()
    events.sort(key=lambda e: e.scheduled_time)

    config = ScenarioConfig(
        municipality=path.stem.split("_")[0] if "_" in path.stem else path.stem,
        difficulty=difficulty,
        events=events,
    )

    logger.info("scenario_loaded_excel", path=str(path), event_count=len(events))
    return config
