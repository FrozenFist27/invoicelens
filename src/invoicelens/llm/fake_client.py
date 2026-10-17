"""Deterministic fake LLM client for tests. Scripted responses, zero cost."""

from __future__ import annotations

from typing import Any

from ..models import Usage


class FakeLLMClient:
    """Replays scripted tool inputs in order. Each script entry is a dict (tool input).

    If a script entry is a callable, it is called with (system, user) and its return
    value (a dict) is used as the tool input.
    """

    def __init__(self, script: list[Any] | None = None, default: dict | None = None):
        self.script = list(script or [])
        self.default = default or {}
        self.calls: list[dict[str, str]] = []
        self._i = 0

    def call_tool(
        self,
        system: str,
        user: str,
        tool_schema: dict[str, Any],
        tool_name: str,
    ) -> tuple[dict[str, Any], Usage]:
        self.calls.append({"system": system, "user": user, "tool_name": tool_name})
        if self._i < len(self.script):
            entry = self.script[self._i]
            self._i += 1
        else:
            entry = self.default
        if callable(entry):
            entry = entry(system, user)
        return dict(entry), Usage(input_tokens=100, output_tokens=100)
