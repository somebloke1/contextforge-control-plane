#!/usr/bin/env python3
"""Render OpenCode semantic model config from runtime env."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


def effective_sticky_key() -> str:
    base = os.environ.get("OPENROUTER_STICKY_KEY", "contextforge-semantic-test")
    epoch_seconds = int(os.environ.get("OPENROUTER_STICKY_EPOCH_SECONDS", "7200"))
    if epoch_seconds <= 0:
        return base
    bucket = int(time.time() // epoch_seconds)
    return f"{base}-e{bucket}"


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
    model_id = os.environ.get("OPENROUTER_OPENCODE_MODEL", "~google/gemini-2.5-flash-lite")
    route = os.environ.get("OPENROUTER_PROVIDER_ROUTE", "google-ai-studio")
    data["model"] = os.environ.get("CONTEXTFORGE_OPENCODE_DEFAULT_MODEL", f"openrouter/{model_id}")
    provider = data.setdefault("provider", {}).setdefault("openrouter", {})
    provider["models"] = {
        model_id: {
            "name": os.environ.get("CONTEXTFORGE_TEST_MODEL_NAME", "Configured semantic-test model via OpenRouter"),
            "limit": {
                "context": int(os.environ.get("CONTEXTFORGE_TEST_CONTEXT_WINDOW", "1048576")),
                "output": int(os.environ.get("CONTEXTFORGE_TEST_MAX_TOKENS", "65535")),
            },
            "options": {
                "provider": {
                    "only": [route],
                    "order": [route],
                    "allow_fallbacks": False,
                }
            },
            "headers": {
                "x-session-id": effective_sticky_key(),
            },
        }
    }
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_auth() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        return
    target = Path("/home/agent/.local/share/opencode/auth.json")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = {}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["openrouter"] = {"type": "api", "key": os.environ["OPENROUTER_API_KEY"]}
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    target.chmod(0o600)


def main() -> int:
    render_config()
    write_auth()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
