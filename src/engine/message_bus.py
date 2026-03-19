"""Message bus for inter-agent and human-agent communication routing."""


import asyncio
from collections import defaultdict
from datetime import datetime

import structlog

from src.models.enums import AgentRole
from src.models.messages import SimulationMessage

logger = structlog.get_logger()


class MessageBus:
    """Routes messages between agents and human participants.

    Each agent/participant subscribes to a queue keyed by their role or ID.
    Messages can be sent to specific roles, participant IDs, or broadcast.
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._history: list[SimulationMessage] = []
        self._broadcast_listeners: list[asyncio.Queue] = []

    def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        """Subscribe to receive messages. subscriber_id is AgentRole value or participant_id."""
        if subscriber_id not in self._queues:
            self._queues[subscriber_id] = asyncio.Queue()
        return self._queues[subscriber_id]

    def subscribe_broadcast(self) -> asyncio.Queue:
        """Subscribe to receive all broadcast messages."""
        q: asyncio.Queue = asyncio.Queue()
        self._broadcast_listeners.append(q)
        return q

    def unsubscribe(self, subscriber_id: str):
        self._queues.pop(subscriber_id, None)

    async def send(self, message: SimulationMessage):
        """Send a message to a specific receiver or broadcast."""
        self._history.append(message)
        logger.debug(
            "message_sent",
            sender=message.sender,
            receiver=message.receiver,
            type=message.message_type,
        )

        if message.receiver == "broadcast":
            # Send to all subscribers
            for q in self._queues.values():
                await q.put(message)
            for q in self._broadcast_listeners:
                await q.put(message)
        else:
            # Send to specific receiver
            if message.receiver in self._queues:
                await self._queues[message.receiver].put(message)
            # Also notify broadcast listeners
            for q in self._broadcast_listeners:
                await q.put(message)

    async def send_to_role(
        self,
        sender: str,
        role: AgentRole,
        content: str,
        sim_time: datetime | None = None,
        message_type: str = "report",
        related_event_id: str | None = None,
    ) -> SimulationMessage:
        """Convenience method to send a message to a specific role."""
        msg = SimulationMessage(
            sender=sender,
            receiver=role.value,
            content=content,
            sim_time=sim_time,
            message_type=message_type,
            related_event_id=related_event_id,
        )
        await self.send(msg)
        return msg

    async def broadcast(
        self,
        sender: str,
        content: str,
        sim_time: datetime | None = None,
        message_type: str = "alert",
    ) -> SimulationMessage:
        """Send a message to all participants."""
        msg = SimulationMessage(
            sender=sender,
            receiver="broadcast",
            content=content,
            sim_time=sim_time,
            message_type=message_type,
        )
        await self.send(msg)
        return msg

    def get_history(
        self,
        sender: str | None = None,
        receiver: str | None = None,
        limit: int | None = None,
    ) -> list[SimulationMessage]:
        """Get message history with optional filters."""
        msgs = self._history
        if sender:
            msgs = [m for m in msgs if m.sender == sender]
        if receiver:
            msgs = [m for m in msgs if m.receiver == receiver or m.receiver == "broadcast"]
        if limit:
            msgs = msgs[-limit:]
        return msgs

    def get_conversation(self, role_a: str, role_b: str) -> list[SimulationMessage]:
        """Get conversation between two roles/participants."""
        return [
            m
            for m in self._history
            if (m.sender == role_a and m.receiver == role_b)
            or (m.sender == role_b and m.receiver == role_a)
            or m.receiver == "broadcast"
        ]
