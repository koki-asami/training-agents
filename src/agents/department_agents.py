"""Department AI agents - simulate government departments."""

import json

from src.agents.base_agent import BaseAgent
from src.agents.prompts.departments import (
    BEGINNER_HINT_SECTION,
    CONSTRUCTION_PROMPT,
    FIRE_DEPARTMENT_PROMPT,
    GENERAL_AFFAIRS_PROMPT,
    WELFARE_PROMPT,
)
from src.engine.state_manager import StateManager
from src.models.enums import AgentRole, DifficultyLevel
from src.tools.tool_registry import (
    get_construction_tools,
    get_fire_department_tools,
    get_general_affairs_tools,
    get_welfare_tools,
)


def _build_state_context(state_manager: StateManager) -> str:
    return json.dumps(state_manager.get_state_summary(), ensure_ascii=False, indent=2)


class FireDepartmentAgent(BaseAgent):
    def __init__(self, municipality: str, state_manager: StateManager):
        tools, handlers = get_fire_department_tools(state_manager)
        self._state_manager = state_manager
        super().__init__(
            role=AgentRole.FIRE_DEPARTMENT,
            system_prompt=FIRE_DEPARTMENT_PROMPT.format(
                municipality=municipality,
                current_state=_build_state_context(state_manager),
            ),
            tools=tools,
            tool_handlers=handlers,
        )

    async def respond(self, user_message: str, **kwargs) -> str:
        # Refresh state context before each response
        self.system_prompt = FIRE_DEPARTMENT_PROMPT.format(
            municipality=self.system_prompt.split("あなたは")[1].split("消防局長")[0]
            if "消防局長" in self.system_prompt
            else "",
            current_state=_build_state_context(self._state_manager),
        )
        return await super().respond(user_message, **kwargs)


class ConstructionAgent(BaseAgent):
    def __init__(self, municipality: str, state_manager: StateManager):
        tools, handlers = get_construction_tools(state_manager)
        self._state_manager = state_manager
        self._municipality = municipality
        super().__init__(
            role=AgentRole.CONSTRUCTION,
            system_prompt=CONSTRUCTION_PROMPT.format(
                municipality=municipality,
                current_state=_build_state_context(state_manager),
            ),
            tools=tools,
            tool_handlers=handlers,
        )

    async def respond(self, user_message: str, **kwargs) -> str:
        self.system_prompt = CONSTRUCTION_PROMPT.format(
            municipality=self._municipality,
            current_state=_build_state_context(self._state_manager),
        )
        return await super().respond(user_message, **kwargs)


class WelfareAgent(BaseAgent):
    def __init__(self, municipality: str, state_manager: StateManager):
        tools, handlers = get_welfare_tools(state_manager)
        self._state_manager = state_manager
        self._municipality = municipality
        super().__init__(
            role=AgentRole.WELFARE,
            system_prompt=WELFARE_PROMPT.format(
                municipality=municipality,
                current_state=_build_state_context(state_manager),
            ),
            tools=tools,
            tool_handlers=handlers,
        )

    async def respond(self, user_message: str, **kwargs) -> str:
        self.system_prompt = WELFARE_PROMPT.format(
            municipality=self._municipality,
            current_state=_build_state_context(self._state_manager),
        )
        return await super().respond(user_message, **kwargs)


class GeneralAffairsAgent(BaseAgent):
    def __init__(
        self,
        municipality: str,
        state_manager: StateManager,
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    ):
        tools, handlers = get_general_affairs_tools(state_manager)
        self._state_manager = state_manager
        self._municipality = municipality
        self._difficulty = difficulty
        hint_section = BEGINNER_HINT_SECTION if difficulty == DifficultyLevel.BEGINNER else ""

        super().__init__(
            role=AgentRole.GENERAL_AFFAIRS,
            system_prompt=GENERAL_AFFAIRS_PROMPT.format(
                municipality=municipality,
                current_state=_build_state_context(state_manager),
                hint_section=hint_section,
            ),
            tools=tools,
            tool_handlers=handlers,
        )

    async def respond(self, user_message: str, **kwargs) -> str:
        hint_section = (
            BEGINNER_HINT_SECTION if self._difficulty == DifficultyLevel.BEGINNER else ""
        )
        self.system_prompt = GENERAL_AFFAIRS_PROMPT.format(
            municipality=self._municipality,
            current_state=_build_state_context(self._state_manager),
            hint_section=hint_section,
        )
        return await super().respond(user_message, **kwargs)
