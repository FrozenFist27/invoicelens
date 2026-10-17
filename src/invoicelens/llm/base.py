"""LLMClient protocol: the provider-agnostic interface used by the pipeline."""

from __future__ import annotations

from typing import Any, Protocol

from ..models import Usage


class LLMClient(Protocol):
    def call_tool(
        self,
        system: str,
        user: str,
        tool_schema: dict[str, Any],
        tool_name: str,
    ) -> tuple[dict[str, Any], Usage]:
        """Force a single tool call; return (tool_input_dict, usage)."""
        ...
