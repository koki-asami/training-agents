"""Session management endpoints."""


from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engine.simulation_runner import SimulationRunner
from src.loaders.scenario_loader import load_scenario_from_json
from src.models.enums import ASSIGNABLE_ROLES, AgentRole, DifficultyLevel
from src.models.session import AgentAssignment, Participant, SimulationSession

router = APIRouter()

# Shared session store (imported from app.py at runtime)
_sessions: dict[str, SimulationRunner] = {}


def get_sessions_store():
    from src.api.app import active_sessions
    return active_sessions


class RoleAssignment(BaseModel):
    role: AgentRole
    is_human: bool = False
    participant_name: str | None = None


class CreateSessionRequest(BaseModel):
    scenario_path: str = Field(description="Path to scenario JSON file")
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    municipality: str = "熊本市"
    role_assignments: list[RoleAssignment] = Field(default_factory=list)


class CreateSessionResponse(BaseModel):
    session_id: str
    participants: list[dict]
    ai_roles: list[str]
    human_roles: list[str]


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new training simulation session."""
    sessions = get_sessions_store()

    # Load scenario
    scenario_path = Path(request.scenario_path)
    if not scenario_path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario file not found: {request.scenario_path}")

    config = load_scenario_from_json(scenario_path, request.difficulty)
    config.municipality = request.municipality
    config.difficulty = request.difficulty

    # Build assignments
    assignments = []
    participants = []

    # Process explicit role assignments
    assigned_roles = set()
    for ra in request.role_assignments:
        if ra.is_human and ra.role not in ASSIGNABLE_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Role {ra.role.value} cannot be assigned to a human",
            )

        participant = None
        if ra.is_human:
            participant = Participant(name=ra.participant_name or "参加者", role=ra.role)
            participants.append(participant)

        assignments.append(
            AgentAssignment(
                role=ra.role,
                is_human=ra.is_human,
                participant_id=participant.participant_id if participant else None,
            )
        )
        assigned_roles.add(ra.role)

    # Fill unassigned roles with AI
    all_roles = [
        AgentRole.COMMANDER,
        AgentRole.GENERAL_AFFAIRS,
        AgentRole.FIRE_DEPARTMENT,
        AgentRole.CONSTRUCTION,
        AgentRole.WELFARE,
        AgentRole.WEATHER,
    ]
    for role in all_roles:
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

    # Create session
    session = SimulationSession(
        config=config,
        assignments=assignments,
        participants=participants,
    )

    # Create runner
    runner = SimulationRunner(session)
    await runner.initialize()

    sessions[session.session_id] = runner

    return CreateSessionResponse(
        session_id=session.session_id,
        participants=[
            {"id": p.participant_id, "name": p.name, "role": p.role.value}
            for p in participants
        ],
        ai_roles=[a.role.value for a in assignments if not a.is_human],
        human_roles=[a.role.value for a in assignments if a.is_human],
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
    """Start a simulation session."""
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    await runner.start()
    return {"status": "started", "session_id": session_id}


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a simulation session."""
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    await runner.stop()
    return {"status": "stopped", "session_id": session_id}


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a simulation (beginner only)."""
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
