# Live ContextForge Service Menu Defect - 2026-06-20

## Scope

Project-init service menus must be generated from the current service set
published on the active ContextForge gateway.

This is a deferred defect recorded after Codex reached UC1 parity with Pi and
OpenCode at the current project-init behavior level.

GitHub owner: https://github.com/somebloke1/contextforge-control-plane/issues/288

## Requirement

When a supported target client enters project init, the helper must discover
the available service menu from live ContextForge-published service state. The
menu must not be a static predefined list, a hard-coded readiness matrix, or a
client-local snapshot that can drift from the gateway.

The helper may still enrich live service records with project-local readiness,
client-adapter support, safe display text, and scoped installation effects, but
the service population itself must come from the active ContextForge service
set.

## Current Boundary

UC1 Codex parity was accepted only at the current behavior boundary:

- Pi, OpenCode, and Codex can complete the install-only project-init story for
  `context7:canonical`;
- the accepted UC1 story ends at installed plus reload/new-session-required;
- the acceptance does not claim live ContextForge service-menu sourcing.

## Failure Mode

A static or readiness-matrix menu can:

- offer services that are not actually published by the current ContextForge
  gateway;
- omit newly published services;
- hide drift between service registration and client activation;
- make later readiness reports appear stronger than the live gateway state;
- cause agents to pass project-init dialogue tests against an obsolete menu.

## Expected Remediation

Implement a live service-menu source path that:

- queries the active ContextForge gateway or its authoritative local service
  publication source;
- maps live service records into helper-owned project-init choices;
- preserves project-local approval/apply boundaries;
- preserves cross-client projection/alignment logic from #285/#286/#287;
- degrades honestly when the gateway cannot be reached;
- does not mutate registry, backend, trust, secrets, or global client config
  during menu discovery;
- includes deterministic structure/runtime tests plus non-Spark semantic
  dialogue evaluation for any model-dependent client interaction.

## Non-Goals

- Do not reintroduce post-install validation/probing into UC1.
- Do not block the already accepted Codex UC1 parity boundary on this deferred
  defect.
- Do not create duplicate project service identities per client.
- Do not replace the project service graph or client projection model.

## Related Evidence

- Codex UC1 parity supplement:
  `run/holistic-orchestrator/reports/uc1-codex-parity-acceptance-20260620T121626Z.md`
- Cross-client disparity readback:
  `docs/use-cases/cross-client-disparity-readback-acceptance-20260620.md`
- New-client alignment import:
  `docs/use-cases/new-client-alignment-import-acceptance-20260620.md`
