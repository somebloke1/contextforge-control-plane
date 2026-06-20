# Use Case 14 Controller Acceptance: Trustworthy Readiness Report

Issue: #256.

Status: accepted by controller on 2026-06-20 after package materialization,
readiness report generation, structural verifier pass, focused source checks,
defect remediation, and corrected non-Spark semantic review.

## Accepted Scope

UC14 is accepted as a readiness-report use case. The accepted terminal state is
a generated report that separates source/tests, backend/container,
ContextForge route, target-client visibility, ordinary interactive proof,
safe-call proof, and handoff readiness for Pi, OpenCode, and Codex.

This is not a release-readiness claim, not a final handoff, not a claim that
every service has safe-call proof in every client, and not a claim that UC13
proves semantic dialogue behavior.

## Evidence

- Package: `docs/use-cases/use-case-14/package.md`
- Runner:
  `docker/client-harness/scripts/run-use-case-14-readiness-report.py`
- Structural verifier:
  `docker/client-harness/scripts/verify-use-case-14-readiness-evidence.py`
- Runtime metadata:
  `docker/client-harness/evidence/use-case-14/use-case-14-metadata-20260620T201054Z.json`
- Runtime verifier:
  `docker/client-harness/evidence/use-case-14/use-case-14-verifier-20260620T201054Z.json`
- Generated readiness report:
  `docker/client-harness/evidence/use-case-14/use-case-14-readiness-report-20260620T201054Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-14/use-case-14-evaluation-package-20260620T201054Z.md`

## Defect And Remediation

Initial semantic evaluator Halley `019ee6a5-e1f8-7722-9ce6-1af6777e6c7e`
scored the first package PASS 86/100 but found an evidence-inventory precision
defect: the UC1 report glob could resolve to a UC13 artifact.

Remediation:

- replaced broad `uc{n}*acceptance-*.md` matching with exact controller and
  Codex-parity acceptance report patterns;
- added `acceptance_groups` for UC1 through UC13;
- required all acceptance groups to be complete in the verifier;
- expanded generated non-claims for UC10 hot registration, UC12
  `calendar-notes` runtime readiness, credential validity, and Serena runtime
  indexing/LSP health.

Corrected evaluator Kuhn `019ee6a8-b04a-7da2-a883-2938fd2c97be` scored the
corrected package PASS 96/100 with no primary failure class and recommended
controller acceptance.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-14-readiness-report.py
```

Result: package assembled successfully with `missing_required_artifacts: 0`.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/verify-use-case-14-readiness-evidence.py \
  --metadata \
  docker/client-harness/evidence/use-case-14/use-case-14-metadata-20260620T201054Z.json
```

Result: `ok=true`, all UC1 through UC13 acceptance groups complete.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_use_case1_e2e_gate -v
```

Result: 29 tests passed.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-14-readiness-report.py \
  docker/client-harness/scripts/verify-use-case-14-readiness-evidence.py \
  tests/test_use_case1_e2e_gate.py
```

Result: pass.

```bash
git diff --check
```

Result: pass.

## Controller Judgment

Accepted.

Residual risk: the phrase "ordinary interactive proof" remains nuance-sensitive
and is accepted only because the report scopes it to selected use cases and
pairs it with explicit safe-call, release, UC10, UC12, credential, Serena, and
handoff non-claims.
