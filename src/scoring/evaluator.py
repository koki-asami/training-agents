"""Scoring evaluator - evaluates participant actions against expected responses."""


from src.models.scoring import CategoryScore, EventScore, SessionScore
from src.models.session import SimulationSession


def calculate_session_score(session: SimulationSession) -> SessionScore | None:
    """Calculate the overall session score for each human participant."""
    if not session.scores:
        return None

    # Group scores by participant
    by_participant: dict[str, list[EventScore]] = {}
    for score in session.scores:
        by_participant.setdefault(score.participant_id, []).append(score)

    # For now, return the first participant's score
    for pid, scores in by_participant.items():
        participant = next((p for p in session.participants if p.participant_id == pid), None)
        if not participant:
            continue

        avg_score = sum(s.score for s in scores) / len(scores)
        avg_response = sum(s.response_time_minutes for s in scores) / len(scores)

        # Category scores
        categories = [
            CategoryScore(
                category="response_time",
                score=max(0, 100 - avg_response * 5),  # Penalty for slow responses
                details=f"平均応答時間: {avg_response:.1f}分",
            ),
            CategoryScore(
                category="decision_quality",
                score=avg_score * 20,
                details=f"平均判断スコア: {avg_score:.1f}/5",
            ),
        ]

        # Identify strengths/weaknesses
        strengths = []
        weaknesses = []
        for s in scores:
            if s.score >= 4:
                strengths.append(f"イベント{s.event_id}: {s.evaluation_notes}")
            elif s.score <= 2:
                weaknesses.append(f"イベント{s.event_id}: {s.evaluation_notes}")

        return SessionScore(
            session_id=session.session_id,
            participant_id=pid,
            participant_role=participant.role.value,
            overall_score=avg_score * 20,
            total_events_scored=len(scores),
            event_scores=scores,
            category_scores=categories,
            response_time_avg_minutes=avg_response,
            strengths=strengths[:5],
            weaknesses=weaknesses[:5],
            recommendations=_generate_recommendations(avg_score, avg_response, weaknesses),
        )

    return None


def _generate_recommendations(
    avg_score: float, avg_response: float, weaknesses: list[str]
) -> list[str]:
    recommendations = []

    if avg_response > 8:
        recommendations.append(
            "応答時間の改善: 情報を受けてから対応指示までの時間を短縮してください。"
            "特に避難指示の発令は迅速さが求められます。"
        )

    if avg_score < 3:
        recommendations.append(
            "判断の質の向上: 期待される対応行動を事前に学習し、"
            "地域防災計画に基づいた判断ができるようにしてください。"
        )

    if len(weaknesses) > 2:
        recommendations.append(
            "複数事象への対応: 同時に発生する事象への優先順位付けを練習してください。"
            "生命の危険度、緊急性、影響範囲を基準に判断しましょう。"
        )

    if not recommendations:
        recommendations.append(
            "全体的に良好な対応でした。より上位の難易度に挑戦してみてください。"
        )

    return recommendations
