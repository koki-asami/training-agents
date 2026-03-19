"""Session models for managing training simulation sessions."""


from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import AgentRole, SimulationPhase
from .messages import SimulationMessage
from .scenario import ScenarioConfig
from .scoring import EventScore
from .state import DisasterState


class Participant(BaseModel):
    """A human participant in the simulation."""

    participant_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    role: AgentRole
    connected: bool = False
    websocket_id: str | None = None


class AgentAssignment(BaseModel):
    """Assignment of a role to either AI or human."""

    role: AgentRole
    is_human: bool = False
    participant_id: str | None = None  # Set if is_human
    agent_instance_id: str | None = None  # Set if AI, unique per resident


class SimulationSession(BaseModel):
    """A complete training simulation session."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    config: ScenarioConfig
    state: DisasterState | None = None
    assignments: list[AgentAssignment] = Field(default_factory=list)
    participants: list[Participant] = Field(default_factory=list)
    messages: list[SimulationMessage] = Field(default_factory=list)
    scores: list[EventScore] = Field(default_factory=list)
    phase: SimulationPhase = SimulationPhase.SETUP

    def get_human_roles(self) -> list[AgentRole]:
        return [a.role for a in self.assignments if a.is_human]

    def get_ai_roles(self) -> list[AgentRole]:
        return [a.role for a in self.assignments if not a.is_human]

    def get_participant_for_role(self, role: AgentRole) -> Participant | None:
        assignment = next((a for a in self.assignments if a.role == role and a.is_human), None)
        if assignment and assignment.participant_id:
            return next(
                (p for p in self.participants if p.participant_id == assignment.participant_id),
                None,
            )
        return None
