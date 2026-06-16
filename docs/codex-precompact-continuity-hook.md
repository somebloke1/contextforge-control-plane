# ContextForge Codex Pre-Compaction Continuity Hook

ContextForge uses a project-local Codex `PreCompact` hook to preserve roadmap
continuity before Codex compacts a long thread. The hook is configured in
`.codex/config.toml` and runs only when this trusted project `.codex` layer is
active.

The hook does not replace Codex's default compaction prompt. It does not set
`compact_prompt`, `experimental_compact_prompt_file`, or
`model_auto_compact_token_limit`. Those settings are intentionally left unset so
Codex's default compaction process remains authoritative.

## Behavior

- Event: `PreCompact`
- Matcher: `manual|auto`
- Script: `.codex/hooks/contextforge_precompact_continuity.py`
- Generated state: `run/codex-precompact-continuity/`

On each compaction event, the hook writes:

- `run/codex-precompact-continuity/latest.json`
- `run/codex-precompact-continuity/latest.md`
- `run/codex-precompact-continuity/events/<event-id>.json`

The `run/` directory is ignored local state. These snapshots are evidence for
the next operator or post-compaction agent; they are not tracked source files.

## Idempotency

When Codex supplies a hook run id, that id is used as the event file name. When
it does not, the hook derives a stable event id from the repo root, event,
trigger, session id, and payload key set. Re-running the same hook input updates
the same event record and `latest.*` files rather than creating duplicate
records.

The hook serializes writes with a project-local lock file and writes files
atomically before replacing the target path.

## Continuity Contract

The snapshot reminds a post-compaction agent to:

- preserve the ContextForge naming boundary;
- refresh current evidence before trusting roadmap claims;
- preserve unrelated dirty work and issue-sliced branch topology;
- keep Codex's default compaction prompt intact;
- run goal maintenance/refinement before moving to the next roadmap loop.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_codex_precompact_continuity_hook -v
```

```sh
codex --strict-config doctor
```

`codex doctor` may still report environment warnings unrelated to this hook,
such as terminal type, auth mode, or available updates. The hook-specific check
is that strict config accepts the project `.codex/config.toml`.

After the hook is first loaded in Codex, review and trust it with `/hooks`.
