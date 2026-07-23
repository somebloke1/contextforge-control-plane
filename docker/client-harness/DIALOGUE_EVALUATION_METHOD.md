# Code-Assistant Dialogue Evaluation Method

This is the reusable method for ContextForge client use-case evaluation. A
use-case gate should localize this method instead of rewriting it.

## Method Layer

The method layer is case-independent:

- start each attempt from an idempotently reset target-client instance and a
  virgin test workspace;
- use deterministic scripts for environment reset, command issuance, transcript
  capture, verifier invocation, and package assembly;
- run the tested client as a real assistant in a stable command-line session or
  explicit continuation chain;
- send only minimal natural prompts that a human would plausibly send;
- preserve installer equivalence: the tested assistant may receive only the
  same product surfaces a random installer would receive, plus simulated-human
  messages. Do not add harness-only, AGENTS-only, hidden, or otherwise
  non-product prompts or behavioral steering to make a tested assistant pass.
  Remediate failures through real product/helper surfaces, runner correctness,
  evaluator criteria, environment fixes, or model-adequacy decisions;
- preserve complete user, assistant, tool-call, and tool-output evidence, with
  any exported package, transcript copy, issue comment, PR comment, or summary
  redacted for passwords, bearer tokens, API keys, JWTs, private keys, and
  other credential values;
- derive separate review surfaces for visible dialogue, hidden/extension
  messages, and tool audit events;
- report stepwise and total generations for every model-dependent use case,
  including prompt, artifact path, return code, timeout, model/client identity,
  assistant-output size, event counts where available, tool-call counts, and
  total generation count;
- for live long-running dialogue attempts, limit controller-facing progress
  checks to run start, 2 minutes, 6 minutes, and terminal completion or error;
  this is orchestration cadence only and must not affect prompts or scoring;
- treat deterministic verifier output as harness and structured-evidence
  support, not semantic acceptance;
- require one delegated validator narrative and score sheet after the
  interaction completes; the evaluator assesses every turn and the whole
  dialogue from the completed evidence package, not during the live
  conversation;
- use Sol (`litellm/codex/gpt-5.6-sol`) through the sandbox OpenCode provider
  with the `high` variant for semantic evaluator runs. When a schema is
  available, include it in the evaluator instructions and validate the final
  artifact separately. Structured validation constrains artifact shape; it does
  not replace semantic judgment.
- require the evaluator narrative to identify visible dialogue quality risks
  that do not necessarily fail the use case, including placeholder-only visible
  prefaces before substantive answers, excessive internal terminology, or
  awkward hesitation that a user would experience as low-quality interaction;
- require the evaluator to judge interaction efficiency relative to the
  de facto persona overhead: whether the assistant reached the required
  outcome without avoidable detours, repeated explanations, needless approvals,
  overlong procedural narration, or premature truncation;
- classify failures as runner/package, tested-client behavior,
  environment/setup, or inconclusive;
- remediate and repeat from a fresh target-client instance until the localized
  use-case story passes.

Harness diagnostics must not print raw ContextForge env files or credential
values. If secret-file inspection is necessary, report key presence,
permissions, selected non-secret ids, and redacted values only. Use
`docker/client-harness/scripts/redact-contextforge-secrets.py` for transcript
streams or env-like output before writing them to evidence directories or
copying them into GitHub.

The method layer does not define service ids, prompt text, expected assistant
copy, tool names, or pass/fail story details. Those belong to the localization
layer.

## Localization Layer

The localization layer contains the case-unique content.

Each use case must provide a compact localization artifact with:

- use-case id and target clients;
- prompt sequence;
- clean-start fixture and target-client reset requirements;
- expected visible user-facing story, step by step;
- supporting tool evidence expected for each step;
- required generation reporting for each step and for the whole session;
- forbidden shortcuts and forbidden mutation surfaces;
- client-specific reload/new-session boundary;
- deterministic verifier command;
- scoring criteria, fatal failures, and score threshold;
- required final validator narrative template.

No truncated stories are allowed. The localization must cover setup through the
terminal expected outcome, including failure branches that should block a pass.

## Package Contract

Every runner-generated evaluation package must include both layers:

- `methodology`: a stable summary of this method;
- `use_case_localization`: the case-specific story and criteria;
- raw artifacts and derived review surfaces;
- stepwise and total generation report for all model-dependent turns;
- deterministic verifier result;
- unscored score sheet for validator completion;
- final narrative instructions.

Future use cases should add or modify only the localization artifact and runner
prompt sequence unless the reusable method itself is inadequate.

## Onboarding Process Gates

Service-onboarding process proof is a special dialogue gate. It tests whether
the ContextForge onboarding process works through actual target clients, not
whether Codex can perform source research or implementation in its own
framework. Use the repo-local `contextforge-onboarding-semantic-testing` skill
as the operational test-running skill for this gate; this method only records
the shared dialogue-evidence boundary.

For each onboarding foil, the tested assistant must be a real Pi or OpenCode
client session. Codex subagents may build runners or evaluate evidence, but
they are not valid tested-client substitutes. The tested assistant receives
only the source lead, generic onboarding guidance available through the client,
and answers from a separate simulated human responder.

