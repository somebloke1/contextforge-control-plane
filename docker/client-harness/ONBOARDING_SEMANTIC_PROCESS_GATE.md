# Onboarding Semantic Process Gate

This gate proves the generic ContextForge onboarding process, not a single
controller-authored service artifact. It applies to each onboarding foil before
the next foil begins.

## Claim Boundary

The gate may claim only the layers it actually exercises. A source-only helper
record proves `source_ready` at most. A direct bridge probe proves
`backend_ready` at most. ContextForge registry and virtual MCP probes prove
`contextforge_ready` at most. The foil is not accepted until real target
clients prove target-client-visible behavior and a semantic evaluator accepts
the process.

The gate must satisfy installer equivalence. If a random user installs the
product, their code assistant must receive the same product surfaces the tested
assistant receives. Harness-only, AGENTS-only, hidden, or otherwise non-product
prompt additions are not valid remediation for a failing semantic run. Do not
change the tested model/profile or add behavioral steering to pass a recent
transcript. Fix the product surface, helper/tool contract, runner, evaluator,
or environment instead.

The service-onboarding how-to prompt is part of the product/helper contract
when it is fetched by the helper from
`CONTEXTFORGE_SERVICE_ONBOARDING_HOW_TO_URL` or the repo-default URL and
injected by the target client as hidden route context before onboarding tool
calls. Ordinary onboarding tool outputs should not carry the how-to text when
the client has a hidden prompt path. It must not be copied into user-visible
prose. Do not publish or upsert this how-to during ordinary onboarding tool
use.

## Roles

- Tested assistant: a real Pi or OpenCode client session launched through the
  Docker client harness.
- Simulated human responder: a separate model/persona that answers only the
  tested assistant's user-facing questions. Acceptance-matrix runs use a Pi
  gpt-5.5 authenticated simulator with `low` thinking unless the controller
  records a specific equivalent substitute; seeded or direct-provider
  responders are debug scaffolding.
- Deterministic runner: resets state, launches containers, records commands,
  captures transcripts, enforces role separation, and packages evidence.
- Semantic evaluator: a non-Spark evaluator that reviews evidence and decides
  process adequacy. Prefer Codex CLI `exec` with `gpt-5.5`,
  `-c model_reasoning_effort="high"`, and `--output-schema <FILE>` for
  evaluator runs. The runner does not decide semantic pass/fail.

Codex subagents may review or evaluate evidence, but they are not the tested
assistant for this gate. A Codex-only onboarding run proves nothing about Pi or
OpenCode onboarding behavior.

## Veil Rule

The tested assistant receives only:

- the source lead, such as an upstream URL;
- generic ContextForge onboarding guidance and helper surfaces available in
  the target client;
- answers from the simulated human responder.

The tested assistant must not receive service-specific implementation facts
from the controller, runner, evaluator, prior branches, parent workspace,
existing service homes, expected package names, expected tool names, expected
bridge commands, expected probe payloads, or hidden pass/fail criteria.

The development ContextForge surface must also be clean for the selected foil
at the beginning of an acceptance run. If the foil already exists as an MCP
service, service tool set, virtual server, service-bound prompt, service-bound
resource, or client activation-menu entry, the onboarding run is invalid
because the tested assistant can start from already-onboarded state. Runners
must fail closed unless structured ContextForge registry readback and
activation-menu readback both prove the foil is absent. Preparing the dev
surface is a separate explicit step; use the foil cleanup/readback utility with
`--apply` only when deliberately resetting the development surface before a
new acceptance attempt.

The runner may know evaluator criteria and evidence routing, but that
information must stay outside prompts sent to the tested assistant.

Controller-facing live progress reporting should occur only at run start, at
2 minutes, at 6 minutes, and at terminal completion or error. This avoids
turn-by-turn orchestration chatter while preserving enough operator visibility.
It is not a prompt, scoring, or behavior rule for the tested assistant or the
simulated human.

