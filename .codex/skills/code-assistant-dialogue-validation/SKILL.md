---
name: code-assistant-dialogue-validation
description: Validate ContextForge client use cases by delegating to a code-assistant validation agent that drives real Pi/OpenCode/Codex/Gemini command-line dialogue sessions end to end, with a stable session id, continuation across reload/new-session boundaries, observed assistant/tool outputs, and no scripted substitution for agent behavior.
---

# Code Assistant Dialogue Validation

Use this skill when a ContextForge acceptance gate depends on how a code
assistant actually behaves in a client session. This skill is for delegated
dev-agent validation of dialogue, not for replacing the dialogue with scripts.

## Core Rule

A scripted smoke test can prepare the environment or audit captured evidence.
It cannot satisfy a human-facing dialogue gate. The pass must come from a
validator agent conducting the same interaction a human would conduct through
the target client CLI.

Use the right primitive for each part of the gate. Deterministic setup belongs
in deterministic code: evidence preservation, target-client reset, workspace
fixture creation, fixed postcondition checks, and verifier invocation must be
idempotent commands or scripts. Do not ask a language model to infer which
state residue should be removed or whether cleanup is "clean enough." Reserve the delegated language model for the semantic work: driving the target
assistant dialogue, observing tool behavior, judging protocol adherence, and
writing the interaction narrative from real evidence.

For the Docker client harness, prefer
`docker/client-harness/scripts/reset-client-harness-state.py` as the
deterministic reset primitive before delegated validation. It preserves
workspace residue under `docker/client-harness/evidence/use-case-1/prior/`,
resets only the selected target client's containers/home volume when requested,
recreates the allowlisted `.gitkeep` workspace fixture, and emits JSON
postcondition readback. Validator leases should cite this script instead of
asking agents to manually calculate stale-state deltas.

No truncated use-case test stories are allowed. Any narrative, lease, or
evaluation standard used for dialogue validation must be a full specified story
from setup state through final readback, including prompts, decision points,
tool ordering, observed outputs, failure branches, forbidden shortcuts, timing
expectations, scoring/rating dimensions if used, and pass/fail criteria.

Use the project dispatch matrix before assigning the validator model. Long
target-client dialogue validation is semantic acceptance work and is not a
Spark work unit. Spark may extract transcript evidence, map fixtures, or make
tiny mechanical patches, but it must not own a multi-turn LM-engaging
validation run or target-client readiness judgment.

Expect raw CLI/JSON streams to become large. Preserve the raw stream as an
evidence artifact, then use targeted readbacks to extract live values such as
challenge ids, plan digests, job ids, and validation statuses. Do not truncate
the use-case story, and do not replace live readback with pattern guesses.

## Roles

- Controller: assigns the validation lease, owns acceptance, GitHub/Project
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
- idempotent target-client reset operation to run before starting, scoped only
  to the target client being validated, with a fixed postcondition and readback;
- preferred reset command for Docker harness leases, normally
  `python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode> --reset-home-volume`;
- virgin per-test harness workspace cleanup and creation. Prior transcripts and forensic
  artifacts must be preserved under the harness `evidence/` tree, not left in
  `/workspace`;
- explicit authority to reset the target-client container plus home/session
  state for a fully virgin target-client instance;
- forbidden host/global/client config, secrets, registry, systemd, production,
  and destructive actions;
- required prompts to send to the client;
- expected reload/new-session continuation behavior;
- the full specified use-case story being evaluated, not a truncated checklist
  or partial happy path;
- a complete-until-observed stop rule: the lease is incomplete until every
  required client-visible tool in the story has actually appeared in transcript
  evidence in the required order;
- transcript path and session id capture method;
- stop condition: pass all expected outcomes or stop at first agent-behavior
  failure with evidence.

The validator must not decide PR readiness. It returns evidence only.

## Dialogue Validation Procedure

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
   re-running it produces the same empty/template-exact start state. Persistence is required only inside the single validation run, not between separate test
   attempts.
4. Start that client's freshly created non-ephemeral Compose service. Do not use `--rm`,
   `pi-ephemeral`, `opencode-ephemeral`, or any tmpfs workspace service for a
   dialogue-validation pass that requires reload, resume, new-session
   continuation, or state survival across CLI calls.
5. Enter or run commands in that persistent client container so the container
   and `/workspace` state survive CLI continuation, reload, and new-session
   steps.
6. Record the evidence preservation command, cleanup command, cleanup readback,
   launch command, cwd, target client, model, and session id.
7. Use the client as an assistant, not as a script runner.
8. Send the same prompts a human would send for the use case. Be patient with
   local-model responses: wait at least 90 seconds for each assistant response
   when needed before treating the response as missing or stalled.
