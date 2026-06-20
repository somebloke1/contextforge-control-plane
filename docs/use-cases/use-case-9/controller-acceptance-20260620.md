# Use Case 9 Controller Acceptance - 2026-06-20

## Scope

Use Case 9 covers opening the same initialized project from Pi and OpenCode and
seeing consistent ContextForge project state and capabilities. A later Codex
parity extension covers the same pre-aligned shared-project readback across
Pi, OpenCode, and Codex.

Accepted target clients:

- Pi
- OpenCode
- Codex (parity extension)

## Controller Judgment

Accepted.

Controller acceptance is based on shared initialized `/workspace` fixtures,
clean non-ephemeral target-client containers, structured cross-client state
comparison, deterministic structure-only verification, and non-Spark semantic
evaluator review. Deterministic checks did not judge generated prose meaning.

## Evidence

- Package:
  `docs/use-cases/use-case-9/package.md`
- Combined Pi/OpenCode evidence:
  `docker/client-harness/evidence/use-case-9/pi-opencode-use-case-9-evidence-20260620T061108Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-9/pi-opencode-evaluation-package-20260620T061108Z.md`
- Verifier JSON:
  `docker/client-harness/evidence/use-case-9/pi-opencode-verifier-20260620T061108Z.json`
- Metadata:
  `docker/client-harness/evidence/use-case-9/pi-opencode-metadata-20260620T061108Z.json`
- Combined Pi/OpenCode/Codex evidence:
  `docker/client-harness/evidence/use-case-9/pi-opencode-codex-use-case-9-evidence-20260620T192303Z.md`
- Pi/OpenCode/Codex evaluation package:
  `docker/client-harness/evidence/use-case-9/pi-opencode-codex-evaluation-package-20260620T192303Z.md`
- Pi/OpenCode/Codex verifier JSON:
  `docker/client-harness/evidence/use-case-9/pi-opencode-codex-verifier-20260620T192303Z.json`
- Pi/OpenCode/Codex metadata:
  `docker/client-harness/evidence/use-case-9/pi-opencode-codex-metadata-20260620T192303Z.json`

## Structured Findings

The UC9 runner reported:

- project root: `/workspace`;
- state status: `initialized`;
- state revision: `2`;
- enabled services: `context7:canonical`;
- target clients: `pi`, `opencode`;
- Context7 enabled for both target clients;
- OpenCode project-local config surface present;
- skipped/unavailable decisions: none;
- verifier failures: none.

The Codex parity extension runner reported:

- project root: `/workspace`;
- state status: `initialized`;
- state revision: `3`;
- enabled services: `context7:canonical`;
- target clients: `codex`, `opencode`, `pi`;
- Context7 enabled for all target clients;
- OpenCode project-local config surface present;
- Codex project-local `.codex/config.toml` surface present;
- skipped/unavailable decisions: none;
- verifier failures: none.

## Semantic Evaluation

Evaluator agent `019ee3a8-a850-7352-ba4e-a90f0eb80e2c` reviewed the package,
evidence, metadata, and verifier output as semantic evidence only.

Verdict:

- PASS, 95/100.
- Failure classification: none.

Evaluator findings:

- both clients used minimal natural prompts;
- both clients answered the current-state question directly;
- both clients identified `/workspace`, initialized status, revision `2`, and
  their own client surface;
- both clients reported `context7:canonical` and aligned Context7
  library/docs capability;
- both clients reported no skipped/unavailable services and no bounded errors;
- both clients avoided claiming interactive tool-use proof from readback alone;
- hidden routing guidance remained hidden.

Codex parity evaluator agent `019ee67c-0390-7de2-ab0c-f92cc5cf0fc2` reviewed
the final Pi/OpenCode/Codex package, evidence, metadata, and verifier output.

Verdict:

- PASS, 94/100.
- Failure classification: none.

Evaluator findings:

- all three clients used minimal natural prompts;
- all three clients answered the current-state question directly enough for
  UC9;
- all three clients identified `/workspace`, initialized status, revision `3`,
  and their own client surface;
- all three clients reported `context7:canonical` and aligned Context7
  library/docs capability;
- all three clients reported no skipped/unavailable services and no bounded
  errors;
- all three clients avoided claiming interactive tool-use proof from readback
  alone;
- no onboarding restart, service selection, validation/probing, registry
  mutation, backend restart, global client mutation, or secret write was shown.

## Verification

Fresh verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile docker/client-harness/scripts/run-use-case-9-dialogue.py docker/client-harness/scripts/verify-use-case-9-e2e-evidence.py docker/client-harness/scripts/dialogue_structural_verifier.py
```

Result: pass.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-9-dialogue.py
```

Result: `ok: true`; verifier failures `[]`; semantic acceptance required.

Codex parity verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile docker/client-harness/scripts/run-use-case-9-dialogue.py docker/client-harness/scripts/verify-use-case-9-e2e-evidence.py docker/client-harness/scripts/dialogue_structural_verifier.py tests/test_use_case1_e2e_gate.py
```

Result: pass.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case9_runner_and_verifier_support_codex_cross_client_set tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case9_verifier_accepts_three_client_structural_metadata tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case11_runner_and_verifier_support_codex
```

Result: pass; 3 tests OK.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-9-dialogue.py --no-build --timeout 240
```

Result: `ok: true`; verifier failures `[]`; semantic acceptance required.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/verify-use-case-9-e2e-evidence.py --evidence docker/client-harness/evidence/use-case-9/pi-opencode-codex-use-case-9-evidence-20260620T192303Z.md --metadata docker/client-harness/evidence/use-case-9/pi-opencode-codex-metadata-20260620T192303Z.json --session-id 'uc9-pi-20260620T192303Z|ses_119830a57ffeIAsAtBZrDFU3XJ|019ee67d-1868-7531-abeb-d82ce6300de5'
```

Result: `ok: true`; verifier failures `[]`.

```text
git diff --check
```

Result: pass.

## Residual Risk

Non-blocking:

- Replies remain somewhat mechanical and include terms such as
  `target-client binding state` and `configured/imported-tool policy`.
- OpenCode is less explicit than Pi about reload-pending/client-visible
  uncertainty, but still preserves the important boundary by not claiming
  interactive proof.
- The Codex parity evaluator noted Pi's visible standalone `...` before the
  substantive readback as a minor polish defect. It should be promoted as a
  regression guard for visible-placeholder behavior, but it is not a UC9
  acceptance blocker.

These are wording-quality risks, not acceptance blockers for UC9. They can be
improved in later UX polishing without invalidating the same-project
consistency result.

## Boundary

This acceptance does not claim actual tool invocation, same-session follow-up,
automatic new-client alignment/import, refresh behavior after a later
project-state change, provider credential validity, registry mutation
readiness, global client mutation, or readiness report completion. Those remain
downstream use cases.
