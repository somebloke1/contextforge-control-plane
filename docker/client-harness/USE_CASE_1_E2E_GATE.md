# Use Case 1 End-to-End Agent Gate

This gate applies to PR #271 and the first cumulative #247 service slice:
`context7:canonical` through Pi client Docker and OpenCode client Docker.

Human validation must not be requested until this gate has passed with full
delegated code-assistant dialogue evidence for both clients. Use the project
skill `.codex/skills/code-assistant-dialogue-validation/SKILL.md` for that
lease. Source tests, direct helper calls, backend probes, smoke scripts,
evidence verifiers, and hand-shaped validation payloads are useful diagnostics,
but they are not substitutes for a delegated agent actually driving the client
dialogue.

## Required Order

1. Run the existing source/unit/static checks.
2. Rebuild any changed client harness images.
3. Delegate a Pi dialogue-validation lease to a dev agent. That agent must run
   the Pi client from the command line in the non-ephemeral Pi harness
   container and conduct the full use-case dialogue.
4. Delegate an OpenCode dialogue-validation lease to a dev agent. That agent
   must run OpenCode from the command line in the non-ephemeral OpenCode
   harness container and conduct the full use-case dialogue.
5. Verify the two captured transcripts with
   `scripts/verify-use-case-1-e2e-evidence.py`.
6. If any required outcome fails, remediate the source/harness/prompt defect,
   rerun the affected source checks, rebuild changed images, rerun the full
   affected agent session from the command line, and rerun the verifier.
7. Repeat testing -> remediation -> testing until both clients pass every
   expected outcome in observed agent interaction evidence.
8. Only after all prior steps pass, ask for human validation.

If either client fails, the branch remains in agent repair. Do not ask the
operator to discover the next failure by hand.

This is a loop, not a one-shot checklist. A partial pass followed by a later
agent failure resets the gate to remediation. A helper rejection that the agent
eventually recovers from is still a failed gate when the required user-facing
interaction was supposed to be clean. Human testing is an acceptance check after
delegated dialogue-agent evidence passes; it is not the mechanism for
discovering ordinary integration failures.

## What Counts As End-to-End Agent Evidence

Each client needs one continuous command-line agent session with a stable
session id or explicit continuation chain. A delegated dev agent must conduct
the session by prompting/instructing the target assistant and observing its
responses. The evidence must show the real model-driven assistant behavior, not
only helper calls, shell probes, or scripted command output.

No truncated use-case test stories are allowed. Use Case 1 evaluation must be
based on the full specified story from clean harness setup through final
readback: setup assumptions, prompt sequence, assistant decision points, tool
ordering, observed outputs, reload/new-session behavior, failure branches,
forbidden shortcuts, timing expectations, scoring/rating dimensions if used,
and pass/fail criteria. A partial happy path, summary, or clipped transcript is
not enough to rate or pass the interaction.

This target-client validation is semantic acceptance work. Do not assign the
full multi-turn Pi/OpenCode dialogue run to Spark. Spark can extract transcript
evidence, map fixtures, or make bounded mechanical patches, but the validator
that conducts the LM-engaging client session must be a non-Spark model suited
to long stateful interaction.

Raw client JSON streams can be large. Passing evidence may keep the full raw
stream in a companion artifact and use targeted readbacks to extract live
challenge ids, plan digests, job ids, and validation statuses, but the full
story must remain reconstructable from preserved evidence. Targeted readbacks
are an evidence-indexing method, not permission to truncate the story or guess
values from patterns.

Do not invert deterministic and semantic responsibilities. Evidence
preservation, target-client reset, workspace fixture creation, postcondition
readback, and verifier invocation must be scripted/idempotent. The delegated
language-model validator is responsible for the high-dimensional semantic work:
driving the target assistant dialogue, observing assistant/tool outputs, and
judging whether the full user-facing interaction satisfied the use-case story.
The validator must not use pattern matching or residue-delta inference as a
substitute for either deterministic reset or semantic interaction judgment.

For Docker client harness validation, the preferred reset primitive is
`python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode> --reset-home-volume`.
The script preserves prior workspace artifacts under
`docker/client-harness/evidence/use-case-1/prior/`, resets only the selected
client's container/home state, recreates the allowlisted `.gitkeep` workspace
fixture, and prints fixed JSON postcondition readback. Use a different reset
only when a lease names a newer deterministic command with the same or stronger
postconditions.

