# Use Case 15 Package: Clear Project Handoff

Issue: #257.

## Status

Queue state: selected after accepted UC14 readiness report. UC15 turns the
current evidence state into a concise handoff: what works, how to operate it,
what remains unproven, and which issue owns each gap.

Controller state: package materialized. Acceptance requires handoff generation,
structural verifier pass, source checks, and non-Spark evaluator review of
handoff usefulness and claim honesty.

## Full Story

1. Use the current checkout as the authority.
2. Use only the current-worktree test venv:
   `run/test-venvs/project-init-workflow/bin/python`.
3. Consume the accepted UC14 readiness metadata and report.
4. Generate a user-facing handoff document with Pi, OpenCode, and Codex
   operating notes.
5. Include evidence paths, known limitations, follow-up issue ownership, and
   next recommended actions.
6. Keep abandoned, superseded, or unproven paths out of active instructions.
7. Run a deterministic verifier over metadata, required paths, clients, issue
   ownership fields, and declared non-claims.
8. Send the handoff package to a non-Spark evaluator for semantic review.

## Terminal Boundary

The terminal boundary is a generated handoff package with:

- concise operating instructions for Pi, OpenCode, and Codex;
- links to the readiness report and accepted use-case evidence;
- explicit residual risks and issue ownership;
- clear next actions;
- GitHub Project/issue coordination updates performed by the controller.

The terminal boundary is not issue closure, release promotion, final merge
approval, all-service safe-call proof, credential validation, live/legacy
ContextForge mutation, or a substitute for the underlying evidence.

## Minimal Commands

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-15-handoff.py
```

## Deterministic Boundary

UC15 deterministic scripts may verify artifact presence, JSON parseability,
required client names, issue-owner fields, and declared non-claims. They must
not judge whether the handoff prose is useful or truthful; that belongs to the
non-Spark evaluator and controller.

## Step Criteria

### handoff_clarity (25 pts)

Expected: the handoff quickly tells the user what works and what to do next.

Fail if: the user must reconstruct status from PR or issue history.

### client_operating_notes (20 pts)

Expected: Pi, OpenCode, and Codex have separate operating notes matching tested
behavior and boundaries.

Fail if: Pi/OpenCode evidence is generalized to Codex or vice versa.

### residual_risk_ownership (25 pts)

Expected: each major gap has an owner issue or explicit carry-forward action.

Fail if: gaps are hidden or ownership is vague.

### claim_honesty (20 pts)

Expected: the handoff preserves UC14 non-claims and does not promote readiness
beyond the weakest proven layer.

Fail if: it claims release readiness, all-client safe-call proof, credential
validity, Serena runtime health, UC10 hot registration, or UC12 runtime
readiness.

### evaluator_review (10 pts)

Expected: a non-Spark evaluator reviews the handoff document.

Fail if: deterministic checks are used as semantic acceptance.

## Source Checks

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m py_compile \
  docker/client-harness/scripts/run-use-case-15-handoff.py \
  docker/client-harness/scripts/verify-use-case-15-handoff-evidence.py

PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest tests.test_use_case1_e2e_gate -v
```
