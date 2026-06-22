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

## Composite Simulated Human Persona Sampling

Before each run, the agent invoking the runner must randomly compose a
simulated human persona across a five-dimensional disposition space and keep
that persona stable for the whole dialogue:

- domain knowledge: ignorant, generally technical, or MCP/ContextForge-aware;
- goal specificity: vague, outcome-oriented, or detailed requirements;
- risk posture: trusting, cautious, or strict about approval and rollback;
- technical fluency: nontechnical, command-comfortable, or architecture-aware;
- interaction style: terse, cooperative, or demanding.

The sampled dimensions compose one persona vector. That vector defines what the
responder may know and how it answers.
For example, an ignorant but strict user may provide only the URL and insist
that the assistant avoid global mutation; an architecture-aware user may state
preferences for stock ContextForge mechanisms and rollback boundaries when
asked. Persona answers must be natural and bounded. They may answer a question,
decline if the persona would not know, or ask the assistant to decide from
research. They must not volunteer low-level facts the tested assistant did not
ask for.

Acceptance-matrix runs should use a reactive simulated-human responder that
reads the tested assistant's previous visible output and produces the next
persona-consistent user message. Seeded followup prompts are useful for runner
smoke/debug checks, but they are weaker evidence because they do not prove that
the simulated human answered the actual questions asked.

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
5. Produce or request approval for the bounded implementation plan.
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
- choose one semantic-test model profile for the full run;
- start non-ephemeral Pi/OpenCode containers;
- maintain distinct session ids for tested assistant and simulated human;
- record every prompt, answer, command, model profile, return code, timeout,
  transcript path, tool event summary, and generated artifact path;
- record the configured turn budget and actual prompt/response count so the
  semantic evaluator can judge whether the interaction was truncated,
  over-guided, or unnecessarily long;
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

- whether the tested assistant stayed behind the veil;
- whether the simulated human answered consistently with its persona;
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
- whether any failure is a runner defect, simulated-human defect,
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
