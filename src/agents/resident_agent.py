"""Resident agent - simulates individual residents during disaster."""


import json
import random

from src.agents.base_agent import BaseAgent
from src.agents.prompts.resident import RESIDENT_PERSONAS, RESIDENT_PROMPT
from src.engine.state_manager import StateManager
from src.models.enums import AgentRole
from src.tools.tool_registry import get_resident_tools


class ResidentAgent(BaseAgent):
    """A resident agent with a specific persona."""

    def __init__(
        self,
        municipality: str,
        area: str,
        state_manager: StateManager,
        persona: dict | None = None,
        instance_id: str = "resident_0",
    ):
        self.persona = persona or random.choice(RESIDENT_PERSONAS)
        self.area = area
        self.instance_id = instance_id
        self._state_manager = state_manager
        self._municipality = municipality

        tools, handlers = get_resident_tools(state_manager)

        persona_text = (
            f"名前: {self.persona['name']}\n"
            f"特徴: {self.persona['description']}\n"
            f"性格傾向: {', '.join(self.persona['traits'])}"
        )

        super().__init__(
            role=AgentRole.RESIDENT,
            system_prompt=RESIDENT_PROMPT.format(
                municipality=municipality,
                area=area,
                persona=persona_text,
                current_state=json.dumps(
                    state_manager.get_state_summary(), ensure_ascii=False
                ),
            ),
            tools=tools,
            tool_handlers=handlers,
        )

    async def respond(self, user_message: str, **kwargs) -> str:
        persona_text = (
            f"名前: {self.persona['name']}\n"
            f"特徴: {self.persona['description']}\n"
            f"性格傾向: {', '.join(self.persona['traits'])}"
        )
        self.system_prompt = RESIDENT_PROMPT.format(
            municipality=self._municipality,
            area=self.area,
            persona=persona_text,
            current_state=json.dumps(
                self._state_manager.get_state_summary(), ensure_ascii=False
            ),
        )
        return await super().respond(user_message, **kwargs)


class WeatherAgent(BaseAgent):
    """Provides official weather information and alerts."""

    def __init__(self, municipality: str, state_manager: StateManager):
        from src.tools.tool_registry import get_weather_tools

        tools, handlers = get_weather_tools(state_manager)
        self._state_manager = state_manager
        self._municipality = municipality

        system_prompt = (
            f"あなたは気象台の担当者です。{municipality}の災害対策本部に気象情報を提供します。\n\n"
            f"## 役割\n"
            f"- 公式な気象警報・注意報の発表\n"
            f"- 降水量予測の提供\n"
            f"- 河川水位情報の提供\n"
            f"- 気象庁の公式用語を使用する\n\n"
            f"## 口調\n"
            f"- 「気象台からお知らせします。」で始める\n"
            f"- 公式・簡潔・正確\n"
            f"- 数値データを必ず含める\n\n"
            f"常に日本語で回答してください。"
        )

        super().__init__(
            role=AgentRole.WEATHER,
            system_prompt=system_prompt,
            tools=tools,
            tool_handlers=handlers,
        )