Docker-isolated target clients do not own the host Docker daemon or host
compose-file path locality. When onboarding uses the shared `npm-stdio-host`,
the runner must provide a host-side runtime/apply proxy so the tested
assistant can use the shipped helper surface while runtime mutation occurs in
the correct host harness context. This proxy must not carry service-specific
facts, expected answers, or behavioral coaching.
After a structured runtime/apply result proves
`service_onboarding_runtime_applied`, the runner may start a fresh or reloaded
target-client session before the next tested-assistant turn. That boundary is
part of the required operator workflow and must be recorded as evidence with
pre/post session ids. It may be exposed to the simulated human only as the
generic fact that a fresh/reloaded session has been started; it must not convey
service-specific package names, tool names, commands, probes, evaluator
criteria, or controller conclusions.

The gate must not confuse ordinary code-assistant artifact work with a runner
shortcut. A tested assistant may, when the simulated human approves it, draft
workspace-local onboarding dossiers, source-evidence tables, managed npm-stdio
service records, ContextForge API JSON definitions, or other auditable planning
artifacts as part of normal assistant behavior. For the current npm-stdio
target, the preferred implementation artifacts are a per-service managed
npm-stdio host record plus a ContextForge API JSON definition for
gateway/tool-refresh/virtual-server registration and rollback targets. A
Dockerfile belongs to the reusable npm-stdio host substrate, not to every
onboarded npm MCP service. Those
artifacts are valid interaction evidence only if they are produced by the
tested assistant inside the target-client session from source-derived facts.
When exact artifact paths or JSON shape are needed, they should come from the
ContextForge helper's non-mutating runtime/apply package
`install_artifact_contract`, not from invented `.contextforge/services` paths
or blank-workspace convention guessing.
The helper may require a standard field set and refuse incomplete install or
register attempts. That is not coaching. It is a product contract forcing the
tested assistant to research and supply the npm package, transport, env vars,
arguments, tool schemas, and prompt-library content. If a runtime attempt
fails, the helper may return stage-labeled error information, but it must not
tell the tested assistant the service-specific fix.
The preferred interface is just-in-time prompting through a non-mutating draft
surface: the tested assistant submits one bounded source-derived slice, the
helper records accepted fields, identifies missing fields, returns the next
required slice, and writes or returns the growing project-local draft payload.
The final runtime/apply package preview remains strict and may be built only
after the draft has enough source-derived fields; runtime execution remains a
separate approval-bound mutation.
For many-tool services, the accepted structured schema input may be a
`toolSchemaRecords` array: one source-derived record per tool with name,
description, input schema, and optional source anchor. This is equivalent to
the canonical `tool_schemas` object after helper normalization, but plain
summaries, tool-name arrays, or controller-filled schema content are still
insufficient.
If the target client cannot reliably pass large nested schema objects as tool
arguments, it may instead write a complete project-local JSON payload and pass
`structured_payload_path`/`structuredPayloadPath` to the helper. That is valid
only when the tested assistant authored the file from source-derived facts
inside the target-client session; the controller or runner must not prebuild
the payload or populate it with hidden expected answers.
Runtime/apply evidence must also prove idempotency at the operation boundary:
failed install/register attempts clean up partial hosted-service,
ContextForge, bridge, and prompt-library state before returning the error;
repeat attempts must not accumulate duplicate state.
They are not acceptance by themselves. The runner or controller must not
prebuild them, feed them to the tested assistant, or treat their existence as a
deterministic package proof. The accepted path still has to return to
ContextForge continuation/runtime-apply, reload/new-session handling,
target-client-visible tools, and a safe service call.

## Composite Simulated Human Persona Sampling

Before each run, the agent invoking the runner must randomly compose a
simulated human persona across a five-dimensional disposition space and keep
that persona stable for the whole dialogue:

- domain knowledge: ignorant, generally technical, or MCP/ContextForge-aware;
- goal specificity: vague, outcome-oriented, or detailed requirements;
- risk posture: trusting, cautious, or strict about approval and rollback;
- technical fluency: nontechnical, command-comfortable, or architecture-aware;
- interaction style: terse, cooperative, or demanding.