The onboarding dialogue is not valid evidence if the foil already exists in
ContextForge at run start as a service, tools, virtual server, service-bound
prompt/resource, or activation-menu entry. That condition is a harness/setup
invalidity, not a semantic failure by the tested assistant.

The simulated human is a composite persona randomly composed per run across a
five-dimensional disposition space: domain knowledge, goal specificity, risk
posture, technical fluency, and interaction style. The persona remains fixed
for the whole run and answers only questions the tested assistant asks. It must
not volunteer package names, tool names, bridge commands, probe payloads,
expected implementation shape, evaluator criteria, or controller memory.
Demanding personas may be exacting, skeptical, terse, or impatient, but they
should not become cantankerous or hostile; their role is to simulate a plausible
human user still trying to complete the onboarding outcome.
The responder also receives a recorded
`determination_to_help_assistant_succeed_at_onboarding = n/20` value. Default
`n` is 15. This is a cooperation multiplier, not extra service knowledge: it
controls how hard the simulated human tries to help the tested assistant reach
successful onboarding while preserving persona knowledge, voice, and approval
boundaries. Quorum batches adapt the next batch's `n` from the first three
structural outcomes: three failures => `+2`, two failures => `+1`, one failure
=> no change, zero failures => `-1`, clamped to `1..20`.
For acceptance-matrix onboarding runs, the simulated human should be reactive:
it reads the tested assistant's previous visible output and produces the next
persona-consistent user message. Seeded prompt sequences are debug scaffolding,
not a substitute for the simulated human answering the actual interaction.
The responder may use a structured harness envelope with `message` and a
non-user-visible continuation flag so the runner can stop after a natural
conversation ending. The tested assistant receives only the message content.
For workflows that require a reload or fresh client after installation, the
runner may perform that actual session boundary after structured install/apply
success. The boundary must be recorded in the evidence package with pre/post
session ids. The simulated human may be told only the generic operator fact
that a fresh/reloaded session has been started, so any tested-assistant
awareness of the boundary arrives as ordinary user-visible dialogue rather
than hidden harness coaching.

Evaluator distinction: normal code-assistant behavior is not a defect merely
because it produces files, plans, tables, managed npm-stdio service records,
ContextForge API JSON, Docker substrate files, or other artifacts. The important
question is whether those artifacts are
assistant-authored, source-derived, within the user's approval boundary, and
then used to advance the generic ContextForge onboarding path. The preferred
implementation artifacts for the npm-stdio target are a per-service managed
npm-stdio host record and a ContextForge API JSON definition for
gateway/tool-refresh/virtual-server registration. The shared Dockerfile is a
substrate artifact, not a per-service requirement. For exact artifact paths and
JSON shape, the assistant should use
the helper-returned `install_artifact_contract` from the non-mutating
runtime/apply package rather than inventing a workspace schema. It is a failure
if the runner or controller prebuilt the
artifacts, if the assistant substitutes them for ContextForge
continuation/runtime-apply, or if the dialogue ends at local documentation
while claiming service availability.

Acceptance requires Pi and OpenCode coverage across at least three distinct
eligible semantic-test model profiles per target client. Deterministic runner
checks may package setup, commands, JSON, files, endpoints, and transcripts,
but semantic adequacy belongs to the evaluator.

## Deterministic Boundary

Deterministic evaluation of generative outputs is disallowed unless the output
is a declared structured artifact, such as JSON, and that deterministic check
is coupled with non-deterministic agent evaluation. Scripts may validate
command status, artifact existence, JSON parseability, schemas, required
fields, and other non-generative or structured contracts. Scripts may also
segment, count, index, and report assistant text and tool traces. They may
check structure, but not meaning. They must not use regexes, keyword matching,
string parsing, or other deterministic pattern matching as a test, gate, score
criterion, semantic observation, or acceptance oracle for free-form assistant
behavior.

For every model-dependent use case, the agent evaluator must receive the full
evidence package after the conversation ends or reaches its safety bound. It
must evaluate every user/assistant turn as part of a single after-action review
and also score the whole interaction. This is not live in-loop scoring and does
not require one evaluator invocation per turn.

- each step generation in sequence;
- the total generation/session report;
- raw transcript and normalized review surfaces;
- structured verifier output;
- the localized scorecard and fatal-failure criteria.
- interaction efficiency after accounting for the sampled or specified human
  persona's natural overhead.

Use Sol (`litellm/codex/gpt-5.6-sol`) through sandbox OpenCode with the `high`
variant for semantic evaluator judgment. A different role binding requires an
explicit evidence-backed reason. Capture raw evaluator events as internal
evidence when useful, but suppress raw reasoning tokens in shared or user-facing
evidence by default; publish evaluator conclusions, cited evidence, score, and
concise rationale instead.

Quality risks such as placeholder-only visible prefaces are semantic evaluator
judgments. Scripts may preserve and segment the visible assistant text for
review, but they must not decide that a free-form reply is or is not a
placeholder by matching strings, regexes, ellipses, token fragments, or other
text patterns.
