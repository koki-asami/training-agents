"""Scoring models for trainee evaluation."""

from datetime import datetime

from pydantic import BaseModel, Field


class EventScore(BaseModel):
    """Score for a single scenario event response."""

    event_id: str
    participant_id: str  # Which human participant was scored
    score: int = Field(ge=1, le=5, description="1-5 score")
    response_time_minutes: float
    action_taken: str
    expected_action: str
    evaluation_notes: str
    timestamp: datetime = Field(default_factory=datetime.now)


class CategoryScore(BaseModel):
    """Aggregated score for a scoring category."""

    category: str  # response_time, decision_quality, communication, process_adherence
    score: float = Field(ge=0.0, le=100.0)
    details: str = ""


class SessionScore(BaseModel):
    """Overall session score for a participant."""

    session_id: str
    participant_id: str
    participant_role: str
    overall_score: float = Field(ge=0.0, le=100.0)
    total_events_scored: int = 0
    event_scores: list[EventScore] = Field(default_factory=list)
    category_scores: list[CategoryScore] = Field(default_factory=list)
    response_time_avg_minutes: float = 0.0
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