9. When the helper requires reload or new session, continue the same validation
   thread using the client-supported continuation/resume mechanism and record
   the continued session id.
10. Treat reload acknowledgement as its own narrow action. Record only that the
   target client was reloaded or continued. Do not pass `validationMode`, do
   not choose skip or presumed-working, and do not record final validation until
   the target-client-visible safe probe or validation tool has actually run.
11. Capture full user, assistant, tool-call, and tool-output transcript. If the
    client emits JSON, preserve the raw tool events and add an observed tool
    index with `Tool:` markers that reference only real transcript entries.
    Pi HTML exports must have their embedded `session-data` payload decoded
    before pass/fail judgment; the base64 wrapper is not itself auditable
    dialogue evidence.
    The observed tool index must be built from real tool-call events, not prose
    such as "I will call tool X next."
   Large raw streams may be stored separately from the narrative transcript, but
   the narrative must cite targeted readbacks from the raw stream for every live
   value used in later prompts.
12. Continue remediation/testing loops only when the controller assigns a new
   validation lease after a fix.
13. Stop when the expected outcome passes cleanly or the first blocking
   behavior failure is observed. Do not stop at proposal, approval, reload, or
   other intermediate checkpoints unless directly interrupted by the controller.
14. If interrupted, write an interruption-safe checkpoint before returning:
   session id, container, last observed tool, current challenge id, plan digest,
   activation job id when known, next required action, and whether the transcript
   is incomplete rather than failed by target-client behavior.

## Pass Criteria

A dialogue validation pass requires:

- one coherent validation thread with stable session identity or explicit
  continuation chain;
- non-ephemeral target-client container use, with the cleanup and launch
  commands visible in the transcript or report;
- a virgin per-test `/workspace` start state. Residue from a previous validation
  attempt must not remain in `/workspace`; historical evidence belongs under
  `evidence/`;
- a freshly created target-client container and, when required by lease, reset
  target-client home/session state. Cleanliness must be proven by recreation
  and allowlisted readback, not by a best-effort residue-removal delta;
- idempotent reset proof: the reset operation is fixed, repeatable, scoped to
  the target client, and has an observed clean postcondition;
- the assistant sees project-init guidance through the target client surface;
- the assistant chooses no service, approval, reload, validation, or skip action
  on behalf of the user;
- the assistant uses helper/project-init tools for discovery, proposal,
  approval/apply, reload acknowledgement, and validation recording;
- target-client validation uses the actual visible ContextForge tool or
  client shim, not backend health, shell commands, package CLIs, direct stdio,
  direct generated Context7 service tools, local files, direct
  `.project/context_forge_state.json` mutation, or invented JSON;
- the assistant calls safe probe before record-validation;
- every required client-visible tool in the full story is observed in order
  before the lease is considered complete;
- no helper rejection is needed to teach the required sequence;
- final readback is initialized/passed for the selected service and target
  client.

## Failure Conditions

Fail the gate and return evidence if any of these occur:

- no stable session id or continuation chain;
- evidence used an ephemeral service, tmpfs workspace service, or `--rm` for
  the target-client dialogue session;
- stale state from a previous target-client container was carried into the run,
  or cleanup/recreation affected unrelated client types;
- `/workspace` contains stale transcripts, project-init state, client config, or
  other residue from a previous validation attempt at test start;
- reset depends on a human or agent deciding what residue should be removed
  instead of an idempotent operation with a fixed postcondition;
- target-client home/session state required to be virgin by the lease was not
  reset, or unrelated client home/session state was reset;
- the transcript relies on pre-existing initialized state instead of exercising
  the expected use-case flow from the first prompt;
- model lacks the expected client-visible tools;
- assistant calls record-validation before the safe probe;
- assistant invents `validation_results`;
- assistant uses shell/package/backend substitutes for target-client proof;
- helper returns permission, insufficient validation, missing-field, or
  equivalent rejection during a supposed passing run;
- assistant claims completion while target-client validation is pending,
  skipped, presumed, or failed;
- validator stops at an intermediate checkpoint without a direct controller
  interruption and without recording an interruption-safe checkpoint;
- any forbidden mutation surface is touched.

## Output Contract

The validator report must include:

- validator agent id and controller lease id;
- client, command line, cwd, model, session id, and transcript path;
- pass/fail verdict for each expected outcome;
- first failure point with line references or excerpt;
- exact non-actions observed;
- whether the run completed or was interruption-incomplete, including the
  checkpoint fields needed to resume without inference;
- verifier command and output, if a verifier exists;
- residual risk and requested controller action.

The controller may use verifier scripts to audit this report, but acceptance
requires the dialogue transcript itself.
