"""Anthropic client: forced tool use, prompt caching, usage capture.

Haiku 5.5 notes (see claude-api skill):
- Do NOT pass temperature/top_p/top_k (non-default values 400).
- Forced tool_choice {type: tool, name} is accepted; response starts with the tool call.
- Thinking is adaptive by default; with forced tool use the response has no thinking block.
- Prompt caching via cache_control on the system block (min 512 tokens to cache).
"""

from __future__ import annotations

import json
from typing import Any

from ..models import Usage
from ..settings import get_pricing, get_settings


class AnthropicClient:
    def __init__(self, model: str | None = None, effort: str | None = None, api_key: str | None = None):
        import anthropic

        cfg = get_settings()
        self.model = model or cfg.llm_model
        self.effort = effort or cfg.extraction_effort
        self.max_tokens = cfg.max_tokens
        key = api_key or cfg.anthropic_api_key
        self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.pricing = get_pricing(self.model)

    def cost_usd(self, usage: Usage) -> float:
        p = self.pricing or {}
        inp = p.get("input_per_mtok", 0.10)
        out = p.get("output_per_mtok", 0.50)
        cw = p.get("cache_write_per_mtok", inp * 1.25)
        cr = p.get("cache_read_per_mtok", inp * 0.1)
        return (
            usage.input_tokens * inp
            + usage.cache_creation_input_tokens * cw
            + usage.cache_read_input_tokens * cr
            + usage.output_tokens * out
        ) / 1_000_000

    def call_tool(
        self,
        system: str,
        user: str,
        tool_schema: dict[str, Any],
        tool_name: str,
    ) -> tuple[dict[str, Any], Usage]:
        # system as a cached block
        system_blocks = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_blocks,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )
        # Haiku 5.5 supports output_config.effort; only send when set to non-default is fine.
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}

        resp = self._client.messages.create(**kwargs)

        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError("LLM refused the request (stop_reason=refusal)")

        usage = Usage(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        )

        tool_input: dict[str, Any] | None = None
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                tool_input = block.input
                break
        if tool_input is None:
            # fall back: first tool_use block of any name
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    tool_input = block.input
                    break
        if tool_input is None:
            # last resort: try to parse text as JSON
            text = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
            )
            if text.strip():
                try:
                    tool_input = json.loads(text)
                except json.JSONDecodeError:
                    tool_input = None
        if tool_input is None:
            raise RuntimeError("no tool_use block in LLM response")

        return dict(tool_input), usage
