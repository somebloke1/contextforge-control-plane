"""Shared client model defaults for Docker dialogue harness runners."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any


MODEL_ENV = Path("env/semantic-model.env")
MAKE_MODEL_ENV_SCRIPT = Path("scripts/make-semantic-model-env.sh")


def ensure_semantic_model_env(
    harness_root: Path,
    *,
    client: str | None = None,
    commands: list[dict[str, Any]] | None = None,
    runner: Any | None = None,
    timeout: int = 60,
) -> None:
    """Generate the ignored semantic model env for model-backed client runs."""

    if client == "codex":
        return
    if (harness_root / MODEL_ENV).exists():
        return
    script = harness_root / MAKE_MODEL_ENV_SCRIPT
    if runner is None:
        raise RuntimeError(f"{MODEL_ENV} is missing; run {script}")
    if commands is None:
        raise RuntimeError("commands list is required when runner is provided")
    runner([str(script)], cwd=harness_root, timeout=timeout, commands=commands)


def pi_command_prefix(session_id: str) -> str:
    provider = "${CONTEXTFORGE_PI_DEFAULT_PROVIDER:-openrouter-gemini-flash-lite}"
    model = "${CONTEXTFORGE_PI_DEFAULT_MODEL:-${OPENROUTER_MODEL:-google/gemini-2.5-flash-lite}}"
    return (
        "cd /workspace && "
        f'pi --provider "{provider}" --model "{model}" '
        f"--session-id {shlex.quote(session_id)} --mode json"
    )


def opencode_model_arg() -> str:
    return "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL:-openrouter/google/gemini-2.5-flash-lite}"


def opencode_command_prefix(session_id: str | None = None, *, create_session: bool = False) -> str:
    session_arg = "" if create_session or not session_id else f"--session {shlex.quote(session_id)} "
    return (
        "cd /workspace && "
        f"opencode run {session_arg}--dir /workspace --dangerously-skip-permissions "
        f'--model "{opencode_model_arg()}" --agent build --format json'
    )
