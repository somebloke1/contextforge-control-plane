---
name: contextforge-governance
description: Maintain this repository's governance ledgers and mentality MCP workflow. Use when Codex needs to create, read, update, delete, reconcile, or summarize DECISIONS.md, ABEYANT_INTENTIONS.md, OPEN_QUESTIONS.md, governance-crud anchors, durable project continuity records, or the repo-local mentality service.
---

# ContextForge Governance

Use the governance ledgers as durable project memory. Prefer the repo scripts or
the `mentality` MCP service over manual Markdown edits when changing entries.

## Ledgers

- `DECISIONS.md`: accepted/superseded/rejected project decisions.
- `ABEYANT_INTENTIONS.md`: deferred intentions and not-now work.
- `OPEN_QUESTIONS.md`: tracked questions, including answered ones retained for
  continuity.

Each entry must preserve the `governance-crud:start` and `governance-crud:end`
anchors and metadata shape.

## Workflow

1. Read the relevant ledger entry before changing it.
2. Use `scripts/governance_crud.py` for repeatable edits when possible.
3. Keep statuses finite and explicit. Do not delete useful history just because
   a question is answered or a decision is superseded.
4. Keep entries grounded in repo facts, command output, or explicit user
   decisions.
5. Avoid committing secrets, local state, generated diagnostics, or token
   material in ledger text.
6. If using the `mentality` MCP service, use read/list for review tasks and
   create/update/delete only when the user asked for ledger mutation.

## Quick Commands

Inspect governance script help before mutation:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/governance_crud.py --help
```

Run governance-related tests after script or ledger-shape changes:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_control_plane_service_memory tests.test_control_plane_project_state -v
```

Read [ledger-shape.md](references/ledger-shape.md) before creating or updating
entries.
