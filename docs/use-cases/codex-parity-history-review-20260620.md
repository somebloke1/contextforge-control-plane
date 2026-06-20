# Codex Parity History Review - 2026-06-20

## Purpose

This review records how the accepted Pi/OpenCode UC1-13 history should guide
Codex bring-up after Codex UC1 parity.

## Reviewed Sources

- `docs/use-cases/dependency-mesh.md`
- `docs/use-cases/use-case-1/package.md`
- `docs/use-cases/use-case-2/package.md`
- `docs/use-cases/use-case-3/package.md`
- `docs/use-cases/use-case-4/package.md`
- `docs/use-cases/use-case-5/package.md`
- `docs/use-cases/use-case-6/package.md`
- `docs/use-cases/use-case-7/package.md`
- `docs/use-cases/use-case-8/package.md`
- `docs/use-cases/use-case-9/package.md`
- `docs/use-cases/use-case-10/package.md`
- `docs/use-cases/use-case-11/package.md`
- `docs/use-cases/use-case-12/package.md`
- `docs/use-cases/use-case-13/package.md`
- `docs/use-cases/use-case-12/controller-acceptance-20260620.md`
- `docs/use-cases/use-case-13/controller-acceptance-20260620.md`
- `run/holistic-orchestrator/reports/uc1-controller-acceptance-20260620T010301Z.md`
- `run/holistic-orchestrator/reports/uc1-codex-parity-acceptance-20260620T121626Z.md`

## Transferable Lessons

- Start Codex from the same dependency layer order as Pi/OpenCode. Do not jump
  to UC14/UC15 or high-level readiness before initialized-project readback and
  capability discovery are proven.
- Preserve the split between deterministic structure and semantic judgment.
  Runner/verifier code may check command status, JSON shape, metadata, session
  continuity, and artifact presence. It must not score free-form assistant
  meaning.
- Keep Codex Docker-only. The host Codex instance is not a test surface.
- Use the authenticated Codex Docker baseline with OAuth/ChatGPT subscription
  auth, no API-key env propagation, and model `gpt-5.4-mini`.
- Extend each use-case runner only as far as the use-case story requires.
  Later claims such as live tool use, cross-client alignment, refresh behavior,
  or readiness aggregation belong to later cases.
- When subagent semantic evaluation is unavailable, record a contained
  OAuth-backed Codex Docker evaluator fallback explicitly and do not pretend it
  is a delegated subagent report.
- Carry #288 as a deferred defect. The current parity sequence aligns clients
  at the present project-init behavior level; it does not claim live
  ContextForge-published service-menu sourcing.

## Next Target Decision

The next Codex parity target is UC2.

Rationale:

- UC2 is the first initialized-project substrate after UC1.
- UC2 proves Codex can start from an already initialized project and avoid
  restarting first-run service selection.
- UC2 does not require actual ContextForge tool invocation, cross-client
  comparison, project-state mutation, service refresh, onboarding, or readiness
  reporting.
- UC3, UC7, UC4, and later use cases depend on this initialized-project
  readback behaving honestly.

## Tentative Codex Parity Sequence

1. UC2 - initialized-project available-tool readback for Codex.
2. UC3 - broad project capability discovery for Codex.
3. UC7 - current ContextForge state/readiness-layer readback for Codex.
4. UC4 - governance service route through Codex, if the Codex adapter exposes
   the mentality route in the initialized fixture.
5. UC5/UC6 - service-selection mutation and negative-choice shapes for Codex.
6. UC8/UC11 - actual Context7 tool use and guidance for Codex.
7. UC9/UC10 - revisit cross-client consistency/refresh with Codex added only
   after per-client initialized readback and projection behavior are proven.
8. UC12/UC13 - extend only after earlier Codex substrate is stable.
9. UC14/UC15 - readiness and handoff after all required client evidence is
   integrated.

The sequence is tentative, not dogmatic. A shared-surface defect can promote a
smaller regression, but the controller should avoid skipping substrate layers.
