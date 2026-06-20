# Feature Request: Agent-Invokable Project Reset Helper - 2026-06-20

## Request

Add an agent-invokable ContextForge helper function, available across supported
agent/client types, that resets the current project context for that agent
session to a clean base state.

## Problem

ContextForge client/session tests repeatedly need a reliable way to return the
current project to a known base state without relying on ad hoc cleanup,
manual delta calculation, or client-specific shell recipes.

The project already treats idempotency as an operating axiom: deterministic
state reset should be handled by deterministic tooling, while language models
should handle semantic judgment. Without a first-class helper reset operation,
agents and users are tempted to approximate cleanup through fragile path,
volume, config, or state-file assumptions.

## Desired Behavior

The helper should expose an agent-callable reset operation that:

- operates relative to the agent session's current project root;
- is available through the ContextForge helper surface for Pi, OpenCode, Codex,
  and future supported clients;
- returns the project to a documented base state suitable for a new
  project-init or use-case test pass;
- is idempotent and safe to call repeatedly;
- preserves evidence when requested or when policy requires preservation;
- reports exactly what was reset, preserved, skipped, and refused;
- refuses unsafe roots, symlink escapes, sibling checkouts, user-global config,
  secrets, OAuth/auth state, registry state, runtime services, and unrelated
  client state unless an explicit separate approval gate exists.

## Scope Questions

- Should the helper reset only project-local state such as `.project/`,
  project-local client config, and harness workspace artifacts?
- Should it have named reset profiles such as `project_init_base`,
  `client_projection_base`, `dialogue_test_base`, and `preserve_evidence`?
- How should it coordinate with Docker harness resets that also reset client
  home volumes?
- Should a reset receipt be persisted in project-local ignored state for later
  audit?

## Acceptance Criteria

- A public helper operation exists for each supported client surface.
- The operation derives the target project root from the current agent/session
  context unless an explicit safe root is provided.
- Reset behavior is profile-driven, documented, and idempotent.
- The helper emits structured reset receipts and a concise
  `assistant_visible_response`.
- Tests prove safe-root enforcement, idempotency, preservation behavior,
  refusal of unsafe/global surfaces, and parity across client wrappers.
- Use-case runners can invoke the helper reset instead of maintaining bespoke
  project-local cleanup logic where appropriate.

## Non-Goals

- Do not reset user-global client authentication.
- Do not delete Docker volumes, containers, systemd units, ContextForge
  registry entries, secrets, OAuth tokens, or external service state.
- Do not treat reset as a semantic validation or readiness gate.

## Related Principle

Idempotency belongs in deterministic tooling. Agents should not infer or
pattern-match the cleanup delta needed to make a project clean when a
deterministic helper can establish and report the base state directly.