Each validation attempt starts from a disposable fresh target-client instance
and a virgin test workspace. Prior transcripts and forensic artifacts must be
moved or copied into
`docker/client-harness/evidence/` before the next run; they must not remain in
`docker/client-harness/workspace/` as part of the next run's start state. The
older shorthand still applies: Each validation attempt starts from a virgin test workspace.
The validator must run an idempotent reset that recreates only the client type
being tested, reset `/workspace` to the lease-defined clean start state, then
use a freshly created non-ephemeral Compose service for that client. Container cleanup is not volume or workspace cleanup:
a virgin run also requires the target client home/session volume to be reset
when the lease calls for a fully clean client instance, plus explicit
`/workspace` cleanup/readback. Do not rely on manually calculating the stale
state delta that must be removed; cleanliness must be proven by fresh
target-client recreation and allowlisted workspace readback. The reset
operation itself must be repeatable and converge on the same clean postcondition
every time; if it depends on a person or agent deciding which residue to remove,
it is not acceptable gate setup. Persistence is required
only inside a single validation run so reload, resume, and new-session behavior
can be observed against surviving state. There is no validation value in carrying
project-init residue from one test attempt into the next.

For compatibility with older validator leases: remove stale containers only for the client type being
tested, but treat that as one step inside the idempotent target-client reset,
not as sufficient proof of cleanliness by itself.

The gate fails if the dialogue uses `--rm`, `pi-ephemeral`,
`opencode-ephemeral`, a tmpfs workspace service, or any launch mode where the
container and `/workspace` state are discarded between CLI calls inside the
same test run. The gate also fails if `/workspace` starts with stale
project-init state, client config, old transcripts, or prior validation residue.
Named client home/session state should be reset only when the lease requires a
fully virgin client home for that target client; unrelated client homes and
volumes must not be touched.

Local Qwen responses can be slow. The validator must wait at least 90 seconds
for each assistant response when needed before classifying a response as
missing, stalled, or failed.

The transcript must include:

- the session id used for the run;
- the delegated validator agent id and lease id;
- the client-specific target-instance recreation command;
- cleanup/readback showing stale target-client containers are gone and the
  target-client home/session state was reset when the lease requires it;
- the idempotent reset command and its fixed postcondition readback;
- when using the Docker harness, the
  `docker/client-harness/scripts/reset-client-harness-state.py` command output;
- the workspace cleanup or reset command and readback proving the test started
  from a virgin `/workspace`;
- the non-ephemeral command line used to start or resume the session;
- the complete user prompts and assistant/tool outputs for the lifecycle;
- service discovery/menu presentation for `context7:canonical`;
- service selection using the helper-discovered service id;
- scoped approval and apply of only project-local state/config;
- reload or new-session acknowledgement when required;
- target-client-visible Context7 safe probe output;
- helper validation recording from the observed safe probe result;
- final initialized/passed readback;
- explicit non-actions for host/global client config, legacy/live
  ContextForge, secrets, trust, systemd, and production registry state.
- raw tool events when available and an observed tool-output index using
  literal `Tool:` markers that references only transcript entries.
- Pi HTML exports are acceptable evidence only when the embedded
  `session-data` payload is decoded and audited as ordered user, assistant,
  tool-call, and tool-result events.
- targeted readbacks for every live challenge id, plan digest, job id, and
  validation result copied into a later prompt.

Captured summaries are not enough. The evidence must contain the observed
assistant messages, tool calls, and tool outputs that prove the agent followed
the flow.

The expected outcome is not merely that a final helper field says initialized.
The observed agent interaction must complete the use case cleanly: correct
service menu, correct selection, scoped approval, required reload/new-session
step, correct target-client safe probe, validation recording from that observed
probe, and a final initialized/passed readback with no forbidden substitutes or
rejection-driven learning loop.

A delegated validation lease is incomplete until every required observed tool
event in the full story has appeared in the captured transcript in order. The
validator must not stop at proposal, approval, reload, or any other
intermediate checkpoint unless directly interrupted by the controller. If
interrupted, the transcript/report must include an interruption-safe checkpoint:
session id, container, last observed tool, live challenge id, plan digest,
activation job id when known, next required action, and a clear
`interruption-incomplete` status distinct from target-client failure.

## Pi Pass Criteria

The Pi evidence must show:

- a persistent Pi session id, either in the captured transcript or supplied to
  the verifier with `--session-id`;
- the session ran from the non-ephemeral Pi client Docker harness against
  `/workspace`;
- `qwen3.6-a3b` was the active model;
- `context7:canonical` was selected from helper-discovered choices;
- reload was acknowledged with `cf_project_init_record_client_reload`;
- validation used `cf_contextforge_pi_validate`;
- `cf_contextforge_pi_validate` returned `pi_validation_complete`;
- validation was recorded with `cf_project_init_record_validation`;
- final helper output contained `status=validation_recorded` and
  `project_status=initialized`.

The Pi gate fails if the agent uses shell substitutes such as
`python3 -m context7_*`, `which context7-*`, `npx @upstash/context7-mcp`, direct
backend probes, direct generated Context7 service tools, local file inspection,
or direct `.project/context_forge_state.json` mutation as validation proof. Pi
validation must go through the Pi-visible ContextForge shim/tool surface. Pi validation must not be inferred from local state.

