"""Scenario revision tracking - records all changes to scenario events."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ScenarioRevision(BaseModel):
    """A single revision record for a scenario event."""

    revision_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    event_id: str = Field(description="変更対象のイベントID")
    revision_number: int = Field(description="何回目の変更か (1-based)")
    timestamp: datetime = Field(default_factory=datetime.now)
    sim_time: str = Field(default="", description="変更時の訓練時刻")

    # What triggered this revision
    trigger: str = Field(
        description="変更のトリガー",
        # Types: "participant_action", "omission", "escalation",
        #        "mitigation", "dynamic_event", "manual"
    )
    trigger_detail: str = Field(default="", description="トリガーの詳細")

    # What changed
    field_name: str = Field(description="変更されたフィールド名")
    original_value: str = Field(default="", description="オリジナルの値")
    new_value: str = Field(default="", description="変更後の値")

    # Why
    reason: str = Field(default="", description="変更理由")
    agent_explanation: str = Field(default="", description="AIエージェントの説明")


class EventRevisionHistory(BaseModel):
    """All revisions for a single event."""

    event_id: str
    original_snapshot: dict = Field(default_factory=dict, description="元のイベント内容のスナップショット")
    revisions: list[ScenarioRevision] = Field(default_factory=list)
    is_dynamic: bool = Field(default=False, description="動的に生成されたイベントか")

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    @property
    def is_modified(self) -> bool:
        return len(self.revisions) > 0
