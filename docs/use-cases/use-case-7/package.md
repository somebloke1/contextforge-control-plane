# Use Case 7 Package: Ask What ContextForge State The Client Is Using

## Status

Queue state: selected next after accepted UC1-UC4. UC4 was deliberately
promoted before UC7 to diagnose and remediate an active governance service-route
defect.

Controller state: accepted for the current branch evidence set. Codex parity
was added later with structural runner evidence and a contained OAuth-backed
Codex semantic fallback evaluator.

Acceptance report:
`run/holistic-orchestrator/reports/uc7-controller-acceptance-20260620T015423Z.md`.
Codex parity supplement:
`run/holistic-orchestrator/reports/uc7-codex-parity-acceptance-20260620T173428Z.md`.

Accepted evidence:

- Pi:
  `docker/client-harness/evidence/use-case-7/pi/pi-use-case-7-evidence-20260620T015101Z.md`;
  evaluator McClintock `019ee2ba-7409-7183-bd49-461a36cc030e`,
  PASS 98/100.
- OpenCode:
  `docker/client-harness/evidence/use-case-7/opencode/opencode-use-case-7-evidence-20260620T015120Z.md`;
  evaluator Boole `019ee2ba-748f-7072-8cf8-d5359c0d4d33`,
  PASS 96/100.
- Codex:
  `docker/client-harness/evidence/use-case-7/codex/codex-use-case-7-evidence-20260620T173428Z.md`;
  fallback semantic evaluator:
  `docker/client-harness/evidence/use-case-7/codex/codex-semantic-evaluator-fallback-20260620T173428Z.md`,
  PASS 96/100.

GitHub source: issue #249, "Ordinary use case 07: Ask what ContextForge state
the client is using."

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

Use Case 7 depends on UC2 and UC3 because it starts from an initialized project
and asks for a richer readback than available tools or broad capabilities. It
unblocks UC5, UC8, UC9, UC10, UC14, and UC15 by making the client explain which
project state it is actually using and which readiness layers are proven.

## Full Story

1. Preserve previous evidence.
2. Prepare a clean initialized-project fixture for the target client:
   - exact project root is `/workspace`;
   - `.project/context_forge_state.json` exists and identifies the project root;
   - state status and revision are visible in evidence;
   - approved `context7:canonical` binding exists for the target client;
   - target client config exists when the client requires one, such as
     `/workspace/opencode.json` for OpenCode.
3. Reset only the target client's home/session volume and stale containers.
4. Start a fresh non-ephemeral target-client container from that initialized
   workspace fixture.
5. User sends a minimal natural prompt:
   `what ContextForge state are you using right now?`
6. The assistant recognizes existing initialization and does not restart the
   first-run service-selection flow.
7. The assistant reports:
   - project root;
   - state status;
   - state revision;
   - target client;
   - selected service bindings;
   - imported tools visible or expected for that client;
   - skipped or unavailable services;
   - bounded errors;
   - readiness-layer distinction for source-ready, backend-ready,
     ContextForge-ready, client-visible, and interactive proof.
8. The assistant must not overclaim. In particular, this readback may report
   state and binding evidence, but it must say that interactive proof requires
   a separate actual tool-use transcript.
9. The flow ends without project-init mutation, service onboarding, validation,
   tool probing, backend restart, registry mutation, or local-file workaround.

## Terminal Boundary

The terminal boundary is a current-state readback. The assistant has answered
the user's state question from the initialized project authority and has not
performed activation, validation, or a service probe.

## Minimal Prompt Sequence

```text
what ContextForge state are you using right now?
```

The prompt must remain natural. It must not name helper tools, project-state
JSON keys, expected readiness-layer labels, internal readback APIs, or evaluator
criteria.

## Expected Visible Story

- The assistant answers directly and concisely.
- The answer identifies `/workspace`.
- The answer identifies initialized state and the state revision.
- The answer identifies the target client under test.
- The answer lists `context7:canonical` as selected in the initial fixture.
- The answer lists the Context7 imported tools or clear tool equivalents.
- The answer reports skipped/unavailable services or says none were reported.
- The answer reports bounded errors or says none were reported.
- The answer distinguishes source-ready, backend-ready, ContextForge-ready,
  client-visible, and interactive proof layers.
