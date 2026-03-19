"""Scenario Master - the orchestrator agent that controls the simulation."""

import json
import os

import structlog

from src.agents.base_agent import BaseAgent, LLM_PROVIDER
from src.agents.prompts.scenario_master import SCENARIO_MASTER_PROMPT
from src.engine.message_bus import MessageBus
from src.engine.state_manager import StateManager
from src.models.enums import AgentRole, DifficultyLevel
from src.models.scenario import ScenarioConfig, ScenarioEvent

logger = structlog.get_logger()


class ScenarioMaster(BaseAgent):
    """Orchestrator agent that controls the training simulation.

    Responsible for:
    - Injecting scenario events at the right time
    - Evaluating participant responses
    - Dynamically adapting the scenario
    - Managing simulation progression
    """

    def __init__(
        self,
        config: ScenarioConfig,
        state_manager: StateManager,
        message_bus: MessageBus,
    ):
        self.config = config
        self.state_manager = state_manager
        self.message_bus = message_bus

        system_prompt = SCENARIO_MASTER_PROMPT.format(
            municipality=config.municipality,
            difficulty=config.difficulty.value,
            current_state="（訓練開始前）",
        )

        if LLM_PROVIDER == "openai":
            default_model = os.getenv("SCENARIO_MASTER_MODEL", "gpt-4o")
        else:
            default_model = os.getenv("SCENARIO_MASTER_MODEL", "claude-opus-4-20250514")

        super().__init__(
            role=AgentRole.SCENARIO_MASTER,
            system_prompt=system_prompt,
            model=default_model,
        )

    def update_system_prompt(self):
        """Refresh the system prompt with current state."""
        state_summary = json.dumps(
            self.state_manager.get_state_summary(), ensure_ascii=False, indent=2
        )
        self.system_prompt = SCENARIO_MASTER_PROMPT.format(
            municipality=self.config.municipality,
            difficulty=self.config.difficulty.value,
            current_state=state_summary,
        )

    async def inject_event(self, event: ScenarioEvent) -> str:
        """Have the Scenario Master process and inject a scenario event.

        Returns the message to be sent to the target agent/department.
        """
        self.update_system_prompt()

        prompt = (
            f"以下のシナリオイベントを状況付与してください。\n\n"
            f"イベントID: {event.event_id}\n"
            f"時刻: {event.scheduled_time}\n"
            f"情報源: {event.source}\n"
            f"管理用詳細: {event.content_admin}\n"
            f"訓練者向け: {event.content_trainee}\n"
            f"狙い: {event.training_objective}\n"
            f"期待される対応: {event.expected_actions}\n\n"
            f"情報源にふさわしい口調で、訓練者向けの状況付与メッセージを生成してください。"
        )

        response = await self.respond(prompt)
        logger.info(
            "event_injected",
            event_id=event.event_id,
            target=event.target_agent.value,
        )
        return response

    async def evaluate_response(
        self, event: ScenarioEvent, participant_action: str
    ) -> dict:
        """Evaluate a participant's response to an event.

        Returns a dict with score (1-5), evaluation notes, etc.
        """
        self.update_system_prompt()

        prompt = (
            f"以下の参加者の対応を評価してください。\n\n"
            f"イベント: {event.title} (ID: {event.event_id})\n"
            f"期待される対応: {event.expected_actions}\n"
            f"想定される課題: {event.expected_issues}\n"
            f"参加者の実際の対応:\n{participant_action}\n\n"
            f"以下のJSON形式で評価を出力してください:\n"
            f'{{"score": 1-5の整数, "evaluation_notes": "評価コメント", '
            f'"strengths": ["良かった点"], "improvements": ["改善点"]}}'
        )

        response = await self.respond(prompt)

        # Try to parse JSON from response
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback
        return {
            "score": 3,
            "evaluation_notes": response,
            "strengths": [],
            "improvements": [],
        }

    async def generate_dynamic_event(self, context: str) -> str:
        """Generate a new event based on the current situation.

        Used when the scenario needs to adapt to participant actions.
        """
        self.update_system_prompt()

        prompt = (
            f"以下の状況に基づいて、新しい状況付与イベントを生成してください。\n\n"
            f"状況: {context}\n\n"
            f"自治体: {self.config.municipality}\n"
            f"難易度: {self.config.difficulty.value}\n\n"
            f"リアルな災害進行に基づいた新しいイベントを生成してください。"
        )

        return await self.respond(prompt)

    async def provide_hint(self, context: str) -> str:
        """Generate a hint for beginner difficulty (delivered via General Affairs agent)."""
        if self.config.difficulty != DifficultyLevel.BEGINNER:
            return ""

        self.update_system_prompt()

        prompt = (
            f"初級訓練モードです。以下の状況で、訓練参加者に対するヒントを生成してください。\n\n"
            f"状況: {context}\n\n"
            f"ヒントは総務部長の口調で、「過去の事例では...」「一般的には...」という形で提供してください。"
            f"答えを直接教えるのではなく、考えるきっかけを与える形にしてください。"
        )

        return await self.respond(prompt)
