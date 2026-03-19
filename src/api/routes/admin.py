"""Admin dashboard endpoints - scenario master / controller view."""

import structlog
from fastapi import APIRouter, HTTPException

from src.models.enums import ROLE_DISPLAY_NAMES, AgentRole

logger = structlog.get_logger()

router = APIRouter()


@router.get("/sessions/{session_id}/timeline")
async def get_timeline(session_id: str):
    """Get full event timeline with injection status, responses, and scores.

    Returns all scenario events (base + dynamic) with their current state,
    plus all messages exchanged, ordered chronologically.
    """
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(
        "timeline_requested",
        session_id=session_id,
        total_events=len(runner.config.events),
        phase=runner.session.phase.value,
    )
    # Log first event data for debugging
    if runner.config.events:
        e0 = runner.config.events[0]
        logger.info(
            "timeline_first_event",
            event_id=e0.event_id,
            title=e0.title,
            content_trainee_len=len(e0.content_trainee),
            content_admin_len=len(e0.content_admin),
            content_trainee_preview=e0.content_trainee[:100],
        )

    # Build event timeline
    events_timeline = []
    scores_by_event = {s.event_id: s for s in runner.session.scores}

    for event in runner.config.events:
        score = scores_by_event.get(event.event_id)
        source_name = event.source
        target_name = ROLE_DISPLAY_NAMES.get(event.target_agent, (event.target_agent.value,))[0]

        events_timeline.append({
            "type": "event",
            "event_id": event.event_id,
            "sim_time": event.scheduled_time,
            "title": event.title,
            "source": source_name,
            "target_agent": event.target_agent.value,
            "target_agent_name": target_name,
            "content_trainee": event.content_trainee,
            "content_admin": event.content_admin,
            "expected_actions": event.expected_actions,
            "expected_issues": event.expected_issues,
            "training_objective": event.training_objective,
            "weather_info": event.weather_info,
            "river_info": event.river_info,
            "terrain_info": event.terrain_info,
            "water_level_status": event.water_level_status,
            "secondary_disaster_risks": event.secondary_disaster_risks,
            # Status
            "injected": event.injected,
            "injected_at": event.injected_at.isoformat() if event.injected_at else None,
            "response_received": event.response_received,
            "response_at": event.response_at.isoformat() if event.response_at else None,
            # Score
            "score": score.score if score else None,
            "score_notes": score.evaluation_notes if score else None,
            "response_time_minutes": score.response_time_minutes if score else None,
            "action_taken": score.action_taken if score else None,
            # Revision info
            "is_modified": (
                runner.scenario_updater.get_history(event.event_id).is_modified
                if runner.scenario_updater and runner.scenario_updater.get_history(event.event_id)
                else False
            ),
            "revision_count": (
                runner.scenario_updater.get_history(event.event_id).revision_count
                if runner.scenario_updater and runner.scenario_updater.get_history(event.event_id)
                else 0
            ),
        })

    # Build message timeline
    messages_timeline = []
    for msg in runner.session.messages:
        sender_name = msg.sender
        for role in AgentRole:
            if role.value == msg.sender:
                sender_name = ROLE_DISPLAY_NAMES.get(role, (msg.sender,))[0]
                break
        if msg.sender.startswith("human:"):
            # Find participant name
            pid = msg.sender.replace("human:", "")
            participant = next(
                (p for p in runner.session.participants if p.participant_id == pid), None
            )
            if participant:
                role_name = ROLE_DISPLAY_NAMES.get(participant.role, (participant.role.value,))[0]
                sender_name = f"{participant.name}（{role_name}）"

        messages_timeline.append({
            "type": "message",
            "message_id": msg.message_id,
            "sim_time": msg.sim_time.strftime("%H:%M") if msg.sim_time else "",
            "timestamp": msg.timestamp.isoformat(),
            "sender": msg.sender,
            "sender_name": sender_name,
            "receiver": msg.receiver,
            "content": msg.content,
            "message_type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
            "related_event_id": msg.related_event_id,
        })

    return {
        "session_id": session_id,
        "municipality": runner.config.municipality,
        "training_level": runner.config.training_level,
        "difficulty": runner.config.difficulty.value,
        "phase": runner.session.phase.value,
        "current_sim_time": runner.clock.sim_time_str,
        "total_events": len(runner.config.events),
        "injected_events": sum(1 for e in runner.config.events if e.injected),
        "responded_events": sum(1 for e in runner.config.events if e.response_received),
        "events": events_timeline,
        "messages": messages_timeline,
        "tasks": runner.task_manager.get_tasks_for_api(),
        "task_summary": runner.task_manager.get_summary(),
        "revisions": runner.scenario_updater.get_histories_for_api() if runner.scenario_updater else [],
        "modified_event_ids": runner.scenario_updater.get_modified_event_ids() if runner.scenario_updater else [],
        "state_summary": runner.state_manager.get_state_summary(),
    }


@router.get("/sessions/{session_id}/events/{event_id}")
async def get_event_detail(session_id: str, event_id: str):
    """Get detailed info about a specific event including related messages."""
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    event = next((e for e in runner.config.events if e.event_id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Find related messages
    related_messages = [
        m.model_dump() for m in runner.session.messages if m.related_event_id == event_id
    ]

    # Find score
    score = next((s for s in runner.session.scores if s.event_id == event_id), None)

    return {
        "event": {
            "event_id": event.event_id,
            "title": event.title,
            "sim_time": event.scheduled_time,
            "source": event.source,
            "content_admin": event.content_admin,
            "content_trainee": event.content_trainee,
            "expected_actions": event.expected_actions,
            "expected_issues": event.expected_issues,
            "training_objective": event.training_objective,
            "weather_info": event.weather_info,
            "river_info": event.river_info,
            "terrain_info": event.terrain_info,
            "water_level_status": event.water_level_status,
            "secondary_disaster_risks": event.secondary_disaster_risks,
            "injected": event.injected,
            "response_received": event.response_received,
        },
        "related_messages": related_messages,
        "score": score.model_dump() if score else None,
    }


@router.get("/sessions/{session_id}/tasks")
async def get_tasks(session_id: str, status: str | None = None, role: str | None = None):
    """Get all disaster response tasks with optional filtering.

    Query params:
    - status: pending, active, in_progress, completed, overdue, skipped
    - role: soumu, shoubou, kensetsu, fukushi, etc.
    """
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    tasks = runner.task_manager.get_tasks_for_api()

    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if role:
        tasks = [t for t in tasks if t["responsible_role"] == role]

    # Add display names
    for t in tasks:
        role_enum = None
        for r in AgentRole:
            if r.value == t["responsible_role"]:
                role_enum = r
                break
        t["responsible_role_name"] = (
            ROLE_DISPLAY_NAMES.get(role_enum, (t["responsible_role"],))[0]
            if role_enum
            else t["responsible_role"]
        )

    return {
        "session_id": session_id,
        "summary": runner.task_manager.get_summary(),
        "tasks": tasks,
    }


@router.post("/sessions/{session_id}/tasks/{task_id}/complete")
async def complete_task(session_id: str, task_id: str, score: int | None = None):
    """Manually mark a task as completed (admin override)."""
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    runner.task_manager.complete_task(
        task_id, runner.clock.sim_time_str, score
    )
    return {"status": "completed", "task_id": task_id}
