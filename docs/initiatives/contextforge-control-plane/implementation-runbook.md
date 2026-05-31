# ContextForge Control-Plane MVS Implementation Runbook

Run ID: `20260530T202154Z`

This runbook covers the current minimal viable slice for the ContextForge
control-plane RFC implementation. It is intentionally narrow: the current
implementation is a set of pure helpers, planners, fixture-backed scenario
executors, evidence builders, and local-first safety gates. It is not yet a
single mature operator CLI that applies a full workflow end to end.

## Current Scope

Implemented surfaces:

- Project-state helpers for `.project/context_forge_state.json` semantics.
- Service classification and planning helpers that keep ContextForge as the
  canonical service/resource authority.
- Consent, trust, authorization, redaction, remote-exposure, and tool-policy
  gates.
- Fixture-backed deterministic MVS scenario execution.
- A Python inference harness that invokes headless `codex exec` roles for a
  tested assistant and a separate evaluator.
- Evidence ledgers and QA artifacts for Wave 12 acceptance review.

Not implemented as completed operator behavior:

- A cohesive production operator/apply CLI.
- Silent user-global trust changes.
- Actual secret-value entry or token material handling.
- Default remote exposure.
- Catalog promotion under generic project-init approval.
- Live ContextForge/systemd/client endpoint proof for the full control-plane
  workflow unless a cited artifact explicitly says so.
- Serena provisioning in this run. Serena remains declined.

## Consent And Non-Actions

The current MVS preserves these boundaries:

- ContextForge remains the stock registry, proxy, and control-plane anchor.
- ContextForge owns canonical service/resource identity; client configs are
  discovery inputs, not service identity authorities.
- Project initialization state belongs in `.project/context_forge_state.json`.
- User-global client trust changes require separate explicit approval and are
  never silent.
- Approved workflows may write project-local config/state only within their
  consent class.
- Remote exposure is non-default and separately gated.
- Actual secret values, bearer tokens, generated JWTs, and passwords are not
  written into evidence.
- Shared canonical services such as context7 are represented through capability
  capsules and are not duplicated per project.
- Per-project services such as Serena are distinct from shared/canonical
  services; Serena is the first proof path in the RFC, not a privileged special
  case.

## Deterministic Regression

Run the deterministic control-plane regression set from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_control_plane_*.py'
```

For the accepted W12-A deterministic MVS slice, the evidence command was:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_mvs_scenarios.py --write-evidence run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json && jq -e '.coverage.mvs_deterministic_probe_complete == true and .no_mutation_attestation.status == "passed" and .secret_scan.status == "passed"' run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json
```

Accepted W12-A evidence:

- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-deterministic-evidence.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-a-summary.md`

W12-A evidence is deterministic and fixture-backed. It does not claim live
assistant execution, live ContextForge registry mutation, live systemd
activation, or live target-client endpoint proof.

## Inference-Inclusive Regression

Run focused inference-harness tests:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_control_plane_inference_harness -v
```

Compile the harness and tests:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile scripts/control_plane_inference_harness.py tests/test_control_plane_inference_harness.py
```

The accepted live W12.z.2 inference run used the Python harness to invoke
headless agents through `codex exec`. The tested assistant and evaluator were
separate roles. The evaluator used structured output; the tested assistant did
not receive the evaluator schema.

Accepted live command:

```sh
PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/control_plane_inference_harness.py --requirements tests/fixtures/control_plane_requirements.json --cases tests/fixtures/control_plane_inference_cases.json --output run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-evidence.json --run-id 20260530T202154Z-w12-z2-live-gpt-5.4-mini --model-designation gpt-5.4-mini_live_headless --codex-model gpt-5.4-mini > run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-command-stdout.txt 2> run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-command-stderr.txt
```

Accepted inference evidence:

- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z1-contract-evidence.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-evidence.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z2-live-run-report.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-root-qa.json`
- `run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-z3-independent-qa.json`
- `run/20260530T202154Z-w12-z2-live-gpt-5.4-mini`

Model note:

- User-requested model string `gpt-5-4-mini` was rejected by `codex exec` as
  unsupported for the account/environment.
- The accepted live inference run used `gpt-5.4-mini`.

## Evidence Review

Use these read-only checks when reviewing W12-C:

```sh
jq empty run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-c-evidence-bundle.json
```

```sh
while IFS= read -r path; do test -e "$path" || { echo "missing $path"; exit 1; }; done < <(jq -r '.. | objects | .path? // empty' run/contextforge-control-plane-implementation/20260530T202154Z/wave12/w12-c-evidence-bundle.json)
```

## Remaining Gates

W12-C is documentation and evidence indexing only. It does not mark D17 or Wave
12 complete. Remaining gates are:

- Full W12-QA over W12-A, W12.z, and W12-C.
- Root adjudication of W12-QA.
- Accepted blocker remediation, if any.
- Root update of D17 only after W12-QA/root gate passes.
- Wave 13 governance closeout and release readiness for D18.
