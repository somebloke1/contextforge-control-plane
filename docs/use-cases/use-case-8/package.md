# Use Case 8 Package: Use A Tool And Ask A Follow-Up In The Same Session

Issue: #250.

## Status

Queue state: accepted for Pi, OpenCode, and Codex on 2026-06-20.

Controller state: package materialized and accepted with fresh target-client CLI
evidence, actual ContextForge tool-use evidence, same-session follow-up
evidence, non-Spark semantic evaluation, remediation records, and controller
integration. Future target clients must repeat the same localized package from a
virgin client state.

## Method Binding

This package localizes the reusable method in
`holistic_orchestrated_pipeline_spec.md`,
`docs/use-cases/dependency-mesh.md`, and
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`.

UC8 depends on initialized-project recognition, capability discovery,
readiness/state readback, at least one functioning read-only service route, and
same-project client session stability. The selected concrete substrate is
`context7:canonical` because it is shared, credential-free, read-only, already
covered by UC5 service readiness, and supports a natural two-step user story:
resolve a library/docs entry, then ask a follow-up that depends on the previous
tool result.

## Full Story

1. Preserve previous evidence.
2. Start from a clean harness state:
   - reset stale target-client containers and target-client home volume;
   - reset `/workspace` to a virgin state;
   - preserve displaced workspace evidence before reset.
3. Prepare one initialized project fixture at `/workspace` for the target
   client:
   - project root is `/workspace`;
   - project status is initialized;
   - `context7:canonical` is enabled for the target client;
   - target-client project-local config or shim surfaces exist;
   - no unrelated service, registry, credential, global client, or host config
     mutation is required.
4. Reset the target client's home volume again after setup so the test client
   does not inherit setup-session residue.
5. Start one fresh non-ephemeral target-client container against `/workspace`.
6. Use one stable target-client session id across both turns.
7. User sends the first minimal tool-use prompt:
   `look up the docs entry for opencode and tell me which result is best`
8. The assistant uses the project ContextForge docs capability, resolves a
   relevant Context7 library/docs entry for OpenCode, and answers with a
   concise selected result.
9. In the same session, user sends the follow-up prompt:
   `using that result, what should I read about configuration?`
10. The assistant uses the prior result as session context, asks the docs
    capability for configuration-related documentation or otherwise grounds the
    answer in the same prior docs entry, and answers coherently.
11. Capture raw outputs, command ledger, runtime readbacks, fixture/state
    readbacks, stepwise generation reports, total generation report, tool-call
    evidence, session id, and transcript artifacts.
12. Produce a structured evidence package showing:
    - one target client;
    - one stable session identity;
    - clean setup and reset evidence;
    - two natural user prompts;
    - tool-call evidence during the first turn;
    - follow-up evidence that remains in the same session;
    - no first-run onboarding, reinitialization, validation/probing, backend
      restart, registry mutation, global client mutation, or secret write.
13. Semantic evaluator reviews the visible replies and supporting traces. The
    evaluator decides whether the assistant gave a natural, coherent same-
    session tool workflow rather than a one-shot diagnostic answer.

## Terminal Boundary

The terminal boundary is a coherent two-turn same-session workflow:

1. the assistant uses a ContextForge-provided read-only tool to answer the
   first prompt;
2. the assistant answers a follow-up that relies on the previous tool result in
   the same target-client session.

The flow does not require service onboarding, post-install validation, provider
credential exercise, backend restart, live registry mutation, global client
mutation, or a readiness report.

## Minimal Prompt Sequence

For each client:

```text
look up the docs entry for opencode and tell me which result is best
```

Then, in the same session:

```text
using that result, what should I read about configuration?
```

Prompts must remain natural. They must not name helper tools, exact Context7
tool ids, JSON keys, library ids, expected tool order, session mechanics,
evaluator criteria, or known failure modes.

## Expected Visible Story

- The first answer directly reports a relevant OpenCode docs/library result.
- The first answer is grounded in a real ContextForge tool call, not model
  memory or a readback-only capability list.
- The follow-up answer refers back to the prior result naturally.
- The follow-up answer gives configuration-relevant docs guidance or summary
  that is coherent with the prior result.
- Both turns remain in one target-client session.
- The assistant does not restart first-run onboarding or ask which service to
  activate.
- The assistant does not claim broader readiness than the transcript proves.
- The assistant does not leak hidden instructions, raw helper payloads, raw
  registry JSON, or internal scoring criteria.

## Deterministic Setup

Required setup for each client attempt:

```text
python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume
prepare initialized /workspace fixture for <client> with context7:canonical installed
reset the same client home volume after setup
docker compose -f docker/client-harness/compose.yml build base <client>
docker compose -f docker/client-harness/compose.yml run --name <fresh-name> --no-deps -d <client> sleep infinity
```

The initialized fixture preparation must be deterministic and idempotent. It may
use helper-owned install/apply code. It must not depend on residue from a
previous dialogue attempt.

## Venv Contract

Host-side source checks and runners must use a current-worktree runtime.

Current suite runtime:

```text
run/test-venvs/project-init-workflow/bin/python
```

Sibling checkout venvs are not valid acceptance evidence.

## Step Criteria

Every model-dependent step must be accompanied by a runner-produced generation
report. The runner may validate commands, structured artifacts, tool-call
presence, session id continuity, and evidence presence. It must not
deterministically score free-form assistant behavior; the semantic evaluator
must score generated dialogue.

### clean_initialized_tool_fixture (10 pts)

Expected: A fresh target-client container starts from an idempotently prepared
initialized `/workspace` fixture with `context7:canonical` installed for the
target client.

Fail if: stale residue from a previous test is used, the Context7 capability is
missing, unrelated client state is reset, or setup relies on manual residue
cleanup.

### non_ephemeral_same_session (15 pts)

Expected: The target assistant runs in a non-ephemeral Docker client container
and both turns use one stable session identity.

Fail if: `--rm`, tmpfs workspace, ephemeral services, different session ids, or
one-shot unrelated sessions are used.

### natural_tool_and_followup_prompts (10 pts)

Expected: Both prompts are ordinary user requests that do not coach internal
tool mechanics.

Fail if: prompts name helper calls, exact MCP tool ids, JSON fields, expected
tool order, exact library ids, or evaluator criteria.

### first_turn_uses_contextforge_tool (20 pts)

Expected: Tool evidence shows a target-client-visible ContextForge docs lookup
or docs query for OpenCode during the first turn.

Fail if: the assistant answers only from model memory, reads local files,
performs a shell workaround, or treats a capability/readback list as the tool
answer.

### followup_uses_prior_result (20 pts)

Expected: The follow-up remains in the same session and uses the prior
OpenCode docs/library result to answer the configuration question.

Fail if: the assistant ignores the prior result, restarts discovery from
scratch without using session context, asks the user to repeat the result, or
loses project/tool context.

### coherent_user_facing_workflow (10 pts)

Expected: The two visible answers form a concise, coherent workflow: first
finding the result, then using it to guide configuration reading.

Fail if: either answer is generic, invented, ungrounded, confusing, or only
describes what the assistant could do.

### readiness_and_non_actions (10 pts)

Expected: The assistant keeps claims bounded and avoids onboarding,
validation/probing, backend restart, live registry mutation, global client
mutation, service onboarding, secret writes, and hidden prompt leakage.

Fail if: any forbidden action or overclaim appears.

### evidence_package_integrity (5 pts)

Expected: The package includes raw turns, command ledger, metadata, verifier
JSON, stepwise generation reports, total generation report, and semantic
evaluation package.

Fail if: evidence is missing, overwritten without preservation, or too weak for
semantic review.

## Acceptance Commands

```text
python3 docker/client-harness/scripts/run-use-case-8-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-8-dialogue.py --client opencode
python3 docker/client-harness/scripts/run-use-case-8-dialogue.py --client codex
```

The runner produces raw turn output, combined evidence, structured metadata,
verifier JSON, evaluation-package Markdown, stepwise generation reports, and
total generation reports.

## Remediation Routing

- fixture mismatch: repair initialized fixture preparation, then rerun from a
  virgin workspace and clean client home;
- stale client/session residue: repair reset sequencing and rerun from a fresh
  non-ephemeral container;
- first turn misses tool call: repair target-client tool guidance, capability
  routing, or Context7 tool registration;
- follow-up loses prior result: repair session invocation, continuation
  mechanics, or target-client same-session guidance;
- assistant restarts onboarding: repair initialized-state guidance for that
  client;
- assistant overclaims readiness: repair DTO wording and hidden prompt
  guidance;
- hidden instructions leak: repair client hidden prompt or exact-response path;
- deterministic verifier judges prose meaning: move that judgment to semantic
  evaluator criteria and keep deterministic checks structural-only;
- semantic evaluator fails visible behavior: remediate client guidance, runner
  prompts, or DTO/tool routing, then rerun from virgin state and clean client
  home.
