# Use Case 15 Controller Acceptance: Clear Project Handoff

Issue: #257.

Status: accepted by controller on 2026-06-20 after handoff package
materialization, structural verifier pass, source checks, remediation from an
initial semantic failure, corrected issue readback, and non-Spark semantic
review.

## Accepted Scope

UC15 is accepted as a project-handoff use case. The accepted terminal state is
a generated handoff that tells the next operator what works, how to operate Pi,
OpenCode, and Codex in the tested harnesses, what remains unproven, and which
follow-up issue owns each major gap.

This is not a release-readiness claim, not issue closure, not PR merge approval,
not all-service safe-call proof, not credential validity, not live/legacy
ContextForge mutation, and not host-Codex promotion.

## Evidence

- Package: `docs/use-cases/use-case-15/package.md`
- Runner:
  `docker/client-harness/scripts/run-use-case-15-handoff.py`
- Structural verifier:
  `docker/client-harness/scripts/verify-use-case-15-handoff-evidence.py`
- Runtime metadata:
  `docker/client-harness/evidence/use-case-15/use-case-15-metadata-20260620T202021Z.json`
- Runtime verifier:
  `docker/client-harness/evidence/use-case-15/use-case-15-verifier-20260620T202021Z.json`
- Generated handoff:
  `docker/client-harness/evidence/use-case-15/use-case-15-handoff-20260620T202021Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-15/use-case-15-evaluation-package-20260620T202021Z.md`
- UC14 readiness input:
  `docker/client-harness/evidence/use-case-14/use-case-14-readiness-report-20260620T201054Z.md`

## Defect And Remediation

Initial semantic evaluator Newton `019ee6ae-4490-7992-a7e5-39e5f114ae99`
returned FAIL 72/100. The primary failure was `handoff_clarity`: the first
handoff was structurally correct but too terse for a human operator to use
without reconstructing state from issue and PR history.

Remediation:

- expanded each client note into `what_works`, `how_to_use`, `evidence`,
  `gap`, and `next_action`;
- added a validated-flow summary across activation, readback, selected tool
  use, cross-client state, service onboarding, and readiness;
- added current issue-status readback for #257, #280, #285, #286, #287, and
  #289;
- corrected the #280 owner text after readback showed #280 is a historical
  `.venv` friction issue with label `invalid`, not service-set parity work;
- strengthened the verifier to require detailed client notes, validated flows,
  issue-owner fields, issue-status readback, and explicit non-claims.

Corrected evaluator Banach `019ee6b1-3d8b-7db3-884c-ae287061c1ed` scored the
corrected package PASS 94/100 with no primary failure class and recommended
controller acceptance.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-15-handoff.py
```

Result: package assembled successfully with `ok=true`.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/verify-use-case-15-handoff-evidence.py \
  --metadata \
  docker/client-harness/evidence/use-case-15/use-case-15-metadata-20260620T202021Z.json
```

Result: `ok=true`.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_use_case1_e2e_gate -v
```

Result: 30 tests passed.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-15-handoff.py \
  docker/client-harness/scripts/verify-use-case-15-handoff-evidence.py \
  tests/test_use_case1_e2e_gate.py
```

Result: pass.

```bash
git diff --check
```

Result: pass.

## Controller Judgment

Accepted.

Residual risk: UC15 is a handoff artifact over the current scoped evidence. It
must not be reused as release approval or as proof that every listed service has
runtime safe-call evidence in every client. Follow-up issues #285, #286, #287,
and #289 remain live and should shape the next coordination queue.
