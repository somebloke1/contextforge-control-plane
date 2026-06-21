# Visible Placeholder Regression Guard Acceptance - 2026-06-20

Issue: #289.

Controller: `codex-thread:019ede5e-c2c8-72b0-8665-2effa6288d05`

## Accepted Scope

This accepts a methodology-only regression guard for visible placeholder
quality risks in code-assistant dialogue evaluations.

The accepted behavior is:

- evaluator packages and narratives should notice placeholder-only visible
  prefaces or similar low-quality visible dialogue risks;
- those risks may lower evaluator score or be promoted as follow-up work even
  when the use case still passes;
- deterministic scripts may preserve, segment, count, or route assistant text
  for review, but they must not decide placeholder meaning by string, regex, or
  token-pattern matching.

## Evidence

- Method update: `docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`
- Triage context:
  `docs/use-cases/flagged-attention-triage-20260620.md`
- Source check:
  `tests/test_use_case1_e2e_gate.py`

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_dialogue_method_records_visible_placeholder_quality_guard -v
```

Result: passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate -v
```

Result: 31 tests passed.

```text
git diff --check
```

Result: passed.

## Boundary

This does not add a deterministic placeholder detector, regex gate, string
matcher, or automatic prose pass/fail rule. It improves the semantic evaluator
instructions and keeps controller acceptance responsible for final judgment.
