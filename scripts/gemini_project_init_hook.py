#!/usr/bin/env python3
"""Gemini CLI hook that injects ContextForge project initialization guidance."""

from __future__ import annotations

import contextlib
import os


def _load_codex_project_init_hook():
    with open(os.devnull, "w", encoding="utf-8") as devnull, contextlib.redirect_stderr(devnull):
        import codex_project_init_hook

    return codex_project_init_hook


codex_project_init_hook = _load_codex_project_init_hook()


GEMINI_HOOK_EVENTS = frozenset({"SessionStart", "BeforeAgent"})


def main() -> int:
    return codex_project_init_hook.main_for_events(GEMINI_HOOK_EVENTS, suppress_output=True, target_client="gemini")


if __name__ == "__main__":
    raise SystemExit(main())
