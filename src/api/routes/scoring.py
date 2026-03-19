"""Scoring endpoints."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/sessions/{session_id}/scores")
async def get_scores(session_id: str):
    """Get all scores for a session."""
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    scores = runner.session.scores
    if not scores:
        return {"session_id": session_id, "scores": [], "summary": None}

    # Calculate summary
    avg_score = sum(s.score for s in scores) / len(scores) if scores else 0
    avg_response_time = (
        sum(s.response_time_minutes for s in scores) / len(scores) if scores else 0
    )

    # Group by participant
    by_participant: dict[str, list] = {}
    for s in scores:
        by_participant.setdefault(s.participant_id, []).append(s.model_dump())

    return {
        "session_id": session_id,
        "total_events_scored": len(scores),
        "average_score": round(avg_score, 2),
        "average_response_time_minutes": round(avg_response_time, 2),
        "scores_by_participant": by_participant,
        "scores": [s.model_dump() for s in scores],
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 100):
    """Get message history for a session."""
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = runner.session.messages[-limit:]
    return {
        "session_id": session_id,
        "total_messages": len(runner.session.messages),
        "messages": [m.model_dump() for m in messages],
    }


@router.get("/sessions/{session_id}/report")
async def get_report(session_id: str):
    """Generate a post-session training report."""
    from src.api.app import active_sessions

    runner = active_sessions.get(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")

    scores = runner.session.scores
    messages = runner.session.messages

    # Build report
    avg_score = sum(s.score for s in scores) / len(scores) if scores else 0

    # Identify strengths and weaknesses
    high_scores = [s for s in scores if s.score >= 4]
    low_scores = [s for s in scores if s.score <= 2]

    strengths = list(set(s.evaluation_notes for s in high_scores if s.evaluation_notes))[:5]
    weaknesses = list(set(s.evaluation_notes for s in low_scores if s.evaluation_notes))[:5]

    return {
        "session_id": session_id,
        "municipality": runner.config.municipality,
        "difficulty": runner.config.difficulty.value,
        "duration_minutes": (
            (runner.session.ended_at - runner.session.started_at).total_seconds() / 60
            if runner.session.ended_at and runner.session.started_at
            else None
        ),
        "total_events": len(runner.config.events),
        "events_processed": runner.scheduler.injected_count,
        "total_messages": len(messages),
        "overall_score": round(avg_score * 20, 1),  # Convert 1-5 to 0-100
        "event_scores": [s.model_dump() for s in scores],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": [
            "応答時間の短縮を意識してください" if avg_score < 3 else "引き続き迅速な対応を維持してください",
            "複数事象発生時の優先順位付けを改善してください" if low_scores else "優先順位付けは適切です",
        ],
    }
