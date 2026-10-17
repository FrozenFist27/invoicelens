"""Settings: reads .env (via pydantic-settings) + config/settings.yaml + config/pricing.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfidenceWeights(BaseModel):
    llm: float = 0.5
    grounding: float = 0.3
    rules: float = 0.2


class GroundingCfg(BaseModel):
    exact: float = 1.0
    fuzzy: float = 0.6
    none: float = 0.0
    fuzzy_threshold: int = 85


class DemoCfg(BaseModel):
    max_upload_mb: int = 2
    max_pages: int = 3
    daily_doc_limit: int = 20


class Settings(BaseSettings):
    """Runtime settings. Env vars override .env; .env overrides defaults."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = ""
    anthropic_api_base: str = ""  # blank = https://api.anthropic.com
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-5-5"

    # Pipeline
    review_threshold: float = 0.7
    max_retries: int = 2
    max_prompt_tokens: int = 12000
    ocr_min_chars_per_page: int = 50
    ocr_dpi: int = 300
    max_tokens: int = 4000
    # Haiku 5.5 effort level (low|medium|high). low keeps spend small.
    extraction_effort: str = "low"

    # Optional paths
    tesseract_cmd: str = ""

    # Demo caps
    demo_mode: bool = False
    demo_daily_doc_limit: int = 20
    demo_max_pages: int = 3

    # Loaded from YAML (not env)
    confidence_weights: ConfidenceWeights = Field(default_factory=ConfidenceWeights)
    grounding: GroundingCfg = Field(default_factory=GroundingCfg)
    demo: DemoCfg = Field(default_factory=DemoCfg)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load Settings, then overlay config/settings.yaml values that are not set via env."""
    s = Settings()
    yml = _load_yaml(PROJECT_ROOT / "config" / "settings.yaml")
    # YAML fills fields only when the env did not explicitly set them.
    env_set = set()
    import os

    for key in Settings.model_fields:
        if key.upper() in os.environ:
            env_set.add(key)
    updates: dict[str, Any] = {}
    for key in (
        "review_threshold",
        "max_retries",
        "max_prompt_tokens",
        "ocr_min_chars_per_page",
        "ocr_dpi",
        "max_tokens",
    ):
        if key in yml and key not in env_set:
            updates[key] = yml[key]
    if "confidence_weights" in yml:
        updates["confidence_weights"] = ConfidenceWeights(**yml["confidence_weights"])
    if "grounding" in yml:
        updates["grounding"] = GroundingCfg(**yml["grounding"])
    if "demo" in yml:
        updates["demo"] = DemoCfg(**yml["demo"])
    if "temperature" in yml:
        # Haiku 5.5 rejects non-default sampling params; temperature is intentionally unused.
        pass
    if updates:
        s = s.model_copy(update=updates)
    return s


def get_pricing(model: str) -> dict[str, float]:
    """Return $/MTok rates for a model id from config/pricing.yaml."""
    data = _load_yaml(PROJECT_ROOT / "config" / "pricing.yaml")
    models = data.get("models", {})
    return models.get(model, models.get("default", {}))
