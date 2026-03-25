"""Scenario data models - maps to training-scenario-generator output."""

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import AgentRole, DifficultyLevel


class ScenarioEvent(BaseModel):
    """A single scenario event (状況付与) from the training-scenario-generator."""

    event_id: str = Field(description="状況付与番号 (e.g., '2-1', '3')")
    title: str = Field(description="付与内容")
    date: str = Field(default="", description="日付 (e.g., '５月２１日')")
    scheduled_time: str = Field(description="時刻 (HH:MM format)")
    source: str = Field(description="情報源 (住民, 消防, etc.)")
    content_admin: str = Field(description="内容_管理用詳細")
    content_trainee: str = Field(description="内容_訓練者向け")
    training_objective: str = Field(default="", description="狙い")
    training_effect: str = Field(default="", description="訓練の効果")
    expected_actions: str = Field(default="", description="期待される対応行動")
    expected_issues: str = Field(default="", description="想定される課題")
    terrain_info: str = Field(default="", description="地形情報や想定される被害の特徴")
    water_level_status: str = Field(default="", description="水位状況")
    secondary_disaster_risks: str = Field(default="", description="想定される二次災害のリスク")

    # Context fields from Excel (気象情報・河川情報 columns)
    weather_info: str = Field(default="", description="気象情報（その時点での気象状況）")
    river_info: str = Field(default="", description="河川情報（その時点での河川状況）")

    # Responsible department (対応部署) - who handles this event
    responsible_department: str = Field(default="", description="対応部署 (総務部, 消防局, etc.)")

    # Derived/runtime fields
    target_agent: AgentRole = AgentRole.GENERAL_AFFAIRS
    response_window_minutes: int = Field(default=10, description="Expected response time window")
    injected: bool = False
    injected_at: datetime | None = None
    response_received: bool = False
    response_at: datetime | None = None


class TrainingLevelInfo(BaseModel):
    """訓練レベル情報 sheet data."""

    training_level: str = Field(default="", description="訓練レベル")
    objective: str = Field(default="", description="狙い")
    response_guidelines: str = Field(default="", description="想定のレベル及び応答要領")
    event_count: int = Field(default=0, description="状況付与数")
    related_agencies: str = Field(default="", description="関係機関")


class ScenarioConfig(BaseModel):
    """Configuration for a training scenario."""

    municipality: str = Field(description="市町村名")
    municipality_en: str = Field(default="")
    training_level: str = Field(default="指揮判断", description="訓練レベル")
    training_level_info: TrainingLevelInfo | None = Field(
        default=None, description="訓練レベル詳細情報"
    )
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    geojson_path: str = Field(default="", description="Path to enhanced GeoJSON")
    geojson_data: str = Field(default="", description="Inline GeoJSON from 地理情報 sheet")
    events: list[ScenarioEvent] = Field(default_factory=list)
    alert_timeline: list[dict] = Field(
        default_factory=list, description="Weather alert progression timeline"
    )
    time_compression_ratio: float = Field(default=3.0, description="sim_minutes per real_minute")
    sim_start_time: str = Field(default="06:00", description="Simulation start (HH:MM)")
    sim_end_time: str = Field(default="18:00", description="Simulation end (HH:MM)")
    description: str = Field(default="豪雨災害対応訓練")
