# Use Case 1 End-to-End Agent Gate

This gate applies to PR #271 and the first cumulative #247 service slice:
`context7:canonical` through Pi client Docker, OpenCode client Docker, and
Codex client Docker.

Use Case 1 is a localization of the reusable dialogue-evaluation method in
`docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`. That method owns the
general principles: idempotent reset, real client dialogue, minimal natural
prompts, raw evidence preservation, deterministic verifier as an audit gate,
and delegated semantic scoring. This file owns only the Use Case 1
localization: target clients, prompt sequence, expected project-init story,
forbidden shortcuts, scoring criteria, and handoff requirements.

Human acceptance must not be requested until this gate has passed with full
code-assistant dialogue evidence for every target client in scope. Use the project
skill `.codex/skills/code-assistant-dialogue-validation/SKILL.md` for that
lease. Source tests, direct helper calls, backend probes, smoke scripts,
evidence verifiers, and hand-shaped payloads are useful diagnostics,
but they are not substitutes for a delegated agent evaluating the real client
dialogue.

The preferred Use Case 1 runner is:

```sh
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client pi
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client opencode
python3 docker/client-harness/scripts/run-use-case-1-dialogue.py --client codex
```

The runner owns deterministic setup, minimal CLI prompt issuance, raw evidence
capture, verifier invocation, and evaluation-package assembly. A delegated
validator still owns the semantic judgment: read the package, score the
interaction, and decide whether the natural human-agent exchange actually met
the use-case story.

## Localization Summary

Use Case 1 unique requirements:

- target clients: Pi client Docker, OpenCode client Docker, and Codex client
  Docker;
- selected service: `context7:canonical`;
- prompt sequence: `hello`, `1`, `approve`;
- expected user-facing story: service list, context7 selection, installation
  package/approval request, scoped install/apply, installed result, and
  reload/new-session-required boundary;
- terminal state: selected ContextForge tools are installed project-locally and
  the assistant stops after telling the user reload or a new session is
  required before the tools register;
- forbidden UC1 shortcuts: post-install validation, Context7 probing, reload
  acknowledgement recording, shell/package/backend substitutes, direct
  `.project/context_forge_state.json` mutation, and host/global config or
  registry mutation.

## Required Order

1. Run the existing source/unit/static checks.
2. Rebuild any changed client harness images.
3. Delegate a Pi dialogue-evaluation lease to a dev agent. That agent should
   run `docker/client-harness/scripts/run-use-case-1-dialogue.py --client pi`
   unless the controller names a newer runner. The agent must evaluate the
   returned package, not invent a different prompt story.
4. Delegate an OpenCode dialogue-evaluation lease to a dev agent. That agent
   should run
   `docker/client-harness/scripts/run-use-case-1-dialogue.py --client opencode`
   unless the controller names a newer runner. The agent must evaluate the
   returned package, not invent a different prompt story.
5. Delegate a Codex dialogue-evaluation lease to a dev agent, or when subagent
   auth is unavailable, run a contained OAuth-backed Codex Docker evaluator
   against the generated package and record that fallback explicitly. The
   runner command is
   `docker/client-harness/scripts/run-use-case-1-dialogue.py --client codex`.
   Codex evaluation must use the authenticated Docker image, OAuth/ChatGPT
   subscription auth, no API-key env vars, and model `gpt-5.4-mini`.
6. Verify that all runner packages include raw transcripts, verifier JSON,
   per-step criteria, scoring weights, fatal failure criteria, and a validator
   narrative.
7. If any required outcome fails, remediate the source/harness/prompt defect,
   rerun the affected source checks, rebuild changed images, rerun the full
   affected agent session from the command line, and rerun the verifier.
8. Repeat testing -> remediation -> testing until all target clients pass every
   expected outcome in observed agent interaction evidence.
9. Only after all prior steps pass, ask for human acceptance.

If any target client fails, the branch remains in agent repair. Do not ask the
operator to discover the next failure by hand.

This is a loop, not a one-shot checklist. A partial pass followed by a later
agent failure resets the gate to remediation. A helper rejection that the agent
eventually recovers from is still a failed gate when the required user-facing
interaction was supposed to be clean. Human testing is an acceptance check after
delegated dialogue-agent evidence passes; it is not the mechanism for
discovering ordinary integration failures.

## What Counts As End-to-End Agent Evidence

Each client needs one continuous command-line agent session with a stable
session id or explicit continuation chain. The runner may issue the fixed
minimal prompts, but the evidence must show the real model-driven assistant
behavior, not only helper calls, shell probes, or scripted command output. A
delegated dev agent must then evaluate the captured dialogue as a human-facing
interaction.

The evaluator's prompts are part of the test surface. The passing run must use
minimal, natural prompts that a user would plausibly send, such as `hello`,
`1`, or `approve`. Do not coach the tested
assistant with helper tool names, internal payload keys, approval challenge
mechanics, required tool ordering, or evaluator pass/fail criteria. A coached
retry can be useful for diagnosis after a failure, but it is not passing
dialogue evidence.

