"""Base agent class - wraps anthropic SDK with tool execution loop."""


from typing import Any, Callable

import anthropic
import structlog

from src.models.enums import AgentRole

logger = structlog.get_logger()


class BaseAgent:
    """Base class for all AI agents in the simulation.

    Wraps the Anthropic API with:
    - System prompt management
    - Conversation history
    - Tool definition and execution
    - Automatic tool-use loop
    """

    def __init__(
        self,
        role: AgentRole,
        system_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        tools: list[dict] | None = None,
        tool_handlers: dict[str, Callable] | None = None,
    ):
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools or []
        self.tool_handlers = tool_handlers or {}
        self.conversation_history: list[dict] = []
        self._client = anthropic.Anthropic()

    async def respond(self, user_message: str, max_tool_rounds: int = 5) -> str:
        """Send a message and get a response, automatically handling tool calls.

        Returns the final text response after all tool calls are resolved.
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        for _ in range(max_tool_rounds):
            response = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=self.conversation_history,
                tools=self.tools if self.tools else anthropic.NOT_GIVEN,
            )

            # Collect text and tool_use blocks
            assistant_content = response.content
            self.conversation_history.append({"role": "assistant", "content": assistant_content})

            # Check if there are tool calls to handle
            tool_uses = [block for block in assistant_content if block.type == "tool_use"]
            if not tool_uses:
                # No tool calls - extract and return text
                text_parts = [
                    block.text for block in assistant_content if block.type == "text"
                ]
                return "\n".join(text_parts)

            # Execute tool calls and add results
            tool_results = []
            for tool_use in tool_uses:
                result = await self._execute_tool(tool_use.name, tool_use.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(result),
                    }
                )
                logger.debug(
                    "tool_executed",
                    agent=self.role.value,
                    tool=tool_use.name,
                )

            self.conversation_history.append({"role": "user", "content": tool_results})

        # Exceeded max rounds - get final text response
        return await self._get_text_response()

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool by name. Override in subclasses for custom handling."""
        handler = self.tool_handlers.get(tool_name)
        if handler:
            return await handler(**tool_input) if asyncio.iscoroutinefunction(handler) else handler(**tool_input)
        logger.warning("unknown_tool", agent=self.role.value, tool=tool_name)
        return f"Error: Unknown tool '{tool_name}'"

    async def _get_text_response(self) -> str:
        """Get a text-only response (no tools)."""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.conversation_history,
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        return "\n".join(text_parts)

    def inject_context(self, context: str):
        """Add context to the conversation as a system-like user message."""
        self.conversation_history.append(
            {
                "role": "user",
                "content": f"[システム情報更新]\n{context}",
            }
        )

    def reset_history(self):
        """Clear conversation history."""
        self.conversation_history = []

    def trim_history(self, max_messages: int = 40):
        """Keep only the most recent messages to manage context window."""
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]


# Need this import for iscoroutinefunction
import asyncio  # noqa: E402
