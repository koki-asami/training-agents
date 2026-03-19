"""Base agent class - supports both Anthropic and OpenAI APIs."""

import asyncio
import json
import os
from typing import Any, Callable

import structlog

from src.models.enums import AgentRole

logger = structlog.get_logger()

# Provider detection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()  # "anthropic" or "openai"


def _anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI function calling format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools


class BaseAgent:
    """Base class for all AI agents in the simulation.

    Supports both Anthropic and OpenAI APIs transparently.
    Set LLM_PROVIDER env var to "anthropic" (default) or "openai".

    Tool definitions use Anthropic format internally and are auto-converted for OpenAI.
    """

    def __init__(
        self,
        role: AgentRole,
        system_prompt: str,
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_handlers: dict[str, Callable] | None = None,
    ):
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_handlers = tool_handlers or {}
        self.conversation_history: list[dict] = []
        self.provider = LLM_PROVIDER

        if self.provider == "openai":
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required when LLM_PROVIDER=openai")
            self._openai_client = openai.OpenAI(api_key=api_key)
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
            self._openai_tools = _anthropic_tools_to_openai(self.tools) if self.tools else []
        else:
            import anthropic
            self._anthropic_client = anthropic.Anthropic()
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    async def respond(self, user_message: str, max_tool_rounds: int = 5) -> str:
        """Send a message and get a response, automatically handling tool calls."""
        if self.provider == "openai":
            return await self._respond_openai(user_message, max_tool_rounds)
        return await self._respond_anthropic(user_message, max_tool_rounds)

    # ── Anthropic implementation ──

    async def _respond_anthropic(self, user_message: str, max_tool_rounds: int) -> str:
        import anthropic

        self.conversation_history.append({"role": "user", "content": user_message})

        for _ in range(max_tool_rounds):
            response = self._anthropic_client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=self.conversation_history,
                tools=self.tools if self.tools else anthropic.NOT_GIVEN,
            )

            assistant_content = response.content
            self.conversation_history.append({"role": "assistant", "content": assistant_content})

            tool_uses = [block for block in assistant_content if block.type == "tool_use"]
            if not tool_uses:
                text_parts = [
                    block.text for block in assistant_content if block.type == "text"
                ]
                return "\n".join(text_parts)

            tool_results = []
            for tool_use in tool_uses:
                result = await self._execute_tool(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                })
                logger.debug("tool_executed", agent=self.role.value, tool=tool_use.name)

            self.conversation_history.append({"role": "user", "content": tool_results})

        return await self._get_text_response_anthropic()

    async def _get_text_response_anthropic(self) -> str:
        response = self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.conversation_history,
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        return "\n".join(text_parts)

    # ── OpenAI implementation ──

    async def _respond_openai(self, user_message: str, max_tool_rounds: int) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})

        for _ in range(max_tool_rounds):
            messages = self._build_openai_messages()

            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
            }
            if self._openai_tools:
                kwargs["tools"] = self._openai_tools

            response = self._openai_client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            # Store the raw assistant message for history
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content or "",
                "_openai_tool_calls": [
                    {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in (message.tool_calls or [])
                ],
            })

            if not message.tool_calls:
                return message.content or ""

            # Execute tool calls
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                result = await self._execute_tool(func_name, func_args)
                logger.debug("tool_executed", agent=self.role.value, tool=func_name)

                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

        return await self._get_text_response_openai()

    async def _get_text_response_openai(self) -> str:
        messages = self._build_openai_messages()
        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def _build_openai_messages(self) -> list[dict]:
        """Convert internal conversation history to OpenAI messages format."""
        messages = [{"role": "system", "content": self.system_prompt}]

        for msg in self.conversation_history:
            role = msg["role"]

            if role == "tool":
                # Tool result message
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": msg["content"],
                })
            elif role == "assistant":
                openai_msg: dict[str, Any] = {"role": "assistant", "content": msg.get("content", "")}
                tool_calls = msg.get("_openai_tool_calls", [])
                if tool_calls:
                    openai_msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls
                    ]
                messages.append(openai_msg)
            elif role == "user":
                content = msg["content"]
                # Anthropic tool_result format -> skip (handled by "tool" role above)
                if isinstance(content, list) and content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                    continue
                # Regular content (could be string or Anthropic content blocks)
                if isinstance(content, str):
                    messages.append({"role": "user", "content": content})
                else:
                    # Anthropic content blocks -> extract text
                    text = " ".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                    if text.strip():
                        messages.append({"role": "user", "content": text})

        return messages

    # ── Shared methods ──

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        handler = self.tool_handlers.get(tool_name)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(**tool_input)
            return handler(**tool_input)
        logger.warning("unknown_tool", agent=self.role.value, tool=tool_name)
        return f"Error: Unknown tool '{tool_name}'"

    def inject_context(self, context: str):
        self.conversation_history.append({
            "role": "user",
            "content": f"[システム情報更新]\n{context}",
        })

    def reset_history(self):
        self.conversation_history = []

    def trim_history(self, max_messages: int = 40):
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]