No truncated use-case test stories are allowed. Use Case 1 evaluation must be
based on the full specified story from clean harness setup through final
readback: setup assumptions, prompt sequence, assistant decision points, tool
ordering, observed outputs, reload/new-session behavior, failure branches,
forbidden shortcuts, timing expectations, scoring/rating dimensions if used,
and pass/fail criteria. A partial happy path, summary, or clipped transcript is
not enough to rate or pass the interaction.

This target-client dialogue evaluation is semantic acceptance work. Do not assign the
full multi-turn Pi/OpenCode dialogue run to Spark. Spark can extract transcript
evidence, map fixtures, or make bounded mechanical patches, but the validator
that conducts the LM-engaging client session must be a non-Spark model suited
to long stateful interaction.

Raw client JSON streams can be large. Passing evidence may keep the full raw
stream in a companion artifact and use targeted readbacks to extract live
challenge ids, plan digests, and job ids, but the full
story must remain reconstructable from preserved evidence. Targeted readbacks
are an evidence-indexing method, not permission to truncate the story or guess
values from patterns.

Do not invert deterministic and semantic responsibilities. Evidence
preservation, target-client reset, workspace fixture creation, minimal prompt
issuance, postcondition readback, verifier invocation, and package assembly
must be scripted/idempotent. The delegated language-model validator is
responsible for the high-dimensional semantic work: judging whether the full
user-facing interaction satisfied the use-case story from real prompt/reply
evidence and supporting tool traces.
The validator must not use pattern matching or residue-delta inference as a
substitute for either deterministic reset or semantic interaction judgment.

For Docker client harness evaluation, the preferred reset primitive is
`python3 docker/client-harness/scripts/reset-client-harness-state.py --client <pi|opencode|codex-cli> --reset-home-volume`.
The script preserves prior workspace artifacts under
`docker/client-harness/evidence/use-case-1/prior/`, resets only the selected
client's container/home state, recreates the allowlisted `.gitkeep` workspace
fixture, and prints fixed JSON postcondition readback. Use a different reset
only when a lease names a newer deterministic command with the same or stronger
postconditions.

Host-side source checks must run in an environment created for this worktree
and test framework. If the current worktree lacks dependencies such as `mcp` or
`mcpgateway`, create an isolated ignored venv for that test framework or test
run, for example under `run/test-venvs/`, and install the minimum declared or
observed dependencies needed to run the suite. Do not borrow
`/home/dgk/workspace/cf-controlplane/.venv` or any sibling checkout runtime to
convert the check into a pass. Container-local harness runtimes such as
`/opt/contextforge-helper-venv` and `/opt/contextforge-wrapper-venv` remain
valid when they are part of the Docker client image under test.

Each evaluation attempt starts from a disposable fresh target-client instance
and a virgin test workspace. Prior transcripts and forensic artifacts must be
moved or copied into
`docker/client-harness/evidence/` before the next run; they must not remain in
`docker/client-harness/workspace/` as part of the next run's start state. The
older shorthand still applies: Each evaluation attempt starts from a virgin test workspace.
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
only inside a single evaluation run so reload, resume, and new-session behavior
can be observed against surviving state. There is no value in carrying
project-init residue from one test attempt into the next.

For compatibility with older validator leases: remove stale containers only for the client type being
tested, but treat that as one step inside the idempotent target-client reset,
not as sufficient proof of cleanliness by itself.

The gate fails if the dialogue uses `--rm`, `pi-ephemeral`,
`opencode-ephemeral`, a tmpfs workspace service, or any launch mode where the
container and `/workspace` state are discarded between CLI calls inside the
same test run. The gate also fails if `/workspace` starts with stale
project-init state, client config, old transcripts, or prior evaluation residue.
The gate also fails if host-side verification is credited after substituting a
sibling checkout `.venv` for a missing current-worktree runtime. Create a
worktree-local isolated test venv instead.
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
- evidence that user prompts were minimal/natural and did not coach internal
  helper tools, payload keys, challenge/digest echo mechanics, exact tool order,
  or evaluator criteria;
- evaluator-package criteria for each anticipated interaction step, including
  expected natural prompt, expected user-facing reply, supporting tool evidence,
  failure conditions, scoring points, fatal failure rules, and verifier result;
- the validator's final pre-submission narrative, written step by step from the
  validator's own perspective, with evidence references and explicit
  classification of runner/package defects versus tested-client behavior
  defects;
- service discovery/menu presentation for `context7:canonical`;
- service selection using the helper-discovered service id;
- scoped approval and apply of only project-local state/config;
- explicit assistant report that the selected ContextForge tools are installed;
- explicit assistant instruction that reload or a new session is required before
  the tools register;
- final initialized/installed readback;
- explicit non-actions for host/global client config, legacy/live
  ContextForge, secrets, trust, systemd, and production registry state.
