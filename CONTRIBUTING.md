# Contributing to ContextForge Control Plane

Thank you for your interest in this repository. This workspace builds and
operates a clean, stock IBM ContextForge MCP Gateway. Before contributing,
please read this guide and [`AGENTS.md`](./AGENTS.md), which is the canonical
source of agent and operator policy.

## Repository intent

- ContextForge registry/catalog records own the assistant-facing service
  offering truth. Repository manifests and scripts support backend runtime and
  provisioning; they are **not** the service menu.
- Prefer stock ContextForge configuration and native registration over
  project-local duplicate gateway, translator, or registration implementations.
- Treat external MCP client configs (Codex, Claude, Gemini, OpenCode, Pi) as
  discovery sources only. Do not create services named after a client merely
  because its config mentioned the same backend.

## Branch policy

- `main` is protected by tracked hooks in [`.githooks/`](./.githooks). Do not
  commit directly to `main` except for explicit administrative bootstrap work
  with `ALLOW_MAIN_COMMIT=1`.
- `dev-root` is the root branch for agent- and feature-created work.
- Create your work branch from `dev-root`, not `main`:

  ```sh
  git switch dev-root
  git switch -c <your-branch>
  ```

- Open a pull request against `dev-root`. Direct pushes to `main` are blocked by
  the local `pre-push` hook unless `ALLOW_MAIN_PUSH=1` is set for bootstrap.
- Enable the tracked hooks locally once:

  ```sh
  git config core.hooksPath .githooks
  ```

## Python environment

- Every branch/worktree must have its own local `.venv`; no branch is left
  without one.

  ```sh
  uv venv .venv
  uv pip install --python .venv/bin/python mcp-contextforge-gateway
  ```

- Use `uv pip install --python .venv/bin/python ...` for dependency changes.
- Do not assume `python -m pip` exists until verified.
- Keep `.venv/` out of Git.

## Secrets and local state

- **Never commit** real API keys, bearer tokens, passwords, generated JWTs, or
  client-local secret values.
- Runtime env files, tokens, databases, logs, generated inventories, and
  installed systemd state are local operational state and must stay out of Git.
  Keep them in ignored local paths such as `config/contextforge.env`,
  `server-instances/<name>/.env`, or installed `/etc/contextforge/*.env`.
- Inventory outputs ending in `.local.json` are host-specific and ignored.
- Generated diagnostics and temporary assets under `generated/` are ignored by
  default unless intentionally promoted to tracked templates.

## Governance ledgers

Durable project continuity lives in three ledgers. Prefer editing them through
the repeatable scripts rather than by hand:

- [`DECISIONS.md`](./DECISIONS.md) — accepted/superseded decisions.
- [`ABEYANT_INTENTIONS.md`](./ABEYANT_INTENTIONS.md) — parked real intentions.
- [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md) — questions kept visible.

- Preserve the `governance-crud` entry anchors and metadata shape.
- Use [`scripts/governance_crud.py`](./scripts/governance_crud.py) for
  repeatable ledger edits and [`scripts/governance_mcp.py`](./scripts/governance_mcp.py)
  for the repo-local MCP service named `mentality`.
- Preserve old entries; mark them answered, superseded, or closed instead of
  deleting them.

## Changing ContextForge-owned state

- Use [`CONTEXTFORGE_SCHEMA.md`](./CONTEXTFORGE_SCHEMA.md) as the local API
  schema and method reference before automating registry, token, team, or
  Admin/API operations.
- Change ContextForge-owned state through the ContextForge API or Admin UI
  behavior. **Direct ContextForge database writes are prohibited**; direct
  database reads are diagnostic only.

## Verification expectations

- Use current local files, command output, service state, and HTTP probes as the
  authority.
- Verify the clean stock gateway before registering any external services.
- Deterministic tests may establish structure, state, transport, command
  completion, JSON shape, endpoint reachability, and evidence packaging. They
  must not judge free-form assistant meaning or user-facing success; semantic
  evaluation must be performed by an appropriate model or human evaluator.
- Do not add harness-only, hidden, or non-product prompts to make a tested
  assistant appear to pass. Improve shipped helper/tool output or product
  guidance only when that surface is genuinely delivered to ordinary users.

## Submitting changes

1. Open or pick a GitHub issue describing the intended change.
2. Branch from `dev-root`.
3. Make focused commits. Keep runtime secrets and local state out.
4. Run the relevant local validation in `.venv`.
5. Open a pull request against `dev-root` and use the pull request template to
   describe verification evidence and any non-actions/boundaries.

By contributing, you agree that your contributions are licensed under the
project's [MIT License](./LICENSE).