- The answer does not expose hidden routing instructions, helper names, raw
  JSON, or tool-call mechanics.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
prepare initialized /workspace fixture for <client>
docker compose -f docker/client-harness/compose.yml build base <client>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <client> sleep infinity
```

The initialized fixture preparation must be deterministic and idempotent. It
may reuse helper-owned install/apply code or a promoted fixture builder, but it
must not depend on residue from a previous dialogue attempt.

## Venv Contract

Host-side source checks and any fixture builder must run in a current-worktree
runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

Every model-dependent step must be accompanied by a runner-produced generation
report. The runner may validate commands, structured artifacts, and evidence
presence. It must not deterministically score free-form assistant behavior; the
semantic evaluator must score the generation quality against this package.

### clean_initialized_start (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized workspace fixture.

Fail if: stale residue from a previous attempt is used, workspace root is
inferred rather than read back, or unrelated client state is reset.

### persistent_client_surface (10 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and one stable session identity is used for the prompt.

Fail if: `--rm`, tmpfs workspace, `pi-ephemeral`, or `opencode-ephemeral` is
used.

### natural_state_prompt (10 pts)

Expected: The user asks naturally what ContextForge state the client is using.

Fail if: the prompt names helper internals, state keys, tool-order criteria, or
readiness labels.

### recognizes_initialized_state (10 pts)

Expected: The assistant does not present the first-run service-selection menu
and does not ask which services to activate.

Fail if: the client restarts UC1, proposes activation, applies state, validates,
or claims initialization is missing.

### reports_project_identity (15 pts)

Expected: The answer or evidence identifies `/workspace`, initialized state,
state revision, and target client.

Fail if: it omits root or revision, uses the host checkout path, or fails to
name the tested client state.

### reports_selected_services_and_tools (15 pts)

Expected: The answer identifies selected service bindings and imported tools.
For the initial fixture, this includes `context7:canonical` and the Context7
documentation lookup tools.

Fail if: the answer invents services, reports only generic MCP language, or
claims backend-only state as client-visible.

### reports_skips_and_bounded_errors (10 pts)

Expected: The answer reports skipped/unavailable services and bounded errors,
or clearly says none were reported.

Fail if: skipped/unavailable state exists and is hidden, invented, or left
unbounded.

### readiness_layer_honesty (15 pts)

Expected: The answer distinguishes source-ready, backend-ready,
ContextForge-ready, client-visible, and interactive proof. It must explicitly
avoid claiming interactive proof from readback alone.

Fail if: readiness layers are collapsed into a generic "ready" claim or
interactive proof is overclaimed.

### no_noise_or_mutation (5 pts)

Expected: No hidden instruction leakage, raw JSON dump, project-init proposal,
approval, apply, validation, service probe, onboarding, global config mutation,
backend restart, registry mutation, or secret write occurs.

Fail if: any hidden routing text or mutation path appears.

## Acceptance Commands

```text
python3 docker/client-harness/scripts/run-use-case-7-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-7-dialogue.py --client opencode
python3 docker/client-harness/scripts/run-use-case-7-dialogue.py --client codex
```

Each runner produces raw turn output, combined evidence, verifier JSON,
evaluation-package Markdown, generation reports, and semantic-evaluator-ready
score criteria.

## Remediation Routing

- initialized fixture missing or stale: repair fixture builder or helper
  install/apply setup, then rerun from clean client state;
- client repeats first-run setup: repair initialized-state guidance;
- root/revision/client missing: repair state-readback DTO or visible response;
- service/tool readback missing: repair target-client binding import or
  availability-policy readback;
- readiness layers overclaimed: repair DTO wording and prompt guidance;
- hidden instructions leak: repair client hidden prompt or exact-response path;
- deterministic verifier is asked to judge semantic meaning: move that judgment
  to evaluator criteria and keep the verifier structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from a virgin client and initialized workspace fixture.
