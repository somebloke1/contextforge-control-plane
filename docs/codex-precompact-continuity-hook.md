# ContextForge Codex Pre-Compaction Continuity Hook

ContextForge uses project-local Codex hooks to preserve roadmap continuity
around long-thread compaction. A `PreCompact` hook writes local continuity state
before compaction, and a `SessionStart` hook with matcher `compact` points the
post-compaction agent at that state through Codex's documented additional
context path. The hooks are configured in `.codex/config.toml` and run only when
this trusted project `.codex` layer is active.

The hook does not replace Codex's default compaction prompt. It does not set
`compact_prompt`, `experimental_compact_prompt_file`, or
`model_auto_compact_token_limit`. Those settings are intentionally left unset so
Codex's default compaction process remains authoritative.

## Behavior

- Event: `PreCompact`
- Matcher: `manual|auto`
- Event: `SessionStart`
- Matcher: `compact`
- Script: `.codex/hooks/contextforge_precompact_continuity.py`
- Generated state: `run/codex-precompact-continuity/`

On each `PreCompact` event, the hook writes an event snapshot and, when Codex
provides a session or thread id, a session-scoped latest pointer:

- `run/codex-precompact-continuity/events/<event-id>.json`
- `run/codex-precompact-continuity/sessions/<session-key>/latest.json`
- `run/codex-precompact-continuity/sessions/<session-key>/latest.md`

The `run/` directory is ignored local state. These snapshots are evidence for
the next operator or post-compaction agent; they are not tracked source files.
If a compaction payload does not include a session or thread id, the hook writes
only the event snapshot and does not create a shared `unknown` latest pointer.

## Standard Repo Assets

The continuity mechanism is a standard repository process, even though its
generated snapshots are ignored runtime state. The tracked assets that define
the process are:

- `.codex/config.toml`: project-local hook wiring for `PreCompact` and compact
  `SessionStart`.
- `.codex/hooks/contextforge_precompact_continuity.py`: hook implementation.
- `schemas/codex-precompact-continuity.schema.json`: snapshot contract for
  generated JSON evidence.
- `docs/codex-precompact-continuity-hook.md`: operator runbook and promotion
  boundary.
- `tests/test_codex_precompact_continuity_hook.py`: regression tests.
- `docs/project-status-roadmap-2026-06-16.md`: goal-loop and roadmap authority.

Every generated snapshot records these standard repo refs when they exist in
the active checkout. That keeps future agents tethered to the repository
process instead of treating one ignored `run/` file as the project mission.

## Promotion Boundary

Promote reusable process, schema, template, validation, and runbook material
into tracked source. Do not commit raw session snapshots, transcript paths,
dirty-worktree inventories, local lock files, generated diagnostics, secrets, or
other checkout-specific evidence by default.

Generated continuity state remains under:

- `run/codex-precompact-continuity/events/*.json`
- `run/codex-precompact-continuity/sessions/*/latest.json`
- `run/codex-precompact-continuity/sessions/*/latest.md`
- `run/codex-precompact-continuity/*.local.lock`

A raw snapshot may be promoted only after a deliberate sanitization/review step
and only when it has durable value beyond the originating session.

## Transitional State Safety

Snapshot `repo_root`, branch, worktree, and dirty-status fields are
point-in-time evidence. They are not target architecture and must not be used to
normalize dependence on a transitional checkout such as the legacy
`/home/dgk/workspace/legacy-controlplane-archive` path.

During migration, active snapshots may still exist in a transitional worktree.
Use them to recover continuity, then return to the tracked standard repo
assets, current formal goal, and current roadmap evidence. The standard process
is portable; a snapshot's originating path is evidence to reconcile or retire.

The `PreCompact` hook returns only common hook output fields. Codex currently
does not document `PreCompact` support for hook-specific additional context.
After compaction, the `SessionStart` hook for `source=compact` returns
`hookSpecificOutput.additionalContext`, which Codex documents for
`SessionStart`, only for the matching session key.

## Non-Commandeering Semantics

The hook is project-local but session-scoped. An ad-hoc Codex session can write
its own continuity evidence under its own session key, but it cannot replace a
project-global roadmap pointer because the hook does not maintain one. A
post-compaction `SessionStart` event reads only the latest snapshot for the same
session key and treats that snapshot as additive evidence.

The default Codex compaction summary, the active user-selected goal, and the
current thread context remain authoritative. The hook is a continuity aid, not a
mission handoff mechanism.

## Retention

The hook enforces bounded local retention while holding the project-local lock:

- most recent event snapshots: `100`
- most recent session latest directories: `50`

The snapshot for the current event and current session, when one exists, is
always retained. Older event files and stale session directories are best-effort
removed from ignored `run/` state. The hook also removes stale root-level
`latest.json` and `latest.md` files left by earlier hook versions, because
current continuity pointers are session-scoped only.

## Idempotency

The hook derives a stable event id from the repo root, event, trigger, session
id, turn id, and payload key set. It does not persist caller-provided run-id
values as event ids or filenames. Re-running the same hook input updates the
same event record and session `latest.*` files rather than creating duplicate
records.

The hook serializes writes with a project-local lock file and writes files
atomically before replacing the target path.

## Continuity Contract

The snapshot reminds a post-compaction agent to:

- preserve the ContextForge naming boundary;
- refresh current evidence before trusting roadmap claims;
- preserve unrelated dirty work and issue-sliced branch topology;
- keep Codex's default compaction prompt intact;
- call `get_goal`, reconcile it with the live user mission, and activate any
  refined successor goal before continuing roadmap work;
- run goal maintenance/refinement before moving to the next roadmap loop.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_codex_precompact_continuity_hook -v
```

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile .codex/hooks/contextforge_precompact_continuity.py tests/test_codex_precompact_continuity_hook.py
```

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import tomllib
from pathlib import Path

config = tomllib.loads(Path(".codex/config.toml").read_text())
assert config["hooks"]["PreCompact"][0]["matcher"] == "manual|auto"
assert config["hooks"]["SessionStart"][0]["matcher"] == "compact"
PY
```

`codex --strict-config doctor --json` is still useful for general Codex config
health, but on this host it reports the active user config path and may fail on
environment warnings such as `TERM=dumb`. Use the `tomllib` probe above for the
project hook config parse/readback check.

After the hook is first loaded in Codex, review and trust it with `/hooks`.
