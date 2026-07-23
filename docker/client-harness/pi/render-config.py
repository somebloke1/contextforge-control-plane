#!/usr/bin/env python3
"""Render and validate the LiteLLM-only Pi sandbox configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


MODEL_THINKING = {
    "codex/gpt-5.6-terra": "high",
    "codex/gpt-5.6-luna": "medium",
    "codex/gpt-5.6-sol": "high",
}
THINKING_LEVEL_MAP = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "max": None,
}
DEFAULT_BASE_URL = "http://host.docker.internal:3333/v1"


def expected_thinking(model: str) -> str:
    try:
        return MODEL_THINKING[model]
    except KeyError as exc:
        raise ValueError(f"unsupported Pi sandbox model: {model!r}") from exc


def validate_models(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Pi sandbox models must be an object")
    providers = data.get("providers")
    if not isinstance(providers, dict) or set(providers) != {"litellm"}:
        raise ValueError("Pi sandbox models must contain only the litellm provider")
    provider = providers["litellm"]
    if not isinstance(provider, dict):
        raise ValueError("Pi sandbox litellm provider must be an object")
    if provider.get("api") != "openai-responses":
        raise ValueError("Pi sandbox models must use OpenAI Responses")
    compat = provider.get("compat")
    if not isinstance(compat, dict) or compat.get("supportsReasoningEffort") is not True:
        raise ValueError("Pi sandbox models must support reasoning effort")
    models = provider.get("models")
    if not isinstance(models, list) or len(models) != len(MODEL_THINKING):
        raise ValueError("Pi sandbox models must contain exactly the approved LiteLLM set")
    by_id: dict[str, dict[str, Any]] = {}
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str):
            raise ValueError("Pi sandbox model records must have string ids")
        model_id = model["id"]
        if model_id in by_id:
            raise ValueError(f"duplicate Pi sandbox model: {model_id!r}")
        by_id[model_id] = model
    if set(by_id) != set(MODEL_THINKING):
        raise ValueError("Pi sandbox models must contain exactly the approved LiteLLM set")
    for model_id, model in by_id.items():
        if model.get("reasoning") is not True:
            raise ValueError(f"Pi sandbox model must enable reasoning: {model_id!r}")
        if model.get("thinkingLevelMap") != THINKING_LEVEL_MAP:
            raise ValueError(f"Pi sandbox thinking map mismatch for {model_id!r}")
    return provider


def render_config() -> None:
    models_source = Path(
        os.environ.get("CONTEXTFORGE_PI_MODELS_SOURCE", "/config/pi/models.json")
    )
    settings_source = Path(
        os.environ.get("CONTEXTFORGE_PI_SETTINGS_SOURCE", "/config/pi/settings.json")
    )
    target_dir = Path(os.environ.get("PI_CODING_AGENT_DIR", "/home/agent/.pi/agent"))
    data = json.loads(models_source.read_text(encoding="utf-8"))
    provider = validate_models(data)

    base_url = os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    if base_url != DEFAULT_BASE_URL:
        raise ValueError(f"Pi sandbox LiteLLM endpoint must be {DEFAULT_BASE_URL!r}")
    provider["baseUrl"] = base_url
    if os.environ.get("LITELLM_API_KEY"):
        provider["apiKey"] = os.environ["LITELLM_API_KEY"]

    if os.environ.get("CONTEXTFORGE_PI_DEFAULT_PROVIDER", "litellm") != "litellm":
        raise ValueError("unsupported Pi sandbox provider")
    default_model = os.environ.get("CONTEXTFORGE_PI_DEFAULT_MODEL", "codex/gpt-5.6-luna")
    required_thinking = expected_thinking(default_model)
    default_thinking = os.environ.get("CONTEXTFORGE_PI_DEFAULT_THINKING", required_thinking)
    if default_thinking != required_thinking:
        raise ValueError(
            f"Pi sandbox thinking level {default_thinking!r} does not match "
            f"{default_model!r} ({required_thinking!r})"
        )

    settings = json.loads(settings_source.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("Pi sandbox settings must be an object")
    settings["defaultProvider"] = "litellm"
    settings["defaultModel"] = default_model
    settings["defaultThinkingLevel"] = required_thinking
    settings["enabledModels"] = [f"litellm/{model}" for model in sorted(MODEL_THINKING)]

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "models.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (target_dir / "settings.json").write_text(
        json.dumps(settings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    render_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
