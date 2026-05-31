# ContextForge Control-Plane Release Readiness

Run ID: `20260530T202154Z`

This report closes Wave 13 implementation work for the ContextForge
control-plane RFC minimal viable slice. It is an evidence index and readiness
statement for the RFC MVS, not a claim that the repository now contains a
polished production operator CLI.

## Status

- D0-D17 are complete after Wave 12 QA and root adjudication.
- D18 is ready for W13-QA.
- Serena remains declined in this run.
- Known excluded local changes remain outside acceptance: `.project/` and
  `server-instances/context7/README.md`.

## Governance Closeout

W13-A applied the approved Wave 0 governance reconciliation through
`scripts/governance_crud.py`.

Created accepted decisions:

- `dec-20260530-0001`: Adopt the control-plane MVS, roadmap, and acceptance
  gates.
- `dec-20260530-0002`: Use `.project/context_forge_state.json` as sole
  project-init state authority.
- `dec-20260530-0003`: Require receipts, traces, and journals for mutating
  control-plane work.
- `dec-20260530-0004`: Require service-management handoff for host-wide
  catalog mutation.
- `dec-20260530-0005`: Keep service memory reference-only for governance in
  v1.
- `dec-20260530-0006`: Gate local auth, token material, trust, and remote
  exposure separately.

Updated governance entries:

- `oq-20260529-0001` is answered: Codex trust is separate, brokered,
  receipt-backed, and never silently bundled into project init.
- `oq-20260528-0012` remains open but narrowed around local prompt/resource
  content-security behavior.
- `oq-20260528-0013` remains open but narrowed around service-management
  candidate promotion.
- `oq-20260528-0018` remains open but narrowed around non-assistant REST APIs.
- `ai-20260530-0001` is honored by the formal RFC/procedure and wave outputs.
- `ai-20260530-0002` remains parked for future prompt/resource library review
  for inference-inclusive proof and regression testing.

## Evidence Index

Primary procedure and design sources:

- `docs/initiatives/contextforge-control-plane/design-rfc.md`
- `docs/initiatives/contextforge-control-plane/design-rfc-procedure.md`
- `AGENTS.md`

Accepted implementation checkpoints:

- `e107698`: accepted Waves 0-11 implementation, tests, fixtures, and schemas.
- `a2ac5d3`: Wave 12 deterministic and inference-inclusive MVS tests.
- `9e2698e`: Wave 12 runbook and acceptance checklist.

Wave 12 acceptance evidence:

- `docs/initiatives/contextforge-control-plane/implementation-runbook.md`
- `docs/initiatives/contextforge-control-plane/acceptance-checklist.md`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-evidence.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-run-report.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-root-qa.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-independent-qa.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-qa-report.json`

Inference-inclusive proof:

- Python harness: `scripts/control_plane_inference_harness.py`
- Cases: `tests/fixtures/control_plane_inference_cases.json`
- Tests: `tests/test_control_plane_inference_harness.py`
- Live raw artifacts: `run/20260530T202154Z-w12-z2-live-gpt-5.4-mini`
- Accepted model: `gpt-5.4-mini`
- Unsupported requested model string recorded: `gpt-5-4-mini`

## Acceptance Criteria Mapping

- D0-D18: D0-D17 are complete; D18 is pending W13-QA and root adjudication.
- `must_pass_mvs`: W12-QA verified all nine `must_pass_mvs` requirements have
  W12-A deterministic/probe coverage and W12.z.2 passing inference coverage.
- Wave QA: W0-W12 QA passed after root adjudication; W13-QA remains pending.
- Deterministic tests: full control-plane discovery passed after W12 closeout.
- Inference-inclusive testing: W12.z.2 live Python harness invoked headless
  `codex exec` tested-assistant and evaluator roles, evaluator-only
  `--output-schema`, and four passing structured evaluator verdicts.
- Consent and mutation boundaries: authorization, trust, token, remote
  exposure, service-management, and project-local apply helpers are covered by
  fixture-backed deterministic tests and fail-closed policy evidence.
- Project state authority: `.project/context_forge_state.json` is the accepted
  state authority by schema, helper implementation, tests, and
  `dec-20260530-0002`.
- Shared canonical services: classification/capsule tests distinguish shared
  canonical services from per-project services.
- Catalog promotion: service-management handoff is the only approved path;
  generic project init cannot promote candidates.
- User-global trust, token material, secret values, and remote exposure:
  separately approved and evidenced by policy; no silent mutation is accepted.
- Governance reconciliation: W13-A applied approved reconciliation operations
  through `scripts/governance_crud.py`.

## Accepted Non-Blockers

- Rejected W12-B fixture-playback artifacts remain in ignored run evidence but
  are superseded and not cited for acceptance.
- W12.z.2 pass verdicts still include a required `likely_cause` enum; a future
  schema may add `none` or `not_applicable`.
- W12-A integration/probe evidence is fixture-backed, not live
  ContextForge/systemd/client endpoint proof, and the runbook/checklist state
  that boundary.
- No standalone W12.z.0 artifact exists; containment is evidenced through
  scope exclusions and the W12.z evidence chain.
- The implementation-quality review found the current MVS is not yet a cohesive
  operator-grade CLI. That is a product-quality follow-up, not an RFC MVS
  blocker.

## Remaining Before Final Declaration

- W13-QA must pass.
- Root must adjudicate W13-QA findings.
- D18 must be marked complete only after W13-QA/root gate passes.
- The final response must summarize completed waves, verification commands,
  unresolved non-blockers, governance changes, and exact acceptance criteria.