The sampled dimensions compose one persona vector. The simulator prompt should
define the human's situation, goal, knowledge, and voice, then let the
model-backed human run. Do not turn the simulated human into an idealized
compliance actor with a rule stack. If that human is demanding, overconfident,
imprecise, or pushes for a shortcut, that is part of the behavior space the
product must survive unless the runner itself leaked hidden controller facts.
Demanding does not mean cantankerous or hostile: the simulated human can be
strict, skeptical, terse, or impatient while remaining constructive and
practically oriented toward completing the onboarding goal.
The simulator must honor the persona's ignorance boundary. It may react to the
tested assistant's visible proposals, approve or decline bounded steps, ask for
evidence, and require rollback clarity, but it must not inject latent model
expertise, protocol recipes, service-specific commands, or alternate
non-ContextForge routes that the persona would not know.
The runner also records
`determination_to_help_assistant_succeed_at_onboarding = n/20`, starting at
15/20 by default. This is not a sixth random persona dimension; it is a
simulated-human cooperation multiplier. At 15/20 or higher, the responder
should be relentlessly constructive about helping the assistant reach
successful ContextForge onboarding while still honoring the persona's knowledge
and approval boundaries. Across three-model quorum batches, all runs in the
same batch use the same `n`; the next batch adapts from the first three
structural onboarding outcomes: all three fail => `n += 2`; two fail =>
`n += 1`; one fails => no change; all three succeed => `n -= 1`, clamped to
`1..20`.

Acceptance-matrix runs should use a reactive simulated-human responder that
reads the tested assistant's previous visible output and produces the next
persona-consistent user message. Seeded followup prompts are useful for runner
smoke/debug checks, but they are weaker evidence because they do not prove that
the simulated human answered the actual questions asked.
The responder may return a structured harness envelope containing the next
human message plus a non-user-visible continuation flag. The runner may stop
capture when that flag says the human would naturally end the conversation; the
tested assistant receives only the human message, never the control metadata.

## Minimum Run Matrix

For each foil:

- clients: `pi`, `opencode`;
- semantic-test model profiles: at least three distinct eligible profiles per
  client;
- user persona coverage: the matrix must include at least one low-knowledge
  user, one higher-knowledge user, and at least two distinct risk postures;
- execution: isolated target-client home, workspace, scoped credentials,
  session id, and evidence root per client/model/persona run.

The same foil can fail in one persona and pass in another. Acceptance requires
the declared run matrix to pass semantically or for failures to be remediated
and rerun from fresh state.

Each client/model/persona run must budget enough interaction for a real
onboarding conversation without coaching or truncation. The proper length is
persona- and outcome-dependent and should become more determinate as the
overall onboarding system evolves. All else equal, the interaction should be
optimal: no gratuitous turns, no loss of required outcome. A seeded runner may
use a generous default turn budget, but acceptance is never decided by a fixed
turn count.
The default capture safety bounds are 32 tested-assistant turns or 600 seconds
of dialogue wall time. Reaching either bound stops capture and must be recorded
as evidence for the evaluator; it does not by itself prove pass or fail.
The evaluator must separately judge efficiency after treating the sampled
persona's natural overhead as given: did the tested assistant reach the outcome
with appropriate pace and without avoidable detours, repeated explanations,
needless approvals, overlong internal narration, or premature truncation?

## End-To-End Story

Each tested assistant must progress through the generic process:

1. Receive only the source lead from the simulated human.
2. Ask clarifying questions if needed.
3. Conduct source research through generic onboarding support.
4. Present key implementation decisions methodically to the simulated human.
5. Produce or request approval for the bounded implementation plan, including
   any assistant-authored managed npm-stdio service record and ContextForge API
   JSON artifact if that is the natural approved intermediate step.
6. Implement or drive the approved dev-surface onboarding work when the gate
   grants that surface.
7. Prove runtime/backend behavior on the declared development surface.
8. Register or bind through the declared ContextForge development surface.
9. Start a fresh/reloaded client session when needed.
10. Demonstrate target-client-visible service listing and a safe service call.
11. Report results with clear claim boundaries and residual risks.

If the tested assistant cannot proceed because the generic support lacks a
capability, the run fails usefully. The controller must encode the missing
generic support before rerunning or advancing to the next foil.

## Deterministic Runner Duties

The runner must:

- reset target-client container, home, workspace, scoped token files, and
  evidence root idempotently;
- preflight the declared ContextForge development surface for preexisting foil
  exposure before dialogue begins, including structured registry readback for
  MCP service, tools, virtual server, prompts, and resources plus
  available-capabilities readback for activation-menu exposure; stop as invalid
  if the foil is already visible;
