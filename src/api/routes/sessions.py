"""Session management endpoints."""

import json
import shutil
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

# Directory to cache uploaded scenarios
SCENARIO_CACHE_DIR = Path("data/scenarios/uploads")
SCENARIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


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


def _cache_scenario(filename: str, content: bytes) -> Path:
    """Save uploaded scenario to cache directory. Returns the cached path."""
    cached_path = SCENARIO_CACHE_DIR / filename
    cached_path.write_bytes(content)
    return cached_path


def _load_scenario(path: Path, difficulty: DifficultyLevel):
    """Load scenario from a file path (JSON or Excel)."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_scenario_from_json(path, difficulty)
    elif suffix == ".xlsx":
        return load_scenario_from_excel(path, difficulty)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


@router.get("/scenarios")
async def list_cached_scenarios():
    """List cached scenario files available for reuse."""
    scenarios = []
    for p in sorted(SCENARIO_CACHE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in (".json", ".xlsx"):
            scenarios.append({
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified": p.stat().st_mtime,
            })

    # Also include bundled sample scenarios
    sample_dir = Path("data/scenarios")
    for p in sorted(sample_dir.glob("*.json")):
        if p.parent != SCENARIO_CACHE_DIR:
            scenarios.append({
                "filename": f"sample/{p.name}",
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified": p.stat().st_mtime,
            })

    return {"scenarios": scenarios}


@router.delete("/scenarios/{filename}")
async def delete_cached_scenario(filename: str):
    """Delete a cached scenario file."""
    if filename.startswith("sample/"):
        raise HTTPException(status_code=400, detail="Cannot delete sample scenarios")

    # Prevent path traversal
    safe_name = Path(filename).name
    cached_path = SCENARIO_CACHE_DIR / safe_name
    if not cached_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    cached_path.unlink()
    return {"status": "deleted", "filename": safe_name}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    scenario_file: UploadFile | None = File(None, description="シナリオファイル (.json or .xlsx)"),
    cached_scenario: str | None = Form(None, description="キャッシュ済みシナリオのファイル名"),
    difficulty: DifficultyLevel = Form(DifficultyLevel.INTERMEDIATE),
    municipality: str = Form("熊本市"),
    role_assignments: str = Form("[]", description="JSON array of role assignments"),
):
    """Create a new training simulation session.

    Scenario can be provided via:
    - scenario_file: upload a new file (will be cached for reuse)
    - cached_scenario: reuse a previously uploaded file by filename
    If neither is provided, returns 400.
    """
    sessions = get_sessions_store()

    # Parse role assignments
    try:
        role_assignments_parsed = json.loads(role_assignments)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid role_assignments JSON")

    # Resolve scenario source
    if scenario_file and scenario_file.filename:
        # New upload -> cache it
        filename = scenario_file.filename
        suffix = Path(filename).suffix.lower()

        if suffix not in (".json", ".xlsx"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {suffix}. Use .json or .xlsx",
            )

        content = await scenario_file.read()
        cached_path = _cache_scenario(filename, content)

        try:
            config = _load_scenario(cached_path, difficulty)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse scenario file: {e}")

    elif cached_scenario:
        # Use cached file
        if cached_scenario.startswith("sample/"):
            cached_path = Path("data/scenarios") / cached_scenario.removeprefix("sample/")
        else:
            cached_path = SCENARIO_CACHE_DIR / cached_scenario

        if not cached_path.exists():
            raise HTTPException(status_code=404, detail=f"Cached scenario not found: {cached_scenario}")

        try:
            config = _load_scenario(cached_path, difficulty)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse cached scenario: {e}")

    else:
        raise HTTPException(status_code=400, detail="Either scenario_file or cached_scenario is required")

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
    raise HTTPException(status_code=400, detail="Already paused or not running")


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    if runner.clock.resume():
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="Not paused")


@router.post("/sessions/{session_id}/interval")
async def set_event_interval(session_id: str, seconds: float):
    sessions = get_sessions_store()
    runner = sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    if seconds < 1 or seconds > 300:
        raise HTTPException(status_code=400, detail="Interval must be between 1 and 300 seconds")

    await runner.set_event_interval(seconds)
    return {"status": "interval_updated", "seconds": seconds}