The Pi gate also fails if the assistant records validation in `presume_working`
mode, records validation before `cf_contextforge_pi_validate`, or claims
completion from readback/tool availability without a `pi_validation_complete`
result, or without `cf_contextforge_pi_validate` appearing as an observed tool
call. A plan, promise, or narration is not evidence of validation.

## Canonical Pi Prompt Sequence

The validator should not improvise validation-state prompts. In particular, do
not tell the assistant "do not validate yet" after apply, because that can cause
the assistant to choose or record a presumed-working validation path.

If the validator needs a distinct reload-continuation prompt, it must be narrow:
Record only the reload acknowledgement with `cf_project_init_record_client_reload`
and do not pass validationMode. The prompt must not ask the assistant to choose
a validation mode, skip validation, record presumed-working, or call
`cf_project_init_record_validation`. The following live-validation prompt must
then immediately request the actual Pi validation tool call.

After approval/apply and reload acknowledgement, the next validator prompt must
explicitly request live Pi validation:

```text
Continue this same Pi session after the reload acknowledgement. Validate
context7:canonical now using the Pi-visible ContextForge validation helper
cf_contextforge_pi_validate. Use the returned pi_validation_complete result as
the only proof, then call cf_project_init_record_validation with that observed
result. Do not use presumed-working, backend health, shell commands, package
CLIs, direct stdio, local file inspection, or direct Context7 backend calls.
```

## OpenCode Pass Criteria

The OpenCode evidence must show:

- the OpenCode session id, such as `ses_...`;
- the session ran from the non-ephemeral OpenCode client Docker harness against
  `/workspace`;
- `qwen3.6-a3b` was the active model;
- the first prompt or resume context exposed the project-init helper flow;
- `context7:canonical` was selected from helper-discovered choices;
- new-session reload was acknowledged with
  `cf_project_init_record_client_reload`;
- validation called the actual OpenCode-visible Context7 tool, for example
  `context7_context7-local-resolve-library-id`;
- only after that safe probe did the agent call
  `cf_project_init_record_validation`;
- final helper output contained `status=validation_recorded` and
  `project_status=initialized`.

The OpenCode gate fails if the agent calls record-validation before the safe
Context7 tool call, even if a later retry succeeds. A successful human-facing
flow cannot depend on helper rejections to teach the required sequence.

## Cross-Client Failure Conditions

Any of the following blocks human validation:

- missing stable session id;
- missing complete assistant/tool output transcript;
- ephemeral validation through `--rm`, `pi-ephemeral`, `opencode-ephemeral`, or
  a tmpfs workspace service;
- missing client-specific stale-container cleanup before launch;
- missing cleanup readback proving stale target-client containers are gone;
- missing workspace cleanup/readback proving a virgin per-test `/workspace`;
- missing idempotent reset command or fixed postcondition readback;
- reset process depends on human/agent judgment about which residue to remove;
- stale transcripts, project-init state, client config, or validation residue in
  `/workspace` at test start;
- `validation_results_insufficient`, permission-intent failures, or equivalent
  helper rejection during the supposed passing run;
- `TOOL_NOT_FOUND`, missing Context7 local CLI/module, or direct package
  fallback presented as validation;
- backend-only ContextForge health, direct bridge checks, local shell commands,
  or direct `npx` stdio calls used as target-client proof;
- final initialized/active claim without target-client-visible validation
  proof;
- pass evidence that depends on stale pre-existing initialized state instead of
  the expected use-case dialogue from the first prompt;
- any host/global Pi or OpenCode config mutation;
- any legacy/live ContextForge, production service, systemd, secret, OAuth,
  trust-token, or registry mutation.

## Verifier

Run the verifier on the captured artifacts before posting a ready/human-test
recommendation:

```sh
python3 docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py \
  --client pi \
  --evidence docker/client-harness/evidence/use-case-1/pi-session.md \
  --session-id <pi-session-id>

python3 docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py \
  --client opencode \
  --evidence docker/client-harness/evidence/use-case-1/opencode-session.md
```

The verifier is an audit gate, not the validation actor and not a repair tool.
It can reject bad evidence after a delegated dialogue run, but it cannot
replace the delegated code-assistant validator. If it fails, keep the work in
agent repair and attach the verifier output to the issue/PR.

## Human Validation Handoff

The human validation handoff must be a single PR comment titled
`Human Validation Checklist for PR #271`. It must include:

- links or paths to the passing Pi and OpenCode agent transcripts;
- validator agent ids and lease ids for both runs;
- verifier command lines and pass output for both clients;
- the exact PR head SHA;
- the human commands to rerun the same surfaces;
- known non-actions and remaining out-of-scope slices.

Do not ask for human validation from scattered issue comments or partial smoke
evidence.
