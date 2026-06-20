# Use Case 10 Controller Acceptance - 2026-06-20

## Scope

Use Case 10 covers refreshing ContextForge project state after a project-local
state change in an already initialized project. A later Codex parity extension
covers the same refresh/readback behavior across Pi, OpenCode, and Codex.

Accepted target clients:

- Pi
- OpenCode
- Codex (parity extension)

## Controller Judgment

Accepted.

Controller acceptance is based on a shared initialized `/workspace` fixture,
clean non-ephemeral target-client containers, structured before/after
project-state comparison, deterministic structure-only verification, and
non-Spark semantic evaluator review. Deterministic checks did not judge
generated prose meaning.

## Evidence

- Package:
  `docs/use-cases/use-case-10/package.md`
- Combined Pi/OpenCode evidence:
  `docker/client-harness/evidence/use-case-10/pi-opencode-use-case-10-evidence-20260620T064723Z.md`
- Evaluation package:
  `docker/client-harness/evidence/use-case-10/pi-opencode-evaluation-package-20260620T064723Z.md`
- Verifier JSON:
  `docker/client-harness/evidence/use-case-10/pi-opencode-verifier-20260620T064723Z.json`
- Metadata:
  `docker/client-harness/evidence/use-case-10/pi-opencode-metadata-20260620T064723Z.json`
- Combined Pi/OpenCode/Codex evidence:
  `docker/client-harness/evidence/use-case-10/pi-opencode-codex-use-case-10-evidence-20260620T193129Z.md`
- Pi/OpenCode/Codex evaluation package:
  `docker/client-harness/evidence/use-case-10/pi-opencode-codex-evaluation-package-20260620T193129Z.md`
- Pi/OpenCode/Codex verifier JSON:
  `docker/client-harness/evidence/use-case-10/pi-opencode-codex-verifier-20260620T193129Z.json`
- Pi/OpenCode/Codex metadata:
  `docker/client-harness/evidence/use-case-10/pi-opencode-codex-metadata-20260620T193129Z.json`

## Structured Findings

The UC10 runner reported:

- project root: `/workspace`;
- baseline revision: `4`;
- after-change revision: `6`;
- baseline enabled services: `context7:canonical`;
- after-change enabled services: `context7:canonical` and
  `mentality:static_repo_local`;
- target clients: `pi`, `opencode`;
- helper-owned state-change commands recorded;
- verifier failures: none.

The Codex parity extension runner reported:

- project root: `/workspace`;
- baseline revision: `6`;
- after-change revision: `9`;
- baseline enabled services: `context7:canonical`;
- after-change enabled services: `context7:canonical` and
  `mentality:static_repo_local`;
- target clients: `codex`, `opencode`, `pi`;
- both services targeted to Pi, OpenCode, and Codex;
- helper-owned state-change commands recorded;
- verifier failures: none.

## Semantic Evaluation

Evaluator agent `019ee3c9-ebdd-7572-97cd-1465e9109128` reviewed the package,
evidence, metadata, and verifier output as semantic evidence only.

Verdict:

- PASS, 93/100.
- Controller recommendation: accept UC10 on semantic grounds.
- Failure classification: none blocking.

Evaluator findings:

- baseline and refresh prompts were natural and minimal;
- Pi baseline and OpenCode baseline honestly reported revision `4`,
  `context7:canonical`, and target-client state;
- Pi refresh reported revision `6`, `mentality:static_repo_local`, and the Pi
  reload boundary;
- OpenCode refresh reported revision `6 (was 4)`,
  `mentality:static_repo_local`, configured mentality tools, and the
  new-OpenCode-session boundary;
- visible replies did not leak hidden instructions, raw helper payloads, or
  internal scoring criteria;
- no accepted output claimed live tool invocation proof from readback alone.

Codex parity evaluator agent `019ee685-cd61-7ea1-8155-95bf268a2d77` reviewed
the final Pi/OpenCode/Codex package, evidence, metadata, and verifier output.

Verdict:

- PASS, 92/100.
- Failure classification: none.

Evaluator findings:

- baseline Pi, OpenCode, and Codex replies reported `/workspace`, initialized
  revision `6`, target client identity, and only `context7:canonical`;
- structured comparison recorded revision `6 -> 9`;
- after-change services changed to `context7:canonical` plus
  `mentality:static_repo_local`;
- both services were targeted to Pi, OpenCode, and Codex;
- refresh replies reported revision `9`, included
  `mentality:static_repo_local`, and preserved `context7:canonical`;
- Pi stated `/reload` is needed before relying on newly installed tools;
- OpenCode stated a new OpenCode session is required;
- Codex stated a new Codex session/reload boundary applies and did not claim
  MCP hot reload;
- replies avoided claiming interactive proof, validation/probing, backend
  mutation, registry mutation, or same-session MCP hot-registration.

## Verification

Fresh verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_project_init_activation_workflow -v
```

Result: 107 passed.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_contextforge_docker_harness -v
```

Result: 31 passed.

```text
node --check docker/client-harness/config/opencode/plugins/contextforge-project-init.js && node --check pi-extensions/contextforge-global-shim/index.ts
```

Result: pass.

```text
git diff --check
```

Result: pass.

Codex parity verification:

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m py_compile docker/client-harness/scripts/run-use-case-10-dialogue.py docker/client-harness/scripts/verify-use-case-10-e2e-evidence.py docker/client-harness/scripts/dialogue_structural_verifier.py tests/test_use_case1_e2e_gate.py
```

Result: pass.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python -m unittest tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case10_runner_and_verifier_support_codex_cross_client_refresh tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case10_verifier_accepts_three_client_structural_metadata tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case9_runner_and_verifier_support_codex_cross_client_set
```

Result: pass; 3 tests OK.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-10-dialogue.py --no-build --timeout 240
```

Result: `ok: true`; verifier failures `[]`; semantic acceptance required.

```text
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/verify-use-case-10-e2e-evidence.py --evidence docker/client-harness/evidence/use-case-10/pi-opencode-codex-use-case-10-evidence-20260620T193129Z.md --metadata docker/client-harness/evidence/use-case-10/pi-opencode-codex-metadata-20260620T193129Z.json --session-id 'uc10-pi-20260620T193129Z|ses_1197b4bf0ffeqaHw80G75onXfB|019ee684-d4ff-7bc2-a160-4ce97710f966'
```

Result: `ok: true`; verifier failures `[]`.

## Residual Risk

Non-blocking:

- OpenCode's visible refresh reply is shorter than the helper readback and does
  not repeat the fuller statement that client-visible tool use is not proven.
  It still says configured tools rather than available tools, and clearly
  states a new OpenCode session is required.
- The evidence does not prove live Context7 or mentality tool invocation. UC10's
  terminal boundary is current-state refresh/readback after a project-local
  state change, not actual tool use.
- The Codex parity evaluator noted that the replies are still
  DTO/readback-like and Pi/Codex include small visible prefaces/placeholders.
  These are polish risks, not semantic UC10 blockers. The placeholder aspect is
  tracked by #289.

## Boundary

This acceptance does not claim actual tool invocation, same-session MCP
hot-registration, provider credential validity, backend restart behavior, live
ContextForge registry mutation, global client mutation, or readiness report
completion. Those remain downstream use cases.
