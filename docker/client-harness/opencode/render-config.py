#!/usr/bin/env python3
"""Render the canonical LiteLLM-only OpenCode sandbox config."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


MODEL_VARIANTS = {
    "codex/gpt-5.6-terra": "high",
    "codex/gpt-5.6-luna": "medium",
    "codex/gpt-5.6-sol": "high",
}
DEFAULT_MODEL = "codex/gpt-5.6-luna"
DEFAULT_BASE_URL = "http://host.docker.internal:3333/v1"


def opencode_model_id(raw_value: str | None, *, default: str = DEFAULT_MODEL) -> str:
    value = (raw_value or f"litellm/{default}").strip()
    model = value.removeprefix("litellm/")
    if model not in MODEL_VARIANTS or value not in {model, f"litellm/{model}"}:
        raise ValueError(f"unsupported OpenCode sandbox model: {value!r}")
    return f"litellm/{model}"


def render_config() -> None:
    source = Path(os.environ.get("CONTEXTFORGE_OPENCODE_CONFIG_SOURCE", "/config/opencode/opencode.json"))
    target = Path(
        os.environ.get(
            "CONTEXTFORGE_OPENCODE_CONFIG_TARGET",
            "/home/agent/.config/opencode/opencode.json",
        )
    )
    if not target.exists() and source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    data = json.loads(target.read_text(encoding="utf-8"))
    default_model = opencode_model_id(os.environ.get("CONTEXTFORGE_OPENCODE_DEFAULT_MODEL"))
    small_model = opencode_model_id(
        os.environ.get("CONTEXTFORGE_OPENCODE_SMALL_MODEL"),
        default=default_model.removeprefix("litellm/"),
    )
    model_component = default_model.removeprefix("litellm/")
    expected_variant = MODEL_VARIANTS[model_component]
    variant = os.environ.get("CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT", expected_variant).strip()
    if variant != expected_variant:
        raise ValueError(f"variant {variant!r} does not match {model_component!r} ({expected_variant!r})")

    source_provider = data.get("provider", {}).get("litellm")
    if not isinstance(source_provider, dict):
        raise ValueError("canonical OpenCode config is missing the litellm provider")
    if source_provider.get("npm") != "@ai-sdk/openai":
        raise ValueError("canonical OpenCode config must use @ai-sdk/openai")
    source_models = source_provider.get("models")
    if not isinstance(source_models, dict) or set(source_models) != set(MODEL_VARIANTS):
        raise ValueError("canonical OpenCode config must contain exactly the approved LiteLLM models")
    for model, expected in MODEL_VARIANTS.items():
        model_config = source_models[model]
        if not isinstance(model_config, dict) or model_config.get("reasoning") is not True:
            raise ValueError(f"canonical OpenCode reasoning must be enabled for {model!r}")
        variants = model_config.get("variants")
        if not isinstance(variants, dict) or set(variants) != {expected}:
            raise ValueError(f"canonical OpenCode reasoning variant mismatch for {model!r}")
        variant_config = variants[expected]
        if (
            not isinstance(variant_config, dict)
            or set(variant_config) != {"reasoningEffort"}
            or variant_config.get("reasoningEffort") != expected
        ):
            raise ValueError(f"canonical OpenCode reasoning effort mismatch for {model!r}")

    provider = dict(source_provider)
    provider["models"] = {model: source_models[model] for model in MODEL_VARIANTS}
    provider["whitelist"] = list(MODEL_VARIANTS)
    options = dict(provider.get("options") or {})
    base_url = os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    if base_url != DEFAULT_BASE_URL:
        raise ValueError(f"OpenCode sandbox LiteLLM endpoint must be {DEFAULT_BASE_URL!r}")
    options["baseURL"] = base_url
    if os.environ.get("LITELLM_API_KEY"):
        options["apiKey"] = os.environ["LITELLM_API_KEY"]
    provider["options"] = options

    data["enabled_providers"] = ["litellm"]
    data["model"] = default_model
    data["small_model"] = small_model
    data["provider"] = {"litellm": provider}
    agents = data.setdefault("agent", {})
    build_agent = agents.setdefault("build", {})
    build_agent["model"] = default_model
    build_agent["variant"] = variant
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    render_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
