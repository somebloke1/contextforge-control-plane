#!/usr/bin/env python3
"""Render the canonical LiteLLM-only OpenCode sandbox config."""

from __future__ import annotations

import json
import os
from pathlib import Path


MODEL_VARIANTS = {
    "codex/gpt-5.6-terra": "high",
    "codex/gpt-5.6-luna": "medium",
    "codex/gpt-5.6-sol": "high",
}
MODEL_NAMES = {
    "codex/gpt-5.6-terra": "GPT-5.6 Terra (human)",
    "codex/gpt-5.6-luna": "GPT-5.6 Luna (blind/default)",
    "codex/gpt-5.6-sol": "GPT-5.6 Sol (evaluator)",
}
DEFAULT_MODEL = "codex/gpt-5.6-luna"
DEFAULT_BASE_URL = "http://host.docker.internal:3333/v1"
PROVIDER_KEYS = {"name", "npm", "options", "whitelist", "models"}
MODEL_KEYS = {"name", "reasoning", "variants"}
TOP_LEVEL_KEYS = {"$schema", "model", "small_model", "enabled_providers", "agent", "mcp", "provider"}
EXPECTED_MCP = {
    "contextforge-helper": {
        "type": "local",
        "enabled": True,
        "command": [
            "{env:CONTEXTFORGE_HELPER_PYTHON}",
            "{env:CONTEXTFORGE_HELPER_SCRIPT}",
        ],
        "environment": {
            "CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE": "opencode",
            "CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT": "1",
            "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": (
                "/home/agent/.local/state/contextforge-client-harness-runtime/"
                "project-init/opencode-latest-user-message.json"
            ),
            "CONTEXTFORGE_OPENCODE_DENY_RAW_WORKSPACE_MUTATION": "1",
            "CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER": "1",
            "MCP_WRAPPER_LOG_LEVEL": "INFO",
            "XDG_RUNTIME_DIR": "/home/agent/.local/state/contextforge-client-harness-runtime",
        },
    }
}


def opencode_model_id(raw_value: str | None, *, default: str = DEFAULT_MODEL) -> str:
    value = (raw_value or f"litellm/{default}").strip()
    model = value.removeprefix("litellm/")
    if model not in MODEL_VARIANTS or value not in {model, f"litellm/{model}"}:
        raise ValueError(f"unsupported OpenCode sandbox model: {value!r}")
    return f"litellm/{model}"


def validate_source(data: object) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(data, dict):
        raise ValueError("canonical OpenCode config must be an object")
    if set(data) != TOP_LEVEL_KEYS:
        raise ValueError("canonical OpenCode top-level keys do not match policy")
    if data.get("$schema") != "https://opencode.ai/config.json":
        raise ValueError("canonical OpenCode schema mismatch")
    if data.get("mcp") != EXPECTED_MCP:
        raise ValueError("canonical OpenCode MCP configuration mismatch")
    if data.get("enabled_providers") != ["litellm"]:
        raise ValueError("canonical OpenCode config must enable only litellm")
    if data.get("model") != f"litellm/{DEFAULT_MODEL}" or data.get("small_model") != f"litellm/{DEFAULT_MODEL}":
        raise ValueError("canonical OpenCode defaults must use Luna through LiteLLM")
    providers = data.get("provider")
    if not isinstance(providers, dict) or set(providers) != {"litellm"}:
        raise ValueError("canonical OpenCode config must contain only the litellm provider")
    source_provider = providers["litellm"]
    if not isinstance(source_provider, dict) or set(source_provider) != PROVIDER_KEYS:
        raise ValueError("canonical OpenCode provider keys do not match policy")
    if source_provider.get("name") != "LiteLLM" or source_provider.get("npm") != "@ai-sdk/openai":
        raise ValueError("canonical OpenCode provider identity mismatch")
    if source_provider.get("options") != {
        "apiKey": "{env:LITELLM_API_KEY}",
        "baseURL": "{env:LITELLM_BASE_URL}",
    }:
        raise ValueError("canonical OpenCode provider options must use only LiteLLM env references")
    if source_provider.get("whitelist") != list(MODEL_VARIANTS):
        raise ValueError("canonical OpenCode whitelist mismatch")
    agents = data.get("agent")
    if not isinstance(agents, dict) or set(agents) != {"build"}:
        raise ValueError("canonical OpenCode config must contain only the build agent")
    build = agents["build"]
    if not isinstance(build, dict) or build != {
        "model": f"litellm/{DEFAULT_MODEL}",
        "variant": MODEL_VARIANTS[DEFAULT_MODEL],
    }:
        raise ValueError("canonical OpenCode build agent mismatch")
    return source_provider, build


def render_config() -> None:
    source = Path(os.environ.get("CONTEXTFORGE_OPENCODE_CONFIG_SOURCE", "/config/opencode/opencode.json"))
    target = Path(
        os.environ.get(
            "CONTEXTFORGE_OPENCODE_CONFIG_TARGET",
            "/home/agent/.config/opencode/opencode.json",
        )
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    source_provider, _source_build = validate_source(data)
    model_smoke = os.environ.get("CONTEXTFORGE_OPENCODE_MODEL_SMOKE", "0")
    if model_smoke not in {"0", "1"}:
        raise ValueError("CONTEXTFORGE_OPENCODE_MODEL_SMOKE must be 0 or 1")
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

    source_models = source_provider.get("models")
    if not isinstance(source_models, dict) or set(source_models) != set(MODEL_VARIANTS):
        raise ValueError("canonical OpenCode config must contain exactly the approved LiteLLM models")
    for model, expected in MODEL_VARIANTS.items():
        model_config = source_models[model]
        if not isinstance(model_config, dict) or set(model_config) != MODEL_KEYS:
            raise ValueError(f"canonical OpenCode model keys mismatch for {model!r}")
        if model_config.get("name") != MODEL_NAMES[model]:
            raise ValueError(f"canonical OpenCode model name mismatch for {model!r}")
        if model_config.get("reasoning") is not True:
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
    if model_smoke == "1":
        data["mcp"] = {}
    data["provider"] = {"litellm": provider}
    data["agent"] = {"build": {"model": default_model, "variant": variant}}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    render_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
