---
name: code-assistant-dialogue-validation
description: Evaluate ContextForge client use cases by delegating to a code-assistant dialogue agent that drives real Pi or OpenCode/Codex/Gemini command-line sessions end to end, with a stable session id, continuation across reload/new-session boundaries, observed assistant/tool outputs, and no scripted substitution for agent behavior.
---

# Code Assistant Dialogue Evaluation

Use this skill when a ContextForge acceptance gate depends on how a code
assistant actually behaves in a client session. This skill is for delegated
dev-agent evaluation of dialogue, not for replacing the dialogue with scripts.
A Codex subagent is not a tested-client substitute. Semantic acceptance that relies on tested-assistant behavior needs at least three independent Luna/medium runs when the localized gate requires quorum evidence; Terra/high remains the simulated-human role and Sol/high remains the evaluator role.

## Layering Rule

Keep reusable methodology separate from use-case localization.

The method layer is stable across use cases: idempotent reset, real client
dialogue, minimal natural prompts, raw evidence preservation, deterministic
verifier output, semantic validator narrative, score sheet, and
test-remediate-test looping.

The localization layer is the only place for case-unique content: target
clients, prompt text, selected services, expected visible assistant replies,
supporting tool evidence, forbidden shortcuts, reload/new-session boundary,
scoring weights, and human handoff requirements.

Each localized package must include a reflective-learning slot. After every
attempt, the validator should report whether the evidence surfaced a better
requirement, prompt shape, DTO shape, reset invariant, score criterion, or
skill instruction. Classify the idea as `incorporate_now`,
`promote_regression`, `defer_with_owner`, or `reject_with_rationale`. Do not
silently discard improvement ideas, and do not broaden the current lease
without controller approval.

