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
MODEL_METADATA = {
    "codex/gpt-5.6-terra": ("GPT-5.6 Terra (human)", 1050000),
    "codex/gpt-5.6-luna": ("GPT-5.6 Luna (blind/default)", 1050000),
    "codex/gpt-5.6-sol": ("GPT-5.6 Sol (evaluator)", 350000),
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
PROVIDER_KEYS = {"baseUrl", "api", "apiKey", "authHeader", "compat", "models"}
MODEL_KEYS = {"id", "name", "reasoning", "thinkingLevelMap", "input", "contextWindow", "maxTokens"}
CANONICAL_SETTINGS = {
    "defaultProvider": "litellm",
    "defaultModel": "codex/gpt-5.6-luna",
    "defaultThinkingLevel": "medium",
    "enabledModels": [
        "litellm/codex/gpt-5.6-terra",
        "litellm/codex/gpt-5.6-luna",
        "litellm/codex/gpt-5.6-sol",
    ],
}


def expected_thinking(model: str) -> str:
    try:
        return MODEL_THINKING[model]
    except KeyError as exc:
        raise ValueError(f"unsupported Pi sandbox model: {model!r}") from exc


def validate_models(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) != {"providers"}:
        raise ValueError("canonical Pi models must contain only providers")
    providers = data.get("providers")
    if not isinstance(providers, dict) or set(providers) != {"litellm"}:
        raise ValueError("Pi sandbox models must contain only the litellm provider")
    provider = providers["litellm"]
    if not isinstance(provider, dict) or set(provider) != PROVIDER_KEYS:
        raise ValueError("canonical Pi litellm provider keys do not match policy")
    if provider.get("baseUrl") != "$LITELLM_BASE_URL" or provider.get("apiKey") != "$LITELLM_API_KEY":
        raise ValueError("canonical Pi provider must use only LiteLLM env references")
    if provider.get("authHeader") is not True:
        raise ValueError("canonical Pi provider must use the authorization header")
    if provider.get("api") != "openai-responses":
        raise ValueError("Pi sandbox models must use OpenAI Responses")
    compat = provider.get("compat")
    if not isinstance(compat, dict) or compat != {
        "supportsDeveloperRole": True,
        "supportsReasoningEffort": True,
    }:
        raise ValueError("canonical Pi compatibility contract mismatch")
    models = provider.get("models")
    if not isinstance(models, list) or len(models) != len(MODEL_THINKING):
        raise ValueError("Pi sandbox models must contain exactly the approved LiteLLM set")
    by_id: dict[str, dict[str, Any]] = {}
    for model in models:
        if not isinstance(model, dict) or set(model) != MODEL_KEYS or not isinstance(model.get("id"), str):
            raise ValueError("canonical Pi model record keys do not match policy")
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
        expected_name, expected_context = MODEL_METADATA[model_id]
        if (
            model.get("name") != expected_name
            or model.get("input") != ["text", "image"]
            or model.get("contextWindow") != expected_context
            or model.get("maxTokens") != 128000
        ):
            raise ValueError(f"canonical Pi model metadata mismatch for {model_id!r}")
    return provider


def validate_settings(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict) or settings != CANONICAL_SETTINGS:
        raise ValueError("canonical Pi settings do not match the LiteLLM-only policy")
    return settings


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

    settings = validate_settings(json.loads(settings_source.read_text(encoding="utf-8")))
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
