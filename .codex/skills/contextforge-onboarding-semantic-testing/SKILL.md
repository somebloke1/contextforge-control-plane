---
name: contextforge-onboarding-semantic-testing
description: Run ContextForge MCP service-onboarding semantic process gates through real Pi and OpenCode target-client sessions. Use when Codex needs to design, run, evaluate, or refine source-lead-only onboarding proofs where a tested assistant starts from an upstream URL or lead, a simulated human responder answers questions, model-profile quorum evidence is required, and Codex subagents must not substitute for target-client behavior.
---

# ContextForge Onboarding Semantic Testing

## Overview

Use this skill for onboarding-process proof, not for already-registered MCP
service-use proof. The object under test is whether generic ContextForge
onboarding support can take a new source lead to target-client-visible service
use through real Pi and OpenCode assistants.
This skill is not for already-registered MCP service-use proof.

For ordinary service-use proof after a service is already registered, use
`comprehensive-mcp-testing`. For generic use-case dialogue evaluation, use
`code-assistant-dialogue-validation`.

## Required Artifacts

Before acting, read the relevant local artifacts:

- `docker/client-harness/ONBOARDING_SEMANTIC_PROCESS_GATE.md`
- `docker/client-harness/onboarding-semantic-process-scenarios.json`
- `docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`
- `docs/initiatives/contextforge-control-plane/service-onboarding-helper.md`

Load only additional runner code, issue text, or evidence files needed for the
current foil.

## Claim Boundary

Do not claim a foil is accepted because Codex, a shell script, or a backend
probe succeeded. Acceptance requires evidence that real Pi and real OpenCode
target-client assistants progressed through the generic onboarding process and
then saw and safely used the onboarded service through ContextForge.

Semantic onboarding tests must satisfy installer equivalence. If a random user
installs the product, their Pi or OpenCode assistant must receive the same
product surfaces used by the tested assistant. Do not add harness-only,
AGENTS-only, hidden, or otherwise non-product prompts, steering, behavioral
prohibitions, or model/profile changes to make a tested assistant avoid a
recent failure. Improve only shipped helper/tool output, shipped product
guidance, runner correctness, evaluator criteria, or real product capability.

If the foil is already present in the target ContextForge surface before the
run starts, the run is invalid. "Present" includes an MCP service, service
tools, virtual server, service-bound prompt, service-bound resource, or any
client activation-menu entry for the foil. Require structured registry
readback for service/tool/server/prompt/resource absence and activation-menu
readback for client-visible exposure before real dialogue begins.

Codex subagents may build runners, package evidence, review GitHub state, or
evaluate transcripts. They are never the tested assistant for this gate.

The generic onboarding how-to prompt is a product/helper surface, not a harness
cheat prompt. The helper should download it from
`CONTEXTFORGE_SERVICE_ONBOARDING_HOW_TO_URL` or the repo-default URL and the
client should inject it as hidden/internal route context before onboarding
tool calls. Keep ordinary onboarding tool outputs free of the how-to text
where the client has a hidden prompt path. Do not publish or upsert this
how-to on every service-onboarding use, and do not show it as user-visible
prose.

Current onboarding target: first support npm-published stdio MCP services
through one shared Docker-hosted `npm-stdio-host` runtime. For such services,
the helper should guide assistants toward a managed npm-stdio service record
and a ContextForge API registration JSON plan, not a bespoke Dockerfile per
service. The stock ContextForge API registers reachable endpoints; it does not
itself install npm packages. The shared host owns npm install/run/bridge CRUD,
while the helper transparently manages ContextForge gateway/tool-refresh/
virtual-server registration.

The helper may require a complete standard field set and fail closed when it is
missing: confirmed npm package, registry type, version policy, stdio transport,
package/runtime arguments, env vars, secret names, tool schemas, abstract
prompt, and lazy-loaded detail prompts. The helper should prompt/remind the
tested assistant to research those fields, but must not research or infer them
for the tested assistant. On runtime failure, the helper returns the failed
stage plus observed/sanitized error only; it must not prescribe the
service-specific correction.
The intended helper ergonomics are just-in-time prompting and cumulative draft
composition: a non-mutating draft/update tool asks for one bounded slice,
records accepted source-derived fields, returns missing fields and the next
required slice, and writes or returns the project-local structured payload path
to use for final package preview. Do not force a tested assistant to satisfy
the entire onboarding contract in one tool call when the draft surface is
available.
For large tool sets, `toolSchemaRecords` is an allowed structured transport
shape: one source-derived record per tool with name, description, input schema,
and optional source anchor. It is not a semantic shortcut and does not permit
plain summaries, tool-name arrays, or controller-provided schema content.
When a target client struggles to pass large nested schemas as tool arguments,
the tested assistant may write a complete project-local JSON payload containing
the same source-derived fields and call the helper with
`structured_payload_path`/`structuredPayloadPath`. The helper may parse that
file because the assistant authored it inside the target-client session; the
controller must not prebuild or inject it.
Runtime/apply operations must be idempotent and transactional. If installation
or registration fails, the executor must uninstall/remove any partial hosted
npm service, bridge endpoint, ContextForge gateway/tool/server association, and
prompt-library content before returning the error. Evidence must record
rollback actions and residual cleanup risk.