For the Docker client harness, the reusable method is summarized in
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`. A use-case gate such as
`docker/client-harness/USE_CASE_1_E2E_GATE.md` must localize that method rather
than duplicate or redefine it. Future use cases should require only a new or
updated localization artifact plus any case-specific runner prompt sequence.

## Core Rule

A scripted smoke test can prepare the environment, issue the ordinary CLI
prompts, capture evidence, and assemble the evaluation package. It cannot
satisfy the semantic judgment by itself. The pass must come from a validator
agent reviewing the real target-client dialogue and judging whether it behaved
like the intended human-facing interaction.

Use the right primitive for each part of the gate. Deterministic setup belongs
in deterministic code: evidence preservation, target-client reset, workspace
fixture creation, fixed postcondition checks, and verifier invocation must be
idempotent commands or scripts. Do not ask a language model to infer which
state residue should be removed or whether cleanup is "clean enough." Reserve the delegated language model for the semantic work: driving the target
assistant dialogue, observing tool behavior, judging protocol adherence, and
writing the interaction narrative from real evidence.

For use cases with a maintained runner, the controller should provide the
runner path to the validator. The runner may drive the fixed minimal prompt
sequence and return raw transcripts, verifier output, and an evaluation package.
The validator then scores that package against the criteria rather than
inventing a new harness. If the runner fails before reaching dialogue because
setup is broken, the validator reports the setup failure and does not rewrite
the use-case story.

The evaluation package must include per-step criteria and a scoring rubric.
Each step must distinguish the natural user-facing exchange from supporting
tool evidence:

- the user prompt text should be ordinary human text, not internal tool
  instructions;
- the assistant reply text should carry the user-facing outcome, such as the
  service menu, approval request, installed result, and reload/new-session
  boundary;
- tool calls and tool outputs may be evaluated as audit evidence, but they do
  not need to appear in the assistant's visible prose except where the client
  exposes them as thinking/tool traces;
- evaluator criteria, helper tool names, internal payload keys, and expected
  tool order belong in the package and validator report, not in prompts sent to
  the tested assistant.

Deterministic verification of free-form assistant behavior is disallowed.
Scripts may capture, segment, count, index, and report generated text; they may
validate structured artifacts such as JSON, command status, and required files.
They may check structure, but not meaning. They must not turn matched strings,
regexes, keyword searches, or string parsing into semantic observations,
score criteria, gates, or acceptance. The only exception is a declared
structured model output, such as JSON, where deterministic checks may verify
parseability, schema shape, required fields, and enum/value structure, and only
when that structured-output check is paired with non-deterministic evaluator
review. Hidden instruction leakage, prompt coaching, overclaiming readiness,
and naturalness of the visible answer are semantic findings for an evaluator
narrative, not deterministic verifier findings.

For the Docker client harness, prefer
`docker/client-harness/scripts/reset-client-harness-state.py` as the
deterministic reset primitive before delegated dialogue evaluation. It preserves
workspace residue under `docker/client-harness/evidence/use-case-1/prior/`,
resets only the selected target client's containers/home volume when requested,
recreates the allowlisted `.gitkeep` workspace fixture, and emits JSON
postcondition readback. Validator leases should cite this script instead of
asking agents to manually calculate stale-state deltas.

No truncated use-case test stories are allowed. Any narrative, lease, or
evaluation standard used for dialogue evaluation must be a full specified story
from setup state through final readback, including prompts, decision points,
tool ordering, observed outputs, failure branches, forbidden shortcuts, timing
expectations, scoring/rating dimensions if used, and pass/fail criteria.

Use the project dispatch matrix before assigning the validator model. Long
target-client dialogue evaluation is semantic acceptance work and is not a
Spark work unit. Spark may extract transcript evidence, map fixtures, or make
tiny mechanical patches, but it must not own a multi-turn LM-engaging
dialogue run or target-client readiness judgment.

Model-boundary principle: Spark is suited to code and textual artifacts, not
live agent-behavior judgment. Use Spark for source edits, transcript
extraction, package linting, and fixture mapping. Use a stronger semantic model
for evaluating whether Pi/OpenCode behaved naturally, whether prompts were too
coached, whether hidden instructions leaked, or whether the interaction should
pass.

For semantic harnesses that split the tested assistant from the evaluator,
`gpt-5.4-mini` is acceptable for the tested assistant role when that is the
client/model under test or a cost-bounded dialogue probe. The evaluator role is
not a mini-model role: use `gpt-5.5` for pass/fail semantic judgment, narrative
quality assessment, overclaim detection, and requirement-gap analysis.

Source-lead-only service-onboarding process gates are legacy/quarantined in
the current product direction. Do not invoke
`contextforge-onboarding-semantic-testing` unless a later explicit governance
decision revives arbitrary/new MCP onboarding.

Expect raw CLI/JSON streams to become large. Preserve the raw stream as an
evidence artifact, then use targeted readbacks to extract live values such as
challenge ids, plan digests, and job ids. Do not truncate
the use-case story, and do not replace live readback with pattern guesses.

## Roles

- Controller: assigns the dialogue lease, owns acceptance, GitHub/Project
  state, merge/ready decisions, and remediation sequencing.
- Dialogue validator: a delegated dev agent that drives one target client from
  the command line and reports observed evidence.
- Verifier scripts: audit the captured transcript after the validator run; they
  do not create acceptance evidence.

## Required Lease Shape

The controller lease must include:

- target client and use case, for example `Pi / Use Case 1 context7`;
- exact worktree and branch;
- allowed Docker/client surfaces, naming the non-ephemeral Compose service for
  the target client;
- runtime authority. Host-side source checks must use a runtime created for the
  current worktree and test framework, normally the worktree's `.venv/bin/python`
  or an ignored isolated test venv such as `run/test-venvs/<suite>/bin/python`.
  If dependencies such as `mcp` or `mcpgateway` are missing, create that
  isolated worktree-local venv and install the minimum declared or observed
  dependencies needed to run the suite. Do not borrow another checkout's `.venv`
  unless the controller explicitly authorizes that substitution for a
  diagnostic-only run;
- idempotent target-client reset operation to run before starting, scoped only
  to the target client being evaluated, with a fixed postcondition and readback;
- preferred reset command for Docker harness leases, normally
  `python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode> --reset-home-volume`;
- preferred use-case runner path when one exists, normally
  `python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client <pi|opencode>`;
- requirement that the runner's evaluation package include per-step criteria,
  the reusable methodology summary, the use-case localization summary, scoring
  weights, fatal failure criteria, raw transcript paths, and verifier output;
- requirement that the validator produce a final pre-submission narrative,
  written from the validator's own perspective, that walks through setup and
  each user turn with evidence references and separates runner/package defects
  from tested-client behavior defects;
- requirement that the validator include reflective-learning notes with any
  useful requirement or behavior improvements discovered during the run,
  classified as `incorporate_now`, `promote_regression`, `defer_with_owner`, or
  `reject_with_rationale`;
- virgin per-test harness workspace cleanup and creation. Prior transcripts and forensic
  artifacts must be preserved under the harness `evidence/` tree, not left in
  `/workspace`;
- explicit authority to reset the target-client container plus home/session
  state for a fully virgin target-client instance;
- forbidden host/global/client config, secrets, registry, systemd, production,
  and destructive actions;
- a minimal natural prompt script to send to the client, written as ordinary
  user intent rather than tool instructions;
- a forbidden prompt-coaching list for the validator, including helper tool
  names, internal payload keys, challenge/digest echo instructions, and exact
  internal tool order;
- expected reload/new-session continuation behavior;
- the full specified use-case story being evaluated, not a truncated checklist
  or partial happy path;
- a complete-until-observed stop rule: the lease is incomplete until every
  required user-facing interaction step in the story appears in transcript
  evidence, with tool traces used as supporting evidence for the evaluator;
- transcript path and session id capture method;
- stop condition: pass all expected outcomes or stop at first agent-behavior
  failure with evidence.

The validator must not decide PR readiness. It returns evidence only.

## Dialogue Evaluation Procedure

1. Preserve any prior run transcript needed as evidence by moving or copying it
   to the harness `evidence/` tree before cleanup. Do not leave prior
   transcripts, project-init state, or client config residue in `/workspace` as
   part of the next test's start state.
2. Run an idempotent target-client reset for the attempt. In the Docker client
   harness, use `docker/client-harness/scripts/reset-client-harness-state.py`
   unless the controller lease provides a newer deterministic reset command.
   The reset removes the target client's previous containers, resets only that
   target client's named home/session volume when the lease requires a fully
   clean client instance, and confirms no old target-client container remains.
   The reset command must be safe to run repeatedly and converge on the same
   clean postcondition. Do not prune unrelated
   containers or delete unrelated client volumes. Do not
   rely on manually calculating a stale-state delta as proof of cleanliness.
3. Reset the harness `/workspace` to the lease-defined virgin state for this
   test run, preferably from an allowlisted empty/template state. Verify the
   workspace by an allowlisted readback instead of by claiming particular
   residue was removed. This workspace reset must also be idempotent:
   re-running it produces the same empty/template-exact start state. Persistence is required only inside the single evaluation run, not between separate test
   attempts.
4. Start that client's freshly created non-ephemeral Compose service. Do not use `--rm`,
   `pi-ephemeral`, `opencode-ephemeral`, or any tmpfs workspace service for a
   dialogue-evaluation pass that requires reload, resume, new-session
   continuation, or state survival across CLI calls.
5. Before any host-side test command, verify or create the worktree-local
   Python runtime required by the test. If a test imports project dependencies
   such as `mcp` or `mcpgateway` and the current worktree lacks them, create an
   ignored isolated test venv under a path such as `run/test-venvs/<suite>/` and
   install the minimum declared or observed dependencies needed to run the
   suite. Do not silently run the test with a sibling checkout's `.venv`; that
   produces false confidence. Container-local harness runtimes such as
   `/opt/contextforge-wrapper-venv` are allowed only when they are part of the
   target client container being tested.
6. Enter or run commands in that persistent client container so the container
   and `/workspace` state survive CLI continuation, reload, and new-session
   steps.
7. Record the evidence preservation command, cleanup command, cleanup readback,
   launch command, cwd, target client, model, and session id.
8. Use the client as an assistant, not as a script runner.
9. Send minimal, ordinary prompts a human would naturally send for the use
   case. The validator may express intent such as "hello", "1", "approve",
   "done" or "continue", but must not name the expected helper
   tools, target-client fields, challenge/digest
   mechanics, or exact tool ordering. Be patient with local-model responses:
   wait at least 90 seconds for each assistant response when needed before
   treating the response as missing or stalled.
10. Follow the localized terminal boundary for the assigned use case. For Use
   Case 1, the boundary is installed plus reload/new-session-required; for
   other use cases, use the case localization artifact rather than importing
   Use Case 1 assumptions.
11. Stop at the localized terminal boundary. Do not continue into extra work
   merely because the client remains interactive.
12. Capture full user, assistant, tool-call, and tool-output transcript. If the
    client emits JSON, preserve the raw tool events and add an observed tool
    index with `Tool:` markers that reference only real transcript entries.
    Pi HTML exports must have their embedded `session-data` payload decoded
    before pass/fail judgment; the base64 wrapper is not itself auditable
    dialogue evidence.
    The observed tool index must be built from real tool-call events, not prose
    such as "I will call tool X next." Tool events are supporting evidence for
    the evaluator. The tested assistant's visible prose should remain a normal
    user-facing exchange, not a technical call log.
   Large raw streams may be stored separately from the narrative transcript, but
   the narrative must cite targeted readbacks from the raw stream for every live
   value used in later prompts.
13. Continue remediation/testing loops only when the controller assigns a new
   dialogue lease after a fix.
14. Stop when the expected outcome passes cleanly or the first blocking
   behavior failure is observed. Do not stop at proposal, approval, reload, or
   other intermediate checkpoints unless directly interrupted by the controller.
15. Before submitting a verdict, write a step-by-step narrative of the testing
   session from your own perspective after the interaction is complete or has
   reached its safety bound. Evaluate every turn in that after-action review,
   but do not run evaluator calls during the live conversation and do not spend
   one evaluator invocation per turn. For each material step, cite the exact
   transcript, raw turn, verifier, or package artifact used; describe the
   natural prompt, visible assistant reply, hidden/extension message if
   relevant, supporting tool evidence, and outcome; and classify any problem as
   runner/package defect, tested-client behavior defect, environment/setup
   defect, or inconclusive. This narrative is an additional semantic signal and
   must not replace raw evidence or deterministic verifier output.
16. Add reflective-learning notes. Surface useful refinements discovered during
   the run, classify each one, and keep them distinct from the pass/fail verdict
   unless the localized package already requires them.
17. If interrupted, write an interruption-safe checkpoint before returning:
   session id, container, last observed tool, current challenge id, plan digest,
   activation job id when known, next required action, and whether the transcript
   is incomplete rather than failed by target-client behavior.

## Prompt Minimality

The activation prompt is part of the test surface. It must supply the smallest
natural-language signal needed for the use case and then let the tested
assistant reveal whether the project guidance, helper prompts, and client tool
surface are sufficient.

Passing evidence must come from an uncoached control run. A validator may not
turn a failing control run into a pass by telling the tested assistant:

- which helper tool to call, such as `cf_project_init_approve`;
- which JSON keys to include, such as `challenge_id` or `plan_digest`;
- that a specific tool must run before another tool;
- to avoid known bad paths such as presumed-working, shell commands, backend
  probes, or direct file edits;
- to report a pass/fail conclusion using the evaluator's criteria.

Those details belong in the delegated evaluator's narrative review and the
controller's remediation plan, not in the user prompts sent to the tested
assistant. A coached diagnostic retry can be useful after a failure to isolate
root cause, but it is explicitly diagnostic evidence and cannot satisfy the
dialogue-evaluation pass.

Prompt skeletons belong to the use-case localization artifact. For Use Case 1,
the localized skeleton is `hello`, `1`, `approve`; other use cases must define
their own minimal prompt sequence.

## General Pass Criteria

A dialogue evaluation pass requires:

- one coherent dialogue thread with stable session identity or explicit
  continuation chain;
- non-ephemeral target-client container use, with the cleanup and launch
  commands visible in the transcript or report;
- a virgin per-test `/workspace` start state. Residue from a previous evaluation
  attempt must not remain in `/workspace`; historical evidence belongs under
  `evidence/`;
- a freshly created target-client container and, when required by lease, reset
  target-client home/session state. Cleanliness must be proven by recreation
  and allowlisted readback, not by a best-effort residue-removal delta;
- idempotent reset proof: the reset operation is fixed, repeatable, scoped to
  the target client, and has an observed clean postcondition;
- host-side source-check commands, if used, ran in a current-worktree Python
  environment created for the worktree and test framework. If the default
  `.venv` is missing dependencies, an ignored isolated venv such as
  `run/test-venvs/<suite>/` is acceptable and preferred over blocking. A sibling
  checkout's `.venv` is not equivalent evidence;
- the assistant sees the relevant use-case guidance through the target client
  surface;
- the assistant does not choose user-owned decisions on behalf of the user;
- the validator prompts are minimal natural user prompts and do not coach
  internal tool names, payload keys, or expected ordering;
- every required user-facing step in the localized full story is observed in
  order before the lease is considered complete, with tool traces used to audit
  how the assistant reached those visible outcomes;
- no helper rejection is needed to teach the required localized sequence;
- the final assistant response reaches the localized terminal state and stops.

Concrete expected outcomes, permitted tools, forbidden shortcuts, and terminal
copy belong in the use-case localization artifact. For Use Case 1, that
localization requires helper/project-init discovery, proposal, approval/apply,
no post-install checks, and installed plus reload/new-session-required final
copy.

## Failure Conditions

Fail the gate and return evidence if any of these occur:

- no stable session id or continuation chain;
- evidence used an ephemeral service, tmpfs workspace service, or `--rm` for
  the target-client dialogue session;
- stale state from a previous target-client container was carried into the run,
  or cleanup/recreation affected unrelated client types;
- `/workspace` contains stale transcripts, project-init state, client config, or
  other residue from a previous evaluation attempt at test start;
- reset depends on a human or agent deciding what residue should be removed
  instead of an idempotent operation with a fixed postcondition;
- a host-side source or unit check that needs project dependencies is run with a
  different checkout's `.venv` instead of a current-worktree runtime or
  current-worktree isolated test venv;
- target-client home/session state required to be virgin by the lease was not
  reset, or unrelated client home/session state was reset;
- the transcript relies on pre-existing initialized state instead of exercising
  the expected use-case flow from the first prompt;
- validator prompts coach the tested assistant with internal helper tool names,
  internal payload schema, approval key mechanics, expected tool order, or
  evaluator pass/fail criteria;
- model lacks the expected client-visible tools;
- assistant calls retired post-apply project-init tools;
- assistant invents post-apply payloads;
- assistant uses shell/package/backend substitutes as part of project init;
- helper returns permission, missing-field, or
  equivalent rejection during a supposed passing run;
- assistant asks the user to continue after the installation package
  has been applied;
- validator stops at an intermediate checkpoint without a direct controller
  interruption and without recording an interruption-safe checkpoint;
- any forbidden mutation surface is touched.

## Output Contract

The validator report must include:

- validator agent id and controller lease id;
- client, command line, cwd, model, session id, and transcript path;
- pass/fail verdict for each expected outcome;
- completed score sheet and final pre-submission narrative, including
  step-by-step evidence references and defect classification;
- first failure point with line references or excerpt;
- exact non-actions observed;
- whether the run completed or was interruption-incomplete, including the
  checkpoint fields needed to resume without inference;
- verifier command and output, if a verifier exists;
- residual risk and requested controller action.

The controller may use verifier scripts to audit this report, but acceptance
requires the dialogue transcript itself.
