# Use Case 2 Package: Resume Initialized Project And See Tools

## Status

Queue state: controller-accepted after accepted Use Case 1.

Controller state: accepted for the current branch evidence set. Pi and OpenCode
structural runners passed, non-Spark semantic evaluators passed, and the
controller recorded acceptance in
`run/holistic-orchestrator/reports/uc2-controller-acceptance-20260620T012346Z.md`.

Accepted evidence:

- Pi combined evidence:
  `docker/client-harness/evidence/use-case-2/pi/pi-use-case-2-evidence-20260620T010847Z.md`
- Pi evaluator package:
  `docker/client-harness/evidence/use-case-2/pi/pi-evaluation-package-20260620T010847Z.md`
- Pi verifier:
  `docker/client-harness/evidence/use-case-2/pi/pi-verifier-20260620T010847Z.json`
- OpenCode combined evidence:
  `docker/client-harness/evidence/use-case-2/opencode/opencode-use-case-2-evidence-20260620T012106Z.md`
- OpenCode evaluator package:
  `docker/client-harness/evidence/use-case-2/opencode/opencode-evaluation-package-20260620T012106Z.md`
- OpenCode verifier:
  `docker/client-harness/evidence/use-case-2/opencode/opencode-verifier-20260620T012106Z.json`

Deterministic acceptance remains structural only. UC2 semantic acceptance came
from evaluator narratives over the final visible assistant answers, not from
regex, keyword, or string-matching gates.

GitHub source: issue #244, "Ordinary use case 02: Resume an initialized project
and see available tools."

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md` and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

Use Case 2 depends on Use Case 1 because it starts from an already initialized
project state produced by the same project-init surface. The starting workspace
is not a fresh uninitialized fixture; it is a clean fixture containing approved
project-local ContextForge state for the target client.

## Full Story

1. Preserve previous evidence.
2. Prepare a clean initialized-project fixture for the target client:
   - exact project root is `/workspace`;
   - `.project/context_forge_state.json` exists and identifies the project root;
   - state revision is visible in evidence;
   - approved `context7:canonical` binding exists for the target client;
   - target client config exists when the client requires one, such as
     `/workspace/opencode.json` for OpenCode.
3. Reset only the target client's home/session volume and stale containers.
4. Start a fresh non-ephemeral target-client container from that initialized
   workspace fixture.
5. User sends a minimal natural prompt asking what tools are available, for
   example `what ContextForge tools are available?`.
6. The assistant recognizes existing initialization and does not restart the
   first-run service-selection flow.
7. The assistant reports the approved ContextForge-backed tools available for
   normal work.
8. The assistant surfaces unavailable or skipped services clearly if any are
   present in readback.
9. The flow ends without service mutation.

## Terminal Boundary

The terminal boundary is a normal-work availability report: exact project root,
state revision, visible approved tool set, and any unavailable/skipped services.
The client must not ask the user to select services, propose a new activation
package, apply project-init state, mutate client config, or claim tool
availability from backend-only readback.

## Minimal Prompt Sequence

```text
what ContextForge tools are available?
```

The prompt must remain natural. It must not name helper tools, project-state
JSON keys, expected tool names, evaluator criteria, or internal readback APIs.

## Expected Visible Story

- The assistant sees the project is already initialized.
- The assistant reports the current project root as `/workspace`.
- The assistant reports the project-state revision observed from the initialized
  fixture.
- The assistant lists the approved ContextForge-backed tool names for the
  selected service. For the initial `context7:canonical` fixture this means the
  Context7 documentation lookup tools exposed through the target client.
- The assistant states unavailable/skipped services if the client readback
  reports any.
- The assistant does not repeat first-run setup or ask which service to
  activate.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode> --reset-home-volume
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

Every agent/model-dependent step must be accompanied by a runner-produced
generation report. The report must include the prompt, artifact ref, return
code, timeout, model/client identity, assistant-output size, event counts where
available, tool-call counts, and total generation/session counts. The runner
may validate structured artifacts and command facts, but it must not
deterministically score the semantic quality of free-form assistant replies.
The semantic evaluator must score both each step generation and the total
interaction.

### clean_initialized_start (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized workspace fixture.

Evidence: reset postconditions; initialized fixture readback; exact project
root `/workspace`; state revision; selected service binding.

Fail if: stale residue from a previous test is used as the initialized state;
workspace root is inferred rather than read back; unrelated client state is
reset.

### persistent_client_surface (10 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and one stable session identity is used for the prompt.

Fail if: `--rm`, tmpfs workspace, `pi-ephemeral`, or `opencode-ephemeral` is
used.

### natural_availability_prompt (10 pts)

Expected: The user asks naturally what ContextForge tools are available.

Fail if: the prompt names helper internals, state keys, expected JSON shape, or
tool-ordering criteria.

### recognizes_initialized_state (15 pts)

Expected: The assistant does not present the first-run service-selection menu
and does not ask which services to activate.

Fail if: the client restarts Use Case 1, proposes activation, applies state, or
claims initialization is missing when the fixture is initialized.

### reports_project_root_and_revision (15 pts)

Expected: The assistant or tool-visible evidence identifies `/workspace` and
the project-state revision.

Fail if: the report omits exact root or revision, or uses a host checkout path
instead of the container project root.

### reports_visible_tool_set (20 pts)

Expected: The assistant lists the approved ContextForge-backed tools visible to
the target client. For the initial Context7 fixture, include documentation
lookup capability names or clear user-facing equivalents.

Fail if: the answer relies on backend-only readback, generic service names with
no tools, or invented tool names.

### reports_skips_or_unavailable (10 pts)

Expected: The assistant clearly reports unavailable/skipped services when the
client readback contains any; otherwise it states no unavailable services were
reported.

Fail if: skipped/unavailable services are hidden or invented.

### no_mutation_or_reinit (10 pts)

Expected: No project-init proposal, approval, apply, service mutation, global
client install/reload, registry mutation, backend restart, or secret write
occurs during the availability report.

Fail if: any mutation or first-run project-init action appears.

## Acceptance Commands

Current structural runner commands:

```text
python3 docker/client-harness/scripts/run-use-case-2-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-2-dialogue.py --client opencode
```

The runner must produce raw turn output, combined evidence, verifier JSON,
evaluation package Markdown, metadata JSON, generation reports, and
semantic-evaluator-ready score criteria. The verifier checks structure only;
semantic acceptance requires non-Spark evaluator review of the real dialogue.

## Remediation Routing

- initialized fixture missing or stale: repair fixture builder or helper
  install/apply setup, then rerun from clean client state;
- client repeats first-run setup: repair startup/readback guidance;
- tool list missing after initialized readback: repair target-client import or
  readback surface;
- output lacks root/revision: repair prompt guidance or package criteria;
- deterministic verifier is asked to judge semantic meaning: move that judgment
  to evaluator criteria and keep the verifier structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from a virgin client and initialized workspace fixture.