## Role Split

- Controller: owns branch/GitHub state, runner package readiness, remediation,
  and final acceptance.
- Tested assistant: real Pi or OpenCode client session launched through the
  Docker client harness.
- Simulated human responder: separate persona that answers only the tested
  assistant's user-facing questions. Acceptance-matrix runs use a Pi
  gpt-5.5 authenticated simulator with `low` thinking unless the controller
  records a specific equivalent substitute; seeded or direct-provider
  responders are debug scaffolding.
- Deterministic runner: resets state, launches clients, selects one model
  profile per run, records transcripts, and packages evidence.
- Semantic evaluator: non-Spark model or SO that judges meaning, route
  adequacy, claim boundaries, and process success. Prefer Codex CLI `exec`
  with `gpt-5.5`, `-c model_reasoning_effort="high"`, and
  `--output-schema <FILE>` for evaluator runs. Use Pi as evaluator only as a
  fallback when Codex CLI is unavailable or auth-blocked.

## Veil Rule

The tested assistant receives only the source lead, generic ContextForge
onboarding guidance available in the target client, and answers from the
simulated human. Do not provide service-specific package names, tool names,
bridge commands, probe payloads, expected implementation shape, controller
memory, evaluator criteria, or prior-run conclusions.

The runner and evaluator may know the criteria, but that knowledge must not
enter prompts sent to the tested assistant.

Acceptance-matrix runs should use a reactive simulated-human responder that
reads the tested assistant's previous visible output and produces the next
persona-consistent user message. Seeded prompt sequences are acceptable for
runner smoke/debug checks, but they are not equivalent to a model-backed
responder answering the actual questions asked.
The responder may return a structured harness envelope containing the human
message plus a non-user-visible continuation flag. The runner may use that
flag to stop capture when the simulated human would naturally end the
conversation; the tested assistant receives only the human message content.

## Persona Sampling

For each client/model run, randomly compose one simulated-human persona across
these five dimensions and keep it stable for the whole dialogue:

- `domain_knowledge`
- `goal_specificity`
- `risk_posture`
- `technical_fluency`
- `interaction_style`

Record the seed and vector. The simulator prompt should define the human's
situation, goal, knowledge, and voice, then let the model-backed human run.
Do not tune the simulated human into an idealized compliance actor. Imperfect,
demanding, imprecise, or overconfident user behavior is part of the product
behavior space unless the runner itself leaked hidden controller facts.
Demanding does not mean cantankerous: the simulated human may be strict,
skeptical, terse, or impatient, but must remain constructive and practically
oriented toward completing the onboarding goal.
The simulator must also honor the persona's ignorance boundary. It may react
to visible assistant proposals, approve, decline, ask for evidence, or ask for
rollback boundaries, but it must not inject latent model expertise, protocol
recipes, service-specific commands, or alternate non-ContextForge routes that
the persona would not know.
In addition to the five persona dimensions, each run records
`determination_to_help_assistant_succeed_at_onboarding = n/20`. Default `n` is
15. At 15/20 or above the simulated human should be relentlessly, constructively
helpful toward successful onboarding: answer questions from visible context,
approve bounded safe next steps when appropriate, request concrete corrections
instead of derailing, and keep the interaction moving while honoring persona
knowledge and approval boundaries.
For three-model quorum batches, all runs in a batch use the same `n`. The next
batch adapts from the first three structural onboarding outcomes: if all three
fail, `n += 2`; if two fail, `n += 1`; if one fails, no change; if all three
succeed, `n -= 1`. Clamp `n` to `1..20`. This is simulated-human behavior
control only; it is not sent as hidden guidance to the tested assistant.

## Run Matrix

For each onboarding foil, acceptance requires:

- target clients: `pi` and `opencode`;
- at least three distinct eligible semantic-test model profiles per target
  client;
- isolated home, workspace, scoped credentials, container name, session id, and
  evidence root per client/model/persona run;
- at least one low-knowledge persona, one higher-knowledge persona, and two
  distinct risk postures across the accepted matrix.
- enough interaction budget for the persona and outcome, without treating a
  fixed turn count as acceptance. The semantic evaluator judges whether the
  dialogue was truncated, over-guided, unnecessarily long, or complete with no
  loss of required outcome.
- default individual-run safety bounds are 32 tested-assistant turns or 600
  seconds of dialogue wall time. These bounds stop capture; they are not a
  semantic pass/fail oracle.
- semantic evaluation of interaction efficiency, taking the sampled persona's
  natural overhead as given and judging whether the assistant avoided needless
  detours, repeated explanations, premature approvals, overlong procedural
  narration, and premature truncation.

Do not move to the next foil until the current foil passes this matrix or the
controller explicitly records a blocked state with owner and remediation path.

