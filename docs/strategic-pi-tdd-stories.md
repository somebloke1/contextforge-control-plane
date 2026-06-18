# Strategic Pi TDD Stories

Issue: #199

This document records the bounded strategic TDD repertoire for user-observable
Pi plus ContextForge behavior. It does not make the whole project TDD. It
protects the specific user stories that must stay open until the user actually
tests and sees the narrated behavior unfold in an ordinary interactive Pi
session.

The machine-readable catalog is
`tests/fixtures/strategic_pi_tdd_stories.json`.

## Scope

The catalog contains 26 mandatory feature requests:

- #201-#216 are intended-behavior stories.
- #219-#228 are structurally different failure/recovery stories.

Accidental extras #217 and #218 were closed as not planned and are explicitly
not part of this repertoire.

Each story requires:

- a user-perception narration;
- a technology-narration correlation;
- labels `feature-request`, `ideal-form`, and `validation-request`;
- Priority `high` and Risk `Med` in Project #6;
- an open issue until ordinary interactive Pi-session proof exists.

## Closure Gate

These issues must not be closed from source tests, mocks, one-shot prompts,
backend health checks, ContextForge-only readback, Project #6 field state, or
PR merge state alone. Closure requires the user to actually observe the
narrated behavior in an ordinary interactive Pi session.

Use `docs/readiness-claim-guardrails.md` when reporting the evidence layer. The
story catalog is `planned` or `source_ready` evidence only. It is not
`backend_ready`, `contextforge_ready`, `target_client_ready`, or `verified`
runtime proof.

## Failure/Recovery Set

The recovery set deliberately covers different structures:

- #219: unavailable dev gateway at session start;
- #220: corrupt project-state input;
- #221: server-id drift against ContextForge;
- #222: scoped auth expiry during interaction;
- #223: unsafe tool request redirected to a safe path;
- #224: wrapper crash with bounded diagnostics;
- #225: project-root change during a session;
- #226: concurrent stale-plan conflict;
- #227: interrupted apply and recovery journal;
- #228: absent tool admitted as a gap.

## Non-Actions

This catalog does not approve runtime or Docker work, client/global config
mutation, hook trust/state mutation, ContextForge registry mutation, token or
secret handling, helper approve/apply/recovery mutation, Serena provisioning,
or mutation of the retired predecessor checkout.
