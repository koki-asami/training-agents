"""WebSocket endpoint for real-time simulation communication."""

import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.models.enums import AgentRole, ROLE_DISPLAY_NAMES

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per session."""

    def __init__(self):
        # session_id -> {participant_id -> WebSocket}
        self.connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, session_id: str, participant_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.connections:
            self.connections[session_id] = {}
        self.connections[session_id][participant_id] = websocket
        logger.info("ws_connected", session_id=session_id, participant_id=participant_id)

    def disconnect(self, session_id: str, participant_id: str):
        if session_id in self.connections:
            self.connections[session_id].pop(participant_id, None)
        logger.info("ws_disconnected", session_id=session_id, participant_id=participant_id)

    async def send_to_participant(self, session_id: str, participant_id: str, data: dict):
        ws = self.connections.get(session_id, {}).get(participant_id)
        if ws:
            await ws.send_json(data)

    async def broadcast_to_session(self, session_id: str, data: dict):
        for ws in self.connections.get(session_id, {}).values():
            await ws.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/simulation/{session_id}/{participant_id}")
async def websocket_simulation(
    websocket: WebSocket, session_id: str, participant_id: str
):
    """WebSocket endpoint for a participant in a simulation session.

    Messages from client:
    - {"type": "message", "content": "...", "target_role": "shoubou"}  # Send to specific role
    - {"type": "message", "content": "...", "target_role": "broadcast"}  # Send to all
    - {"type": "command", "action": "pause"}
    - {"type": "command", "action": "resume"}

    Messages to client:
    - {"type": "message", "sender": "shoubou", "sender_name": "消防局", "content": "...", "sim_time": "..."}
    - {"type": "state_update", "state": {...}}
    - {"type": "score", "event_id": "...", "score": 4, "notes": "..."}
    - {"type": "system", "content": "..."}
    """
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        await websocket.close(code=4004, reason="Session not found")
        return

    # Verify participant
    participant = next(
        (p for p in runner.session.participants if p.participant_id == participant_id),
        None,
    )
    if not participant:
        await websocket.close(code=4003, reason="Participant not found")
        return

    await manager.connect(session_id, participant_id, websocket)
    participant.connected = True

    # Set up callbacks for the runner
    async def on_message(msg_data: dict):
        """Route simulation messages to appropriate WebSocket connections."""
        receiver = msg_data.get("receiver", "")
        sender = msg_data.get("sender", "")

        # Resolve sender display name
        metadata = msg_data.get("metadata", {})
        sender_name = sender
        # Use source name if present in metadata (e.g., "住民", "警察(110番)")
        source = metadata.get("source", "")
        if source:
            sender_name = source
        else:
            for role in AgentRole:
                if role.value == sender:
                    names = ROLE_DISPLAY_NAMES.get(role)
                    if names:
                        sender_name = names[0]  # Japanese name
                    break

        ws_data = {
            "type": "message",
            "sender": sender,
            "sender_name": sender_name,
            "content": msg_data.get("content", ""),
            "sim_time": msg_data.get("sim_time", ""),
            "message_type": msg_data.get("message_type", "report"),
            "related_event_id": msg_data.get("related_event_id"),
            "source": source,
            "responsible_department": metadata.get("responsible_department", ""),
        }

        if receiver == "broadcast" or receiver == f"human:{participant_id}":
            await manager.send_to_participant(session_id, participant_id, ws_data)
        elif receiver.startswith("human:"):
            target_pid = receiver.replace("human:", "")
            await manager.send_to_participant(session_id, target_pid, ws_data)

    async def on_state_change(state_summary: dict):
        await manager.broadcast_to_session(
            session_id, {"type": "state_update", "state": state_summary}
        )

    runner.set_message_callback(on_message)
    runner.set_state_change_callback(on_state_change)

    # Send initial state
    await websocket.send_json(
        {
            "type": "system",
            "content": f"接続しました。役割: {ROLE_DISPLAY_NAMES.get(participant.role, ('', ''))[0]}",
        }
    )
    await websocket.send_json(
        {"type": "state_update", "state": runner.state_manager.get_state_summary()}
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "")
                target_role_str = data.get("target_role", "broadcast")

                target_role = None
                if target_role_str != "broadcast":
                    try:
                        target_role = AgentRole(target_role_str)
                    except ValueError:
                        await websocket.send_json(
                            {"type": "error", "content": f"Unknown role: {target_role_str}"}
                        )
                        continue

                # Process the human message
                responses = await runner.handle_human_message(
                    participant_id=participant_id,
                    role=participant.role,
                    content=content,
                    target_role=target_role,
                )

                # Send responses back
                for resp in responses:
                    sender_name = resp.sender
                    for role in AgentRole:
                        if role.value == resp.sender:
                            names = ROLE_DISPLAY_NAMES.get(role)
                            if names:
                                sender_name = names[0]
                            break

                    await websocket.send_json(
                        {
                            "type": "message",
                            "sender": resp.sender,
                            "sender_name": sender_name,
                            "content": resp.content,
                            "sim_time": resp.sim_time.strftime("%H:%M") if resp.sim_time else "",
                            "message_type": resp.message_type.value,
                        }
                    )

            elif msg_type == "command":
                action = data.get("action")
                if action == "pause":
                    runner.clock.pause()
                elif action == "resume":
                    runner.clock.resume()

    except WebSocketDisconnect:
        manager.disconnect(session_id, participant_id)
        participant.connected = False