## Runner Requirements

Use the onboarding semantic-process runners, not the comprehensive
already-registered-service runners:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docker/client-harness/scripts/run-onboarding-semantic-process-quorum.py \
  --client pi \
  --foil time \
  --timeout 420 \
  --no-build
```

Use `run-onboarding-semantic-process-dialogue.py` only for one
client/model/persona slice, debugging, or a runner-invoking agent that supplies
persona-consistent prompts with `--prompt` or `--prompt-file`.

The runner may deterministically verify reset postconditions, command status,
JSON structure, artifact existence, endpoint reachability, transcript capture,
credential cleanup, and preexisting-foil absence in structured ContextForge
readbacks. It must not evaluate generated assistant meaning through string
matching, regex matching, keyword matching, or transcript pattern scoring.
After a structured `service_onboarding_runtime_applied` result, the runner may
start a fresh or reloaded target-client session for the next tested-assistant
turn. This is required orchestration evidence, not tested-assistant coaching:
record the pre/post session ids and boundary reason, and expose at most the
generic operator fact that a fresh/reloaded session has been started to the
simulated human responder. Do not add service-specific facts, expected tool
names, commands, or evaluator criteria through this boundary.

When target clients are Docker-isolated, do not expect the tested Pi/OpenCode
container to own host Docker Compose paths or the host Docker daemon. Runtime
apply for the shared `npm-stdio-host` must run through the configured
host-side runtime/apply proxy while preserving the same helper/tool surface to
the tested assistant. This is environment restoration, not a prompt cheat: do
not add service-specific facts or behavioral steering through the proxy.

The runner package should emit a manifest-first evidence bundle with:

- foil id and source lead;
- target client, model profile, provider route preference, persona seed/vector,
  and session ids;
- command ledger and reset/readback evidence;
- stepwise and total generation reports;
- raw transcript paths and targeted excerpts;
- structured runtime/ContextForge/target-client readbacks;
- evaluator score sheet and final narrative prompt for one after-action
  judgment covering every turn and the whole dialogue.

Before launching live target-client dialogue, run a semantic-model provider
availability preflight for each selected profile using a representative prompt
and output-token envelope for the current harness. This is deterministic setup
evidence only. If a profile fails for provider authentication, rate, credit,
prompt-token, output-token, or route limits, classify the run as
environment/setup model-profile unavailable and stop before Docker build or
target-client launch. Do not report that as a ContextForge onboarding product
failure, and do not lower the envelope merely to pass unless the profile's
eligibility and the reduced acceptance scope are explicitly changed.

During live semantic runs, controller-facing progress checks should be limited
to run start, the 2-minute mark, the 6-minute mark, and terminal completion or
error. Do not add ad hoc live polling updates unless the run itself fails or
requires immediate intervention. This cadence is a human-facing orchestration
discipline only; it must not alter prompts sent to the tested assistant or
simulated human.

If a deterministic check fails before real dialogue begins, report setup
failure. Do not rewrite the story into a scripted substitute.

## Evaluation

Use a non-Spark semantic evaluator for pass/fail judgment. The default
semantic evaluator surface is Codex CLI `exec` with `gpt-5.5`,
`-c model_reasoning_effort="high"`, and `--output-schema <FILE>` for the
scorecard artifact. Use a lower thinking level only with an explicit
evidence-backed reason. Structured output constrains the evaluator artifact
shape; it does not replace semantic judgment. Capture raw evaluator events as
internal evidence when useful, but suppress raw thinking tokens in shared or
user-facing evidence by default and report conclusions plus concise rationale
instead. Any decision to render raw thinking tokens must be explicit,
surface-labeled, and justified by the controller. The evaluator receives the
full evidence package after the interaction completes or hits its safety bound.
It must assess every turn and the whole interaction in one after-action review;
do not call an evaluator inside the live conversation loop or spend one
evaluator invocation per turn. The evaluator must judge whether the tested
assistant:

- stayed behind the veil;
- asked suitable questions or proceeded from source research when questions
  were unnecessary;
- surfaced key implementation decisions methodically;
- used generic ContextForge onboarding support rather than controller memory or
  direct upstream shortcuts;
- kept source, backend, ContextForge registry, target-client-visible, and
  accepted claims separate;
- handled reload or new-session boundaries clearly;
- produced clear, low-noise user-facing copy;
- demonstrated target-client-visible service listing and a safe service call;
- moved efficiently relative to persona, task complexity, and required outcome;
- identified residual risks honestly.

Classify failures as runner defect, tested-client behavior defect,
generic-support gap, model inadequacy, service-specific defect, or
environment/setup defect. Route each finding to the correct issue or
remediation branch.

## Refinement

When a failure reveals a reusable lesson about source-lead packaging, runner
isolation, model adequacy, evidence shape, product continuation guidance, or
evaluator criteria, patch this skill or the referenced gate artifact before
wider fan-out. Do not bury durable method lessons only in issue comments.
