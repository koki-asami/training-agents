"""Adaptation engine - dynamically modifies scenarios based on participant actions."""


from datetime import datetime, timedelta

import structlog

from src.agents.scenario_master import ScenarioMaster
from src.engine.state_manager import StateManager
from src.models.enums import DifficultyLevel
from src.models.scenario import ScenarioEvent

logger = structlog.get_logger()


class AdaptationEngine:
    """Evaluates participant actions and adapts the scenario.

    Tracks three types of deviation:
    1. Timing: response within expected window
    2. Action: correct action taken
    3. Omission: no action on critical event
    """

    def __init__(
        self,
        scenario_master: ScenarioMaster,
        state_manager: StateManager,
        difficulty: DifficultyLevel,
    ):
        self.scenario_master = scenario_master
        self.state_manager = state_manager
        self.difficulty = difficulty
        self._omission_tracked: dict[str, datetime] = {}  # event_id -> deadline

    def track_event(self, event: ScenarioEvent, sim_time: datetime):
        """Start tracking an event for response timeout."""
        deadline = sim_time + timedelta(minutes=event.response_window_minutes)
        self._omission_tracked[event.event_id] = deadline
        logger.debug(
            "tracking_event",
            event_id=event.event_id,
            deadline=deadline.strftime("%H:%M"),
        )

    def mark_responded(self, event_id: str):
        """Mark an event as responded to."""
        self._omission_tracked.pop(event_id, None)

    async def check_omissions(self, current_sim_time: datetime) -> list[dict]:
        """Check for events where the response window has expired.

        Returns a list of consequence actions to take.
        """
        consequences = []
        expired = [
            eid
            for eid, deadline in self._omission_tracked.items()
            if current_sim_time > deadline
        ]

        for event_id in expired:
            self._omission_tracked.pop(event_id)

            if self.difficulty == DifficultyLevel.BEGINNER:
                # Beginner: provide hints instead of consequences
                consequences.append(
                    {
                        "type": "hint",
                        "event_id": event_id,
                        "message": f"イベント{event_id}への対応がまだ行われていません。",
                    }
                )
            else:
                # Intermediate/Advanced: generate escalation
                consequences.append(
                    {
                        "type": "escalation",
                        "event_id": event_id,
                        "message": f"イベント{event_id}への対応遅延により状況が悪化しています。",
                    }
                )

            logger.warning("omission_detected", event_id=event_id, difficulty=self.difficulty.value)

        return consequences

    async def generate_escalation(self, event_id: str, context: str) -> ScenarioEvent | None:
        """Generate an escalation event when a participant fails to respond."""
        response = await self.scenario_master.generate_dynamic_event(
            f"イベント{event_id}に対する対応が遅延しています。{context}\n"
            f"この遅延により発生する二次的な事象を生成してください。"
        )

        if response:
            # Create a dynamic event
            event = ScenarioEvent(
                event_id=f"D-{event_id}",
                title=f"対応遅延による状況悪化",
                scheduled_time=self.state_manager.state.sim_time.strftime("%H:%M"),
                source="シナリオマスター",
                content_admin=response,
                content_trainee=response,
                training_objective="対応遅延の影響を体験する",
                expected_actions="状況の再評価と対応の見直し",
            )
            return event
        return None

    async def evaluate_and_adapt(
        self,
        event: ScenarioEvent,
        participant_action: str,
        response_time_minutes: float,
    ) -> dict:
        """Evaluate a response and determine if adaptation is needed.

        Returns evaluation result with any adaptation actions.
        """
        evaluation = await self.scenario_master.evaluate_response(event, participant_action)

        # Determine adaptation based on score
        score = evaluation.get("score", 3)
        adaptation = None

        if score <= 2 and self.difficulty != DifficultyLevel.BEGINNER:
            # Poor response - escalate consequences
            adaptation = {
                "type": "escalation",
                "description": "対応不十分による状況悪化",
            }
        elif score >= 5:
            # Excellent response - may mitigate future events
            adaptation = {
                "type": "mitigation",
                "description": "適切な対応による被害軽減",
            }

        evaluation["adaptation"] = adaptation
        evaluation["response_time_minutes"] = response_time_minutes

        return evaluation
