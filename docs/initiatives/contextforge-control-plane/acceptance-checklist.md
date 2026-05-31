# ContextForge Control-Plane Acceptance Checklist

Run ID: `20260530T202154Z`

This checklist maps the current Wave 12 evidence to the RFC/procedure
acceptance criteria. It does not claim final acceptance. D17 remains pending
until full W12-QA and root adjudication pass. D18 remains pending for Wave 13.

## Status Key

- `satisfied`: evidence exists for the current MVS scope.
- `pending W12-QA`: W12-C has indexed the evidence, but full Wave 12 QA/root
  gate has not yet accepted it.
- `pending W13`: governance closeout or final release-readiness work remains.
- `non-blocker`: accepted limitation that does not block current gate.
- `out of scope`: excluded from this MVS unless separately approved.

## D17 Wave 12 Checklist

| Criterion | Status | Evidence |
| --- | --- | --- |
| Deterministic MVS scenarios cover project-state, sticky declines, disabled/no-service state, planning, consent, apply, Codex trust, tool policy, Serena, project-inspector, shared-service capsule, service-management handoff, language profiles, service-memory boundary, governance reconciliation, malicious metadata, auth wrappers/profiles, and remote exposure gates. | pending W12-QA | `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-summary.md` |
| W12-A deterministic/probe evidence is no-mutation and redaction checked. | pending W12-QA | `w12-a-deterministic-evidence.json` records `no_mutation_attestation.status == "passed"` and `secret_scan.status == "passed"`. |
| Inference-inclusive tests preserve inferential isolation between tested assistant, evaluator, remediator, and orchestration. | pending W12-QA | `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-evidence.json`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-root-qa.json`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-independent-qa.json` |
| Semantic inference verdicts are model-generated structured evaluator output, not deterministic pattern matching. | pending W12-QA | `scripts/control_plane_inference_harness.py`; `tests/test_control_plane_inference_harness.py`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/evaluator-output.schema.json`; `w12-z2-live-evidence.json` |
| Live inference run used Python harness invoking headless `codex exec` roles. | pending W12-QA | Command recorded in `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-summary.md`; raw artifacts under `run/20260530T202154Z-w12-z2-live-gpt-5.4-mini`. |
| Evaluator verdicts are evidence-cited and all four live inference cases passed. | pending W12-QA | `w12-z2-live-evidence.json`; `w12-z2-live-run-report.json`; `w12-z3-root-qa.json`; `w12-z3-independent-qa.json` |
| ContextForge remains the stock registry/proxy/control-plane anchor. | pending W12-QA | Deterministic evidence covers authority and service-management plan-only behavior; no direct ContextForge database writes are claimed. |
| ContextForge owns canonical service/resource identity; client configs are discovery inputs. | pending W12-QA | W12-A authority/shared-service capsule scenarios. |
| `.project/context_forge_state.json` owns project initialization state. | pending W12-QA | W12-A project-state authority scenarios. No live `.project/context_forge_state.json` write is claimed in W12. |
| User-global client trust changes require separate explicit approval. | pending W12-QA | W12-A Codex trust and auth-profile scenarios. |
| Remote exposure is local-first, non-default, auth-aware, and separately gated. | pending W12-QA | W12-A auth-profile and remote-exposure scenarios. |
| Serena is declined in this run and not provisioned. | pending W12-QA | W12-A project planner and project adapter cases. |
| Shared/canonical services are distinguished from per-project services. | pending W12-QA | W12-A context7 shared capsule and ssh-tmux session-scope cases. |
| W12.z.3 independent QA passed. | satisfied for W12.z scope; pending full W12-QA | `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-independent-qa.json` |
| W12-C docs/runbook/evidence bundle exist. | pending W12-QA | `docs/initiatives/contextforge-control-plane/implementation-runbook.md`; `docs/initiatives/contextforge-control-plane/acceptance-checklist.md`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-c-evidence-bundle.json`; `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-c-summary.md` |

## Accepted Non-Blockers

- W12.z.3 independent QA noted that there is no standalone W12.z.0 artifact.
  It accepted sequence coverage through W12.z.1, W12.z.2, and root W12.z.3 QA
  artifacts.

## Remaining Gates

- Full W12-QA must review W12-A, W12.z, and W12-C together.
- Root must adjudicate W12-QA findings.
- D17 must remain pending until the W12 root gate passes.
- W13-A must apply only approved governance updates through the repository
  governance tooling.
- W13-B must produce the final release-readiness report.
- W13-QA and final root acceptance remain pending.

## Out-Of-Scope Exclusions

- `.project/` is a known local/untracked worktree item and is excluded from
  W12-C acceptance unless explicitly re-scoped.
- `server-instances/context7/README.md` is a known unrelated modified tracked
  file and is excluded from W12-C acceptance unless explicitly re-scoped.
- No live ContextForge/systemd/client endpoint success is claimed here unless
  separately cited by an existing evidence artifact.
- No remote exposure, user-global trust, token material, actual secret entry,
  or catalog promotion is accepted under generic project-init approval.

## Final Acceptance Still Pending

The procedure's final acceptance requires D0-D18 complete or explicitly
deferred, every wave QA passed after root adjudication, deterministic and
required integration/probe tests passing, inference-inclusive isolation with
structured evaluator verdicts, consent receipts for mutating effects,
verification traces for verified states, project state in
`.project/context_forge_state.json`, shared canonical service capability
capsules, separately approved global trust/token/secret/remote-exposure
changes, and governance reconciliation review.
