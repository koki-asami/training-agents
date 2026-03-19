"""Message models for inter-agent and human-agent communication."""


from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import MessageType


class SimulationMessage(BaseModel):
    """A message exchanged between agents or between agents and humans."""

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now, description="Real time")
    sim_time: datetime | None = Field(default=None, description="Simulation time")
    sender: str = Field(description="AgentRole value or 'human:{participant_id}'")
    receiver: str = Field(description="AgentRole value, 'human:{participant_id}', or 'broadcast'")
    content: str
    message_type: MessageType = MessageType.REPORT
    related_event_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def is_from_human(self) -> bool:
        return self.sender.startswith("human:")

    @property
    def is_to_human(self) -> bool:
        return self.receiver.startswith("human:") or self.receiver == "broadcast"
