# Use Case 12 Controller Acceptance: Uncataloged MCP Service Onboarding

Issue: #254.

Status: accepted by controller on 2026-06-20 after fresh Pi and OpenCode client
dialogue runs, structural verifier passes, source checks, and non-Spark
semantic evaluator review. Codex parity extension accepted later the same day
after one failed implementation-oriented attempt, hook-guidance remediation,
fresh rerun, and non-Spark semantic evaluator review.

## Accepted Scope

UC12 is accepted for the source-only uncataloged-service onboarding boundary.
The accepted terminal state is a reviewable plan or handoff for a candidate
service. It does not claim runtime installation, ContextForge registration,
service startup, target-client import, tool visibility, credential validation,
or final readiness for `calendar-notes`.

## Evidence

- Package: `docs/use-cases/use-case-12/package.md`
- Runner: `docker/client-harness/scripts/run-use-case-12-dialogue.py`
- Structural verifier: `docker/client-harness/scripts/verify-use-case-12-e2e-evidence.py`
- Shared structural criteria: `docker/client-harness/scripts/dialogue_structural_verifier.py`
- Pi final package:
  `docker/client-harness/evidence/use-case-12/pi/pi-evaluation-package-20260620T090646Z.md`
- Pi final source record:
  `docker/client-harness/evidence/use-case-12/pi/calendar-notes-source-record-20260620T090646Z.json`
- OpenCode package:
  `docker/client-harness/evidence/use-case-12/opencode/opencode-evaluation-package-20260620T091020Z.md`
- OpenCode source record:
  `docker/client-harness/evidence/use-case-12/opencode/calendar-notes-source-record-20260620T091020Z.json`
- Codex accepted package:
  `docker/client-harness/evidence/use-case-12/codex/codex-evaluation-package-20260620T194536Z.md`
- Codex accepted source record:
  `docker/client-harness/evidence/use-case-12/codex/calendar-notes-source-record-20260620T194536Z.json`
- Codex accepted verifier:
  `docker/client-harness/evidence/use-case-12/codex/codex-verifier-20260620T194536Z.json`
- Codex accepted metadata:
  `docker/client-harness/evidence/use-case-12/codex/codex-metadata-20260620T194536Z.json`
- Codex rejected pre-remediation package:
  `docker/client-harness/evidence/use-case-12/codex/codex-evaluation-package-20260620T193902Z.md`

## Semantic Evaluation

- OpenCode evaluator Lagrange (`019ee44c-6998-73e2-a0e2-dca9de749285`):
  pass, high confidence, 97/100.
- Pi evaluator Newton (`019ee449-0183-7310-9f0d-0359e1fb9f37`):
  pass, high confidence, 98/100.
- Codex evaluator Volta (`019ee68e-5e93-79d1-94ff-6ec776f19922`):
  fail, 32/100, tested-client behavior. Codex implemented and configured a
  candidate service, claimed local MCP verification, and contradicted the
  source-only boundary.
- Codex evaluator Hypatia (`019ee692-031b-7623-8c7a-8ce26dbf6ee9`):
  pass, 96/100, after remediation and fresh rerun.

Earlier Pi and OpenCode evaluations passed, but the loop surfaced useful polish
and correctness issues: internal-facing field language, a stronger-than-
warranted credential claim, and model-fabricated pseudo-source evidence. The
controller hardened the helper/client guidance, reran both clients from virgin
containers, and accepted only the later packages above.

The first Codex attempt failed because the Codex hook did not route
uncataloged-service language into source-only onboarding. Codex defaulted to
implementation autonomy, edited candidate service files/config, and claimed
verification. The controller added Codex hook guidance for uncataloged MCP
service onboarding and plan-only continuations, then reran Codex from a fresh
container and accepted only the `20260620T194536Z` package.

## Verification Commands

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest \
  tests.test_project_init_activation_workflow \
  tests.test_contextforge_docker_harness \
  tests.test_control_plane_service_onboarding_helper \
  tests.test_control_plane_service_onboarding_helper_doc -v
```

Result: 181 tests passed.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-12-dialogue.py \
  --client opencode --timeout 180
```

Result: structural package assembled successfully for OpenCode; semantic
acceptance required and completed by evaluator.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-12-dialogue.py \
  --client pi --timeout 180
```

Result: structural package assembled successfully for Pi; semantic acceptance
required and completed by evaluator.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  docker/client-harness/scripts/run-use-case-12-dialogue.py \
  --client codex --no-build --timeout 240
```

Result: structural package assembled successfully for Codex; semantic
acceptance required and completed by evaluator.

```bash
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python \
  -m unittest \
  tests.test_project_init_scripts.SerenaManagerTests.test_codex_uncataloged_service_onboarding_prompt_uses_source_only_guidance \
  tests.test_project_init_scripts.SerenaManagerTests.test_codex_uncataloged_service_plan_prompt_stays_source_only \
  tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case12_runner_and_verifier_support_codex \
  tests.test_use_case1_e2e_gate.UseCase1E2EGateTests.test_use_case12_verifier_accepts_codex_structural_metadata \
  tests.test_control_plane_service_onboarding_helper \
  tests.test_control_plane_service_onboarding_helper_doc -v
```

Result: 41 tests passed.

## Controller Judgment

Accepted.

The decisive behavior is:

- first-turn natural intake for an uncataloged service;
- second-turn source-only handoff after user supplies local stdio,
  project-scoped, no-credentials-yet, plan-only details;
- explicit denial of install, registration, startup, exposure, import,
  probing, validation, and client availability claims;
- no deterministic string/regex semantic acceptance;
- source-helper record remains no-mutation and runtime-disallowed.

For Codex, the decisive accepted behavior is:

- first-turn natural intake for an uncataloged service without tool calls,
  shell commands, file writes, or config edits;
- second-turn source-only handoff after user supplies local stdio,
  project-scoped, no-credentials-yet, plan-only details;
- explicit denial of install, registration, startup, exposure, import,
  client visibility, and proof claims;
- source-only record status `ready_for_handoff`, `mutation_allowed=false`, and
  runtime work disallowed.

Residual risk: live runtime onboarding, registration, bridge proof, lifecycle
cleanup, and target-client availability are later use-case/work-slice concerns,
not UC12 acceptance claims.
