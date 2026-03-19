"""Disaster response task models - extracted from scenario events."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"          # イベント未付与、タスクまだ発生していない
    ACTIVE = "active"            # イベント付与済、対応待ち
    IN_PROGRESS = "in_progress"  # 対応中（参加者が言及した）
    COMPLETED = "completed"      # 完了
    OVERDUE = "overdue"          # 対応期限超過
    SKIPPED = "skipped"          # スキップされた


class TaskPriority(str, Enum):
    CRITICAL = "critical"   # 人命に関わる
    HIGH = "high"           # 緊急対応が必要
    MEDIUM = "medium"       # 重要だが猶予あり
    LOW = "low"             # 余裕がある


class DisasterTask(BaseModel):
    """A disaster response task derived from a scenario event's expected actions."""

    task_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    event_id: str = Field(description="元のシナリオイベントID")
    title: str = Field(description="タスクの簡潔な説明")
    description: str = Field(default="", description="詳細")
    responsible_role: str = Field(default="", description="担当部署 (AgentRole value)")
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM

    # Timing
    sim_time_created: str = Field(default="", description="タスク発生時刻 (HH:MM)")
    sim_time_due: str = Field(default="", description="対応期限 (HH:MM)")
    sim_time_completed: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    # Tracking
    assigned_to: str = Field(default="", description="実際の対応者")
    notes: str = Field(default="", description="進捗メモ")
    score: int | None = None  # 1-5 evaluation


def extract_tasks_from_event(
    event_id: str,
    sim_time: str,
    expected_actions: str,
    training_objective: str,
    source: str,
    target_agent: str,
) -> list[DisasterTask]:
    """Extract individual tasks from an event's expected_actions field.

    The expected_actions field typically contains numbered items like:
    1. 消防局に現場確認と安全確保を指示する
    2. 建設部に倒木除去を指示する
    3. 電力会社への連絡を総務部に指示する
    """
    tasks = []
    if not expected_actions:
        return tasks

    # Split by numbered lines or newlines
    lines = expected_actions.replace("、", "\n").split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove leading numbers like "1. " or "1、" or "① "
        cleaned = line.lstrip("0123456789.、①②③④⑤⑥⑦⑧⑨⑩・- ）)").strip()
        if not cleaned or len(cleaned) < 3:
            continue

        # Detect responsible role from text
        responsible = target_agent
        role_keywords = {
            "消防": "shoubou",
            "建設": "kensetsu",
            "福祉": "fukushi",
            "総務": "soumu",
        }
        for keyword, role_val in role_keywords.items():
            if keyword in cleaned:
                responsible = role_val
                break

        # Detect priority from keywords
        priority = TaskPriority.MEDIUM
        if any(w in cleaned for w in ["救助", "救急", "人命", "孤立", "要配慮者"]):
            priority = TaskPriority.CRITICAL
        elif any(w in cleaned for w in ["避難指示", "避難所開設", "通行止め", "交通規制"]):
            priority = TaskPriority.HIGH
        elif any(w in cleaned for w in ["監視", "記録", "報告"]):
            priority = TaskPriority.LOW

        tasks.append(DisasterTask(
            event_id=event_id,
            title=cleaned,
            description=f"狙い: {training_objective}" if training_objective else "",
            responsible_role=responsible,
            priority=priority,
            sim_time_created=sim_time,
        ))

    return tasks
