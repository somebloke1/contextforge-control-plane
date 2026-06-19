#!/usr/bin/env python3
"""OpenCode hook that returns ContextForge project initialization guidance."""

from __future__ import annotations

import contextlib
import os


def _load_codex_project_init_hook():
    with open(os.devnull, "w", encoding="utf-8") as devnull, contextlib.redirect_stderr(devnull):
        import codex_project_init_hook

    return codex_project_init_hook


codex_project_init_hook = _load_codex_project_init_hook()

OPENCODE_HOOK_EVENTS = frozenset({"chat.message", "session.created"})


def main() -> int:
    return codex_project_init_hook.main_for_events(OPENCODE_HOOK_EVENTS, suppress_output=True, target_client="opencode")


if __name__ == "__main__":
    raise SystemExit(main())
