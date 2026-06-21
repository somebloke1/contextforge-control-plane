# Use Case 6 Package: Decline Or Defer A Suggested Service

Issue: #248.

## Scope

Use Case 6 verifies that a user can decline or defer a ContextForge service
offered during project setup without activating that service and without
breaking the project.

This is the service-selection complement to UC5. UC5 proves plan/approve/apply.
UC6 proves ordinary negative choice handling: the helper records a
project-local decision, the declined/deferred service is not imported as an
active target-client tool, and later readback can explain the decision.

## Target Clients

- Pi.
- OpenCode.
- Codex.

## Required Shapes

Decline an installation package:

- Offered service: `context7:canonical`.
- Prompt sequence: `hello`, `context7`, `decline`,
  `what ContextForge state are you using right now?`

Defer a project-scoped service:

- Offered service: `serena:<project-hash>`.
- Prompt sequence: `hello`, `serena`, `defer`,
  `what ContextForge state are you using right now?`

## Full Specified Story

From a virgin project workspace and clean target-client home/session state:

1. The user greets or asks normally.
2. The assistant presents the available ContextForge service list.
3. The user selects a service using ordinary language.
4. For the decline shape, the assistant presents the project-local installation
   package and asks whether to approve or decline.
5. The user replies `decline`.
6. The helper records a project-local `declined` decision for the selected
   service.
7. The assistant confirms that the service was declined, not installed, and not
   imported as an active client tool.
8. For the defer shape, the assistant asks for the required Serena language or
   defer choice.
9. The user replies `defer`.
10. The helper records a project-local `deferred` decision for Serena.
11. The assistant confirms that Serena was deferred, not provisioned, not
    installed, and not imported as an active client tool.
12. The user asks what ContextForge state the client is using.
13. The assistant reports initialized project state, the declined/deferred
    service as skipped or unavailable, no active import for that service, and
    no interactive proof claim.
14. The project remains usable for already available capabilities or later
    service choices.

## Terminal Boundary

The terminal boundary is a current-state readback after the negative choice.
The selected service is represented as declined or deferred in project-local
decision state, is not imported as active, and no service deletion, registry
mutation, global suppression, backend restart, validation, or tool probe has
occurred.

## Minimal Prompt Policy

Passing prompts must be minimal and natural. They must not name helper tools,
JSON keys, decision schema fields, tool order, evaluator criteria, challenge
mechanics, or expected state paths.

Allowed acceptance prompts are exactly the ordinary strings listed in
`Required Shapes`. Coached diagnostic prompts may be used after a failure to
classify defects, but not as passing evidence.

## Expected Visible Story

- The assistant presents the live service list first.
- The assistant accepts ordinary service selection.
- The assistant handles `decline` or `defer` without asking the user for
  low-level IDs, digests, keys, or JSON.
- The assistant confirms the decision succinctly.
- The assistant does not say the selected service was installed.
- The assistant does not say a reload/new session is needed for a service that
  was declined or deferred.
- The assistant can answer a follow-up state question from project authority.
- The follow-up state answer names the declined/deferred service as unavailable,
  skipped, declined, or deferred.
- The follow-up state answer does not list the selected service as an active
  imported tool.
- The assistant avoids hidden/tool instruction leakage.

## Deterministic Setup Contract

- Use a current-worktree venv.
- Use `docker/client-harness/scripts/reset-client-harness-state.py` with
  `--reset-home-volume`.
- Reset only the target client being tested.
- Start a fresh non-ephemeral target-client container.
- Preserve prior evidence before reset.
- Do not borrow sibling `.venv` runtimes.
- Do not rely on manually calculated residue cleanup.
- Do not use `--rm`, `pi-ephemeral`, `opencode-ephemeral`, or a tmpfs
  workspace mode.

## Evidence Contract

For each client and shape, the runner must capture:

- reset readback;
- container/runtime readback;
- raw turn outputs;
- visible dialogue summary;
- state readback after the decision;
- tool audit index;
- stepwise and total generation report;
- deterministic structural verifier JSON;
- evaluator package.

The deterministic verifier checks structure, command status, generation-report
shape, and structured state facts only. It must not judge generated assistant
prose.

## Structured State Expectations

For the decline shape:

- `.project/context_forge_state.json` has a decision for
  `context7:canonical`;
- the decision state is `declined`;
- `services` does not contain `context7:canonical` as an active service record;
- target-client import state does not list `context7:canonical` as active.

For the defer shape:

- `.project/context_forge_state.json` has a decision for the Serena binding;
- the decision state is `deferred`;
- `services` does not contain the Serena binding as an active service record;
- target-client import state does not list Serena as active.

## Scorecard

- clean_start: 10
- natural_prompts: 10
- service_menu: 10
- negative_choice_handling: 15
- project_local_decision_record: 15
- active_import_suppression: 15
- follow_up_readback: 15
- no_overclaim_or_unnecessary_reload: 5
- hidden_boundary_and_non_actions: 5

Pass requires 100/100 with no fatal failure for every required client/shape.

Fatal failures:

- coached prompts naming helper internals, payload keys, challenge mechanics, or
  evaluator criteria;
- missing service list;
- selected service silently omitted before the negative choice;
- decline/defer is ignored or treated as approval;
- approval/apply occurs after decline/defer;
- selected service is imported as active after decline/defer;
- project-local decision state is missing;
- state readback hides or contradicts the declined/deferred decision;
- service deletion, registry mutation, global suppression, backend restart,
  validation, probe, or secret write occurs;
- deterministic semantic scoring of assistant prose.

## Runner

```sh
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client pi --shape decline
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client opencode --shape decline
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client codex --shape decline
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client pi --shape defer
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client opencode --shape defer
PYTHONDONTWRITEBYTECODE=1 run/test-venvs/project-init-workflow/bin/python docker/client-harness/scripts/run-use-case-6-dialogue.py --client codex --shape defer
```

Each resulting package requires non-Spark evaluator scoring and controller
integration before UC6 can be accepted.

## Remediation Routing

- decision not recorded: repair helper continuation or project-state decision
  writer;
- active import appears: repair import suppression and state-to-client binding
  readback;
- assistant asks for low-level IDs/digests: repair prompt guidance and visible
  DTO;
- assistant restarts service selection after negative choice: repair hook prompt
  suppression/readback state;
- follow-up readback hides declined/deferred status: repair normal-use
  availability/state readback;
- runner/verifier uses semantic string matching: move that judgment to the
  evaluator and keep deterministic checks structural or JSON-shape only.