- preflight each selected semantic-test model profile against the current
  provider using a representative prompt and output-token envelope before
  Docker build or target-client dialogue. Provider authentication, route,
  rate, credit, prompt-token, or output-token failures are setup failures, not
  ContextForge product failures. Stop and package that evidence rather than
  consuming a full semantic dialogue. Do not reduce the preflight envelope
  merely to make a profile pass unless the profile's eligibility and
  acceptance scope are explicitly changed;
- choose one semantic-test model profile for the full run;
- start non-ephemeral Pi/OpenCode containers;
- maintain distinct session ids for tested assistant and simulated human;
- record every prompt, answer, command, model profile, return code, timeout,
  transcript path, tool event summary, and generated artifact path;
- record the configured turn budget and actual prompt/response count so the
  semantic evaluator can judge whether the interaction was truncated,
  over-guided, or unnecessarily long;
- record the configured dialogue wall-time budget, elapsed time, and stop
  reason;
- record whether the simulated-human responder was model-backed/reactive or
  seeded/debug, including a redacted responder model profile when model-backed;
- package source helper records, runtime readbacks, registration readbacks,
  target-client transcripts, and cleanup evidence;
- declare `semantic_acceptance: requires_non_spark_evaluator`;
- avoid deterministic scoring of free-form prose.

Allowed deterministic checks are command status, JSON structure, artifact
existence, endpoint reachability, scoped-token cleanup, and target-client
container reset postconditions. Meaning, route adequacy, user-facing clarity,
coaching leakage, recovery quality, and process success belong to the semantic
evaluator. Deterministic tooling must not evaluate generated assistant meaning
through string or regex matching.
The runner must not evaluate generated assistant meaning through string or
regex matching.

## Evaluator Criteria

Use Codex CLI `exec` with `gpt-5.5`,
`-c model_reasoning_effort="high"`, and `--output-schema <FILE>` for semantic
evaluator judgment by default. Use a lower thinking level or a different
surface only when the controller records an explicit evidence-backed reason.
The semantic evaluator performs high-dimensional judgment over meaning, route
adequacy, claim boundaries, leakage, recovery, and efficiency; it is not a
deterministic transcript scorer. Structured output constrains the evaluator
artifact shape, not the semantic judgment. Capture raw evaluator events as
internal evidence when useful, but suppress raw thinking tokens in shared or
user-facing evidence by default and report conclusions plus concise rationale
instead. Rendering raw thinking tokens is an explicit design decision that must
be surface-labeled and justified.

The evaluator must judge:

- every user/assistant turn after the interaction is complete or has reached
  its safety bound, without evaluator calls during the live conversation and
  without one evaluator invocation per turn;

- whether the tested assistant stayed behind the veil;
- whether the simulated human identity and knowledge context were supplied
  without leaking hidden controller facts;
- whether implementation decisions were surfaced methodically;
- whether the assistant used generic ContextForge onboarding support rather
  than controller memory or direct upstream shortcuts;
- whether runtime, ContextForge, target-client-visible, and verified claims
  were kept separate;
- whether Pi/OpenCode actually saw and safely used the onboarded service;
- whether reload or new-session boundaries were handled clearly;
- whether user-facing copy was concise and non-noisy;
- whether the interaction was efficient relative to the persona and task
  complexity, with no gratuitous turns and no omitted required outcome;
- whether any failure is a runner defect,
  tested-client behavior defect, generic-support gap, model inadequacy,
  service-specific issue, or environment/setup defect.

## Non-Acceptance Examples

Do not accept:

- a Codex subagent onboarding the service outside Pi/OpenCode;
- direct shell or Python calls to the upstream MCP package as a substitute for
  target-client-visible service use;
- a backend or registry proof without Pi/OpenCode list-tools plus safe call;
- a coached prompt that supplies package names, tool names, bridge commands, or
  expected payloads;
- deterministic transcript keyword checks as semantic acceptance;
- a run that starts from an existing service home or prior Time-specific
  artifacts.
- a run that starts with the foil already present in ContextForge as a service,
  tools, virtual server, service-bound prompts/resources, or activation-menu
  entry.
