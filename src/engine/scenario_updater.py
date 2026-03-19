"""Scenario updater - AI agent that revises scenario events based on simulation state."""

import json

import structlog

from src.agents.scenario_master import ScenarioMaster
from src.engine.state_manager import StateManager
from src.models.scenario import ScenarioEvent
from src.models.scenario_revision import EventRevisionHistory, ScenarioRevision

logger = structlog.get_logger()


class ScenarioUpdater:
    """Tracks and applies revisions to scenario events.

    When participants take actions (or fail to), future events may need
    to be updated to reflect the changed disaster state. This class:
    1. Maintains revision history for every event
    2. Uses the ScenarioMaster agent to generate revised content
    3. Applies revisions while preserving the original
    """

    def __init__(self, scenario_master: ScenarioMaster, state_manager: StateManager):
        self.scenario_master = scenario_master
        self.state_manager = state_manager
        self._histories: dict[str, EventRevisionHistory] = {}

    def register_event(self, event: ScenarioEvent):
        """Register an event and snapshot its original content."""
        if event.event_id not in self._histories:
            self._histories[event.event_id] = EventRevisionHistory(
                event_id=event.event_id,
                original_snapshot={
                    "title": event.title,
                    "content_admin": event.content_admin,
                    "content_trainee": event.content_trainee,
                    "expected_actions": event.expected_actions,
                    "expected_issues": event.expected_issues,
                    "training_objective": event.training_objective,
                    "water_level_status": event.water_level_status,
                    "secondary_disaster_risks": event.secondary_disaster_risks,
                },
            )

    def register_dynamic_event(self, event: ScenarioEvent):
        """Register a dynamically generated event."""
        self.register_event(event)
        self._histories[event.event_id].is_dynamic = True

    def _record_revision(
        self,
        event_id: str,
        field_name: str,
        original_value: str,
        new_value: str,
        trigger: str,
        trigger_detail: str,
        reason: str,
        agent_explanation: str,
        sim_time: str,
    ) -> ScenarioRevision:
        history = self._histories.get(event_id)
        if not history:
            return None

        revision = ScenarioRevision(
            event_id=event_id,
            revision_number=history.revision_count + 1,
            sim_time=sim_time,
            trigger=trigger,
            trigger_detail=trigger_detail,
            field_name=field_name,
            original_value=original_value,
            new_value=new_value,
            reason=reason,
            agent_explanation=agent_explanation,
        )
        history.revisions.append(revision)

        logger.info(
            "scenario_revised",
            event_id=event_id,
            field=field_name,
            trigger=trigger,
            revision_number=revision.revision_number,
        )
        return revision

    async def update_event_from_action(
        self,
        event: ScenarioEvent,
        participant_action: str,
        evaluation_score: int,
        sim_time: str,
    ) -> list[ScenarioRevision]:
        """Update future aspects of an event based on participant action.

        Called after a participant responds to an event. If the response
        was poor or excellent, future events' context may need updating.
        """
        revisions = []

        if evaluation_score >= 4:
            trigger = "mitigation"
            prompt = (
                f"参加者が以下の適切な対応を行いました:\n{participant_action}\n\n"
                f"元のイベント内容:\nタイトル: {event.title}\n"
                f"想定される二次災害: {event.secondary_disaster_risks}\n\n"
                f"この対応により、二次災害リスクや被害状況がどう軽減されたか、"
                f"更新後の内容を日本語で簡潔に記述してください。\n"
                f"JSON形式: {{\"updated_risks\": \"...\", \"reason\": \"...\"}}"
            )
        elif evaluation_score <= 2:
            trigger = "escalation"
            prompt = (
                f"参加者の対応が不十分でした:\n{participant_action}\n\n"
                f"元のイベント内容:\nタイトル: {event.title}\n"
                f"想定される二次災害: {event.secondary_disaster_risks}\n\n"
                f"対応不足により、状況がどう悪化したか、"
                f"更新後の内容を日本語で簡潔に記述してください。\n"
                f"JSON形式: {{\"updated_risks\": \"...\", \"reason\": \"...\"}}"
            )
        else:
            return revisions  # Score 3: no update needed

        try:
            response = await self.scenario_master.respond(prompt)
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                updated_risks = data.get("updated_risks", "")
                reason = data.get("reason", "")

                if updated_risks and updated_risks != event.secondary_disaster_risks:
                    rev = self._record_revision(
                        event_id=event.event_id,
                        field_name="secondary_disaster_risks",
                        original_value=event.secondary_disaster_risks,
                        new_value=updated_risks,
                        trigger=trigger,
                        trigger_detail=participant_action[:200],
                        reason=reason,
                        agent_explanation=response,
                        sim_time=sim_time,
                    )
                    if rev:
                        event.secondary_disaster_risks = updated_risks
                        revisions.append(rev)

        except Exception as e:
            logger.error("scenario_update_failed", event_id=event.event_id, error=str(e))

        return revisions

    async def escalate_from_omission(
        self,
        event: ScenarioEvent,
        sim_time: str,
    ) -> list[ScenarioRevision]:
        """Update event content when participant failed to respond in time."""
        revisions = []

        prompt = (
            f"以下のイベントに対して、参加者が期限内に対応しませんでした:\n"
            f"タイトル: {event.title}\n"
            f"管理用詳細: {event.content_admin[:300]}\n"
            f"期待される対応: {event.expected_actions}\n\n"
            f"対応遅延により状況がどう悪化したか、訓練者向け内容と管理用詳細を更新してください。\n"
            f"JSON形式: {{"
            f"\"updated_content_trainee\": \"...\", "
            f"\"updated_content_admin\": \"...\", "
            f"\"reason\": \"...\""
            f"}}"
        )

        try:
            response = await self.scenario_master.respond(prompt)
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                for field, key in [
                    ("content_trainee", "updated_content_trainee"),
                    ("content_admin", "updated_content_admin"),
                ]:
                    new_val = data.get(key, "")
                    old_val = getattr(event, field, "")
                    if new_val and new_val != old_val:
                        rev = self._record_revision(
                            event_id=event.event_id,
                            field_name=field,
                            original_value=old_val,
                            new_value=new_val,
                            trigger="omission",
                            trigger_detail=f"期待される対応: {event.expected_actions[:200]}",
                            reason=data.get("reason", "対応遅延による状況悪化"),
                            agent_explanation=response,
                            sim_time=sim_time,
                        )
                        if rev:
                            setattr(event, field, new_val)
                            revisions.append(rev)

        except Exception as e:
            logger.error("omission_update_failed", event_id=event.event_id, error=str(e))

        return revisions

    def get_history(self, event_id: str) -> EventRevisionHistory | None:
        return self._histories.get(event_id)

    def get_all_histories(self) -> dict[str, EventRevisionHistory]:
        return self._histories

    def get_modified_event_ids(self) -> list[str]:
        return [eid for eid, h in self._histories.items() if h.is_modified]

    def get_histories_for_api(self) -> list[dict]:
        """Serialize all histories for the API."""
        result = []
        for event_id, history in self._histories.items():
            result.append({
                "event_id": event_id,
                "is_dynamic": history.is_dynamic,
                "is_modified": history.is_modified,
                "revision_count": history.revision_count,
                "original_snapshot": history.original_snapshot,
                "revisions": [
                    {
                        "revision_id": r.revision_id,
                        "revision_number": r.revision_number,
                        "timestamp": r.timestamp.isoformat(),
                        "sim_time": r.sim_time,
                        "trigger": r.trigger,
                        "trigger_detail": r.trigger_detail,
                        "field_name": r.field_name,
                        "original_value": r.original_value,
                        "new_value": r.new_value,
                        "reason": r.reason,
                        "agent_explanation": r.agent_explanation,
                    }
                    for r in history.revisions
                ],
            })
        return result
