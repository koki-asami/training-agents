"""Session management endpoints."""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.engine.simulation_runner import SimulationRunner
from src.loaders.scenario_loader import (
    load_scenario_from_excel,
    load_scenario_from_json,
)
from src.models.enums import ASSIGNABLE_ROLES, AgentRole, DifficultyLevel
from src.models.session import AgentAssignment, Participant, SimulationSession

router = APIRouter()


def get_sessions_store():
    from src.api.app import active_sessions

    return active_sessions


class CreateSessionResponse(BaseModel):
    session_id: str
    participants: list[dict]
    ai_roles: list[str]
    human_roles: list[str]


def _build_session(config, role_assignments_raw: list[dict]) -> SimulationSession:
    """Build a SimulationSession from config and role assignments."""
    assignments = []
    participants = []
    assigned_roles = set()

    for ra in role_assignments_raw:
        role = AgentRole(ra["role"])
        is_human = ra.get("is_human", False)

        if is_human and role not in ASSIGNABLE_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Role {role.value} cannot be assigned to a human",
            )

        participant = None
        if is_human:
            participant = Participant(name=ra.get("participant_name") or "参加者", role=role)
            participants.append(participant)

        assignments.append(
            AgentAssignment(
                role=role,
                is_human=is_human,
                participant_id=participant.participant_id if participant else None,
            )
        )
        assigned_roles.add(role)

    # Fill unassigned roles with AI
    for role in [
        AgentRole.COMMANDER,
        AgentRole.GENERAL_AFFAIRS,
        AgentRole.FIRE_DEPARTMENT,
        AgentRole.CONSTRUCTION,
        AgentRole.WELFARE,
        AgentRole.WEATHER,
    ]:
        if role not in assigned_roles:
            assignments.append(AgentAssignment(role=role, is_human=False))

    # Add resident agents (always AI)
    for i in range(3):
        assignments.append(
            AgentAssignment(
                role=AgentRole.RESIDENT,
                is_human=False,
                agent_instance_id=f"resident_{i}",
            )
        )

    return SimulationSession(
        config=config,
        assignments=assignments,
        participants=participants,
    )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    scenario_file: UploadFile = File(..., description="シナリオファイル (.json or .xlsx)"),
    difficulty: DifficultyLevel = Form(DifficultyLevel.INTERMEDIATE),
    municipality: str = Form("熊本市"),
    role_assignments: str = Form("[]", description="JSON array of role assignments"),
):
    """Create a new training simulation session with an uploaded scenario file.

    - scenario_file: JSON or Excel (.xlsx) file from training-scenario-generator
    - difficulty: beginner / intermediate / advanced
    - municipality: 自治体名
    - role_assignments: JSON string, e.g. [{"role":"commander","is_human":true,"participant_name":"田中"}]
    """
    sessions = get_sessions_store()

    # Parse role assignments
    try:
        role_assignments_parsed = json.loads(role_assignments)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid role_assignments JSON")

    # Determine file type and load
    filename = scenario_file.filename or "scenario.json"
    suffix = Path(filename).suffix.lower()

    if suffix not in (".json", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use .json or .xlsx",
        )

    # Save uploaded file to temp location
    content = await scenario_file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if suffix == ".json":
            config = load_scenario_from_json(tmp_path, difficulty)
        else:
            config = load_scenario_from_excel(tmp_path, difficulty)
    except Exception as e:
        Path(tmp_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse scenario file: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    config.municipality = municipality
    config.difficulty = difficulty

    # Build session
    session = _build_session(config, role_assignments_parsed)

    # Create runner
    runner = SimulationRunner(session)
    await runner.initialize()

    sessions[session.session_id] = runner

    return CreateSessionResponse(
        session_id=session.session_id,
        participants=[
            {"id": p.participant_id, "name": p.name, "role": p.role.value}
            for p in session.participants
        ],
        ai_roles=[a.role.value for a in session.assignments if not a.is_human],
        human_roles=[a.role.value for a in session.assignments if a.is_human],
    )


@router.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    sessions = get_sessions_store()
    return [
        {
            "session_id": sid,
            "phase": runner.session.phase.value,
            "municipality": runner.config.municipality,
            "difficulty": runner.config.difficulty.value,
            "event_progress": f"{runner.scheduler.injected_count}/{len(runner.config.events)}",
        }
        for sid, runner in sessions.items()
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "phase": runner.session.phase.value,
        "config": runner.config.model_dump(),
        "state": runner.state_manager.get_state_summary(),
        "participants": [p.model_dump() for p in runner.session.participants],
        "message_count": len(runner.session.messages),
        "score_count": len(runner.session.scores),
    }


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    await runner.start()
    return {"status": "started", "session_id": session_id}


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    await runner.stop()
    return {"status": "stopped", "session_id": session_id}


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    if runner.clock.pause():
        return {"status": "paused"}
    raise HTTPException(status_code=400, detail="Cannot pause (not allowed at this difficulty)")


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    if runner.clock.resume():
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="Not paused")
