# Use Case 3 Package: Discover Project Capabilities

## Status

Queue state: controller-accepted after accepted Use Case 2.

Controller state: accepted for the current branch evidence set. Pi and OpenCode
structural runners passed, non-Spark semantic evaluators passed, and the
controller recorded acceptance in
`run/holistic-orchestrator/reports/uc3-controller-acceptance-20260620T012827Z.md`.

Accepted evidence:

- Pi combined evidence:
  `docker/client-harness/evidence/use-case-3/pi/pi-use-case-3-evidence-20260620T012529Z.md`
- Pi evaluator package:
  `docker/client-harness/evidence/use-case-3/pi/pi-evaluation-package-20260620T012529Z.md`
- Pi verifier:
  `docker/client-harness/evidence/use-case-3/pi/pi-verifier-20260620T012529Z.json`
- OpenCode combined evidence:
  `docker/client-harness/evidence/use-case-3/opencode/opencode-use-case-3-evidence-20260620T012548Z.md`
- OpenCode evaluator package:
  `docker/client-harness/evidence/use-case-3/opencode/opencode-evaluation-package-20260620T012548Z.md`
- OpenCode verifier:
  `docker/client-harness/evidence/use-case-3/opencode/opencode-verifier-20260620T012548Z.json`

Deterministic acceptance remains structural only. UC3 semantic acceptance came
from evaluator narratives over the final visible assistant answers, not from
regex, keyword, or string-matching gates.

GitHub source: issue #245, "Ordinary use case 03: Discover available project
capabilities."

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md` and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

Use Case 3 depends on Use Case 2 because it starts from an initialized project
and asks a broader ordinary-work question: not merely which tools are loaded,
but what the assistant can do in this project from current ContextForge and
project authority.

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
5. User sends a minimal natural prompt asking what the assistant can do in the
   project, for example `what can you do in this project?`.
6. The assistant recognizes existing initialization and does not restart the
   first-run service-selection flow.
7. The assistant answers from current project state plus ContextForge catalog
   and tool metadata, without exposing helper/tool-call mechanics.
8. The assistant distinguishes:
   - capabilities available now;
   - known but unavailable capabilities;
   - capabilities that would require onboarding or approval before use.
9. The assistant includes enough high-level provenance to explain why the
   answer reflects current project/ContextForge authority, without forcing raw
   state revisions, JSON keys, helper names, or registry dumps into the visible
   reply.
10. The flow ends without service mutation.

## Terminal Boundary

The terminal boundary is a normal-work capability summary: available-now,
known-unavailable, and onboarding-needed capability classes with concise
authority/provenance. The evidence package must identify the exact project root
and state revision used for the answer, but the visible reply should remain
natural and should not expose raw state revisions unless doing so is useful to
the user. The client must not ask the user to select services, propose
onboarding, apply project-init state, mutate client config, run probes, or show
raw registry noise.

## Minimal Prompt Sequence

```text
what can you do in this project?
```

The prompt must remain natural. It must not name helper tools, project-state
JSON keys, expected service bindings, evaluator criteria, or internal readback
APIs.

## Expected Visible Story

- The assistant sees the project is already initialized.
- The evidence identifies the current project root as `/workspace`.
- The evidence identifies the project-state revision observed from the
  initialized fixture.
- The assistant explains available-now capability for the initial
  `context7:canonical` fixture as Context7 documentation lookup or equivalent
  ordinary language.
- The assistant reports known but unavailable capabilities. If none are present
  in readback, it says none were reported.
- The assistant reports catalog capabilities that would require onboarding or
  approval before use.
- The assistant names or implies its authority at a high level: current project
  state plus ContextForge capability catalog/tool metadata, without helper-call
  narration or registry noise.
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

Fail if: stale residue from a previous test is used as the initialized state;
workspace root is inferred rather than read back; unrelated client state is
reset.

### persistent_client_surface (10 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and one stable session identity is used for the prompt.

Fail if: `--rm`, tmpfs workspace, `pi-ephemeral`, or `opencode-ephemeral` is
used.

### natural_capability_prompt (10 pts)

Expected: The user asks naturally what the assistant can do in the project.

Fail if: the prompt names helper internals, state keys, expected JSON shape, or
service-ordering criteria.

### recognizes_initialized_state (10 pts)

Expected: The assistant does not present the first-run service-selection menu
and does not ask which services to activate.

Fail if: the client restarts Use Case 1, proposes activation, applies state, or
claims initialization is missing when the fixture is initialized.

### evidence_project_root_and_revision (10 pts)

Expected: The evidence identifies `/workspace` and the project-state revision
used by the initialized fixture.

Fail if: the evidence omits exact root or revision, or uses a host checkout path
instead of the container project root. Do not fail solely because the visible
assistant reply avoids raw revision details in an otherwise natural answer.

### reports_available_now (15 pts)

Expected: The assistant names capabilities available now. For the initial
Context7 fixture, this includes Context7 documentation lookup or the Context7
tool names.

Fail if: the answer gives only generic "MCP tools" language or invents
unapproved tools.

### reports_known_unavailable (10 pts)

Expected: The assistant distinguishes known but unavailable capabilities when
present, or makes clear there are no known unavailable capabilities when that
state is relevant to the answer.

Fail if: unavailable capability state exists and is hidden, invented, or merged
into the available-now class. If the initialized fixture reports no known
unavailable capabilities, the evaluator may treat a concise answer that lists
available and onboarding-needed classes as acceptable unless it misleadingly
implies all known capabilities are available.

### reports_onboarding_needed (15 pts)

Expected: The assistant distinguishes capabilities that would require
onboarding or approval before use.

Fail if: it presents unapproved catalog services as already usable, or omits the
onboarding-needed class entirely.

### reports_provenance_without_noise (5 pts)

Expected: The assistant gives concise provenance such as project state plus
ContextForge catalog/tool metadata, or otherwise clearly frames the answer as
the current project's ContextForge capability state.

Fail if: it dumps raw registry JSON, stale client config assumptions, or
backend-only claims.

### no_mutation_or_reinit (5 pts)

Expected: No project-init proposal, approval, apply, service onboarding, global
client install/reload, registry mutation, backend restart, tool probe, or
secret write occurs during capability discovery.

Fail if: any mutation or first-run project-init action appears.

## Acceptance Commands

Current commands:

```text
python3 docker/client-harness/scripts/run-use-case-3-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-3-dialogue.py --client opencode
```

The runner must produce raw turn output, combined evidence, verifier JSON,
evaluation package JSON/Markdown, and semantic-evaluator-ready score criteria.

## Remediation Routing

- initialized fixture missing or stale: repair fixture builder or helper
  install/apply setup, then rerun from clean client state;
- client repeats first-run setup: repair startup/readback guidance;
- capability classes missing: repair capability-summary DTO, prompt guidance,
  or package criteria;
- evidence lacks root/revision, or visible answer lacks natural current-authority
  framing: repair prompt guidance, runner evidence, or helper visible response;
- deterministic verifier is asked to judge semantic meaning: move that judgment
  to evaluator criteria and keep the verifier structural-only;
- semantic evaluator fails visible behavior: remediate client guidance or DTO
  shape, then rerun from a virgin client and initialized workspace fixture.