- raw tool events when available and an observed tool-output index using
  literal `Tool:` markers that references only transcript entries. Tool traces
  are evaluator evidence; the tested assistant's normal visible prose should
  not be laden with internal call details.
- Pi HTML exports are acceptable evidence only when the embedded
  `session-data` payload is decoded and audited as ordered user, assistant,
  tool-call, and tool-result events.
- targeted readbacks for every live challenge id, plan digest, and job id copied
  into a later prompt.

Captured summaries are not enough. The evidence must contain the observed
assistant messages, tool calls, and tool outputs that prove the agent followed
the flow.

The expected outcome is not merely that a final helper field says initialized.
The observed agent interaction must complete the use case cleanly: correct
service menu, correct selection, scoped approval, installation package applied,
and a clear final message that the tools are installed and a reload/new session
is required before they register. The flow ends there.

The deterministic runner/verifier status is necessary but not sufficient for
acceptance. A delegated validator must complete the score sheet and narrative
before submitting a pass/fail recommendation. The narrative is especially
important when isolating whether a failure belongs to the package/runner, the
tested client, or the surrounding environment.

A delegated dialogue-evaluation lease is incomplete until every required
user-facing step in the full story has appeared in the captured transcript in
order, with supporting tool traces available for audit. The validator stops at
the installed/reload-required message. If
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
- final assistant output says the tools are installed and `/reload` is required
  before they register.

The Pi gate fails if the agent uses shell substitutes such as
`python3 -m context7_*`, `which context7-*`, `npx @upstash/context7-mcp`, direct
backend probes, direct generated Context7 service tools, local file inspection,
or direct `.project/context_forge_state.json` mutation as part of project init.

## Minimal Natural Prompt Sequence

The validator should not improvise post-install prompts by leaking the
implementation contract. Do not ask the assistant to continue after apply during
a passing run.

For Use Case 1, a suitable uncoached prompt skeleton is:

```text
hello
1
approve
```

The passing run ends when apply succeeds and the assistant tells the user to
start a new session or reload before the tools register.

## OpenCode Pass Criteria

The OpenCode evidence must show:

- the OpenCode session id, such as `ses_...`;
- the session ran from the non-ephemeral OpenCode client Docker harness against
  `/workspace`;
- `qwen3.6-a3b` was the active model;
- the first prompt or resume context exposed the project-init helper flow;
- `context7:canonical` was selected from helper-discovered choices;
- final assistant output says the tools are installed and a new OpenCode session
  from the project root is required before they register.

The OpenCode gate fails if the agent asks the user to continue after reporting
the installed/new-session-required result.

## Cross-Client Failure Conditions

Any of the following blocks human acceptance:

- missing stable session id;
- missing complete assistant/tool output transcript;
- ephemeral dialogue through `--rm`, `pi-ephemeral`, `opencode-ephemeral`, or
  a tmpfs workspace service;
- missing client-specific stale-container cleanup before launch;
- missing cleanup readback proving stale target-client containers are gone;
- missing workspace cleanup/readback proving a virgin per-test `/workspace`;
- missing idempotent reset command or fixed postcondition readback;
- reset process depends on human/agent judgment about which residue to remove;
- validator user prompts coach the tested assistant with helper tool names,
  approval key echo instructions, internal payload schemas, expected tool order, or
  evaluator pass/fail criteria;
- stale transcripts, project-init state, client config, or prior-run residue in
  `/workspace` at test start;
- permission-intent failures or equivalent
  helper rejection during the supposed passing run;
- `TOOL_NOT_FOUND`, missing Context7 local CLI/module, or direct package
  fallback used as part of project init;
- backend-only ContextForge health, direct bridge checks, local shell commands,
  or direct `npx` stdio calls used as part of project init;
- any extra project-init tool call after apply succeeds;
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
  --metadata docker/client-harness/evidence/use-case-1/pi-metadata.json \
  --session-id <pi-session-id>

python3 docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py \
  --client opencode \
  --evidence docker/client-harness/evidence/use-case-1/opencode-session.md \
  --metadata docker/client-harness/evidence/use-case-1/opencode-metadata.json
```

The verifier is an audit gate, not the dialogue actor and not a repair tool.
It can reject structurally bad evidence after a delegated dialogue run, but it
cannot judge the meaning of free-form generated prose and cannot replace the
delegated code-assistant validator. If it fails, keep the work in agent repair
and attach the verifier output to the issue/PR.

## Human Acceptance Handoff

The human acceptance handoff must be a single PR comment titled
`Human Acceptance Checklist for PR #271`. It must include:

- links or paths to the passing Pi and OpenCode agent transcripts;
- validator agent ids and lease ids for both runs;
- verifier command lines and pass output for both clients;
- the exact PR head SHA;
- the human commands to rerun the same surfaces;
- known non-actions and remaining out-of-scope slices.

Do not ask for human acceptance from scattered issue comments or partial smoke
evidence.
