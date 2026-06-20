# Holistic Orchestrated Pipeline Spec

## Purpose

This specification defines the controller-owned SuperLoop for testing,
remediating, and accepting all ContextForge client use cases, beginning with Use
Case 1 and continuing through Use Cases `2..n`. The loop is designed to run
without required user steps inside the test/remediation cycle. User input is
reserved for true product decisions, approvals outside the allowed test
surface, or scope changes.

The pipeline treats scripts, verifiers, workers, and dialogue validators as
evidence producers. The controller owns acceptance.

## Symbolic Control Form

Legend:

- `SO` = SuperLoop controller.
- `UC[n]` = use case `n`.
- `Q` = ordered use-case queue.
- `P[n]` = durable localized package for `UC[n]`.
- `M` = reusable method layer.
- `L[n]` = lease for one bounded worker/evaluator task.
- `D` = deterministic harness work.
- `J` = semantic judgment work by a non-Spark dialogue evaluator.
- `G` = generation report: stepwise and total model-dependent outputs,
  counts, timings, and artifact refs captured by scripts but not scored by
  scripts.
- `E` = evidence: logs, transcripts, verifier output, scorecards, reports.
- `R` = remediation patch or package adjustment.
- `V` = verification command or observed runtime probe.
- `✓` = controller acceptance after evidence integration.
- `⊥` = must remain distinct, not substitutable.
- `▣` = recurrent loop.

Compressed invariant:

```text
SO ▣:
  Q=[UC1..UCn] →
  for UC[i]:
    materialize(P[i] ⋈ M) →
    for client∈P[i].targets:
      D(clean_env, clean_client, clean_workspace, runner, verifier, G) →
      J(real_dialogue_E, G, scorecard, narrative) →
      classify({package|runner|tested_client|implementation|env|inconclusive}) →
      reflect(learning, requirement_refinement, behavior_improvement) →
      if pass(client): continue
      else R → V → rerun(client from virgin state)
    if all clients pass: ✓UC[i] → promote regressions → next UC

Invariants:
  scripts/verifiers/workers produce E ⊥ ✓;
  deterministic reset/venv/container/workspace setup ⊥ LM inference;
  deterministic pass/fail ⊥ generative-output quality judgment;
  semantic dialogue judgment ⊥ pattern matching;
  Spark ⊥ multi-turn client-readiness judgment;
  sibling .venv ⊥ valid current-worktree evidence;
  residue-delta cleanup ⊥ idempotent virgin reset.
```

Fidelity: the symbolic form is lossless relative to control flow, authority
boundaries, evidence requirements, and reset/testing invariants. The sections
below expand it into executable policy.

## Directory Structure

Tracked durable artifacts:

- `holistic_orchestrated_pipeline_spec.md`: this controller specification.
- `docs/use-cases/`: durable use-case localization packages, scorecards,
  standard narratives, and acceptance summaries.
- `docker/client-harness/use-cases/`: durable client-harness use-case runner,
  verifier, fixture, and transcript-normalization assets when they are
  promoted from a specific case.
- Existing Case 1 artifacts remain valid while migration to the generalized
  structure is incremental:
  - `docker/client-harness/DIALOGUE_EVALUATION_METHOD.md`
  - `docker/client-harness/USE_CASE_1_E2E_GATE.md`
  - `docker/client-harness/scripts/run-use-case-1-dialogue.py`
  - `docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py`

Ignored runtime assembly:

- `run/holistic-orchestrator/queue/`: queue snapshots and controller state.
- `run/holistic-orchestrator/packages/`: generated per-attempt evaluation
  packages before promotion.
- `run/holistic-orchestrator/leases/`: active and retired worker lease records.
- `run/holistic-orchestrator/attempts/`: attempt-local logs, transcripts,
  normalized tool indexes, and verifier outputs.
- `run/holistic-orchestrator/reports/`: evaluator narratives and controller
  integration reports.
- `run/holistic-orchestrator/venvs/`: isolated worktree-local test venvs.
- Existing `run/test-venvs/` remains acceptable for suite-specific venvs.

## Use-Case Scheduling

The use-case set is not an arbitrary serial checklist. Treat `UC1..UCn` as a
dependency-aware priority queue. Numeric order is the default presentation
order, not a substitute for controller judgment.

The controller schedules work by:

1. hard dependency: a use case cannot be accepted before the substrate it
   requires has passing evidence;
2. least-dependent-first ordering: among viable candidates, exercise the
   smallest lower-layer user story before the stories that depend on it;
   climb from bootstrap, to initialized-state recognition, to capability
   summary, to concrete activated-service use, to higher-order workflows;
3. shared blast radius: failures in reset discipline, venv policy,
   initialized-state recognition, client continuation, or ContextForge route
   discovery outrank narrow feature cases because they can invalidate many
   downstream attempts;
4. information value: when two cases share dependencies, run the one that most
   quickly distinguishes package, harness, client, and implementation defects;
5. remediation locality: prefer a case whose failure can be remediated in the
   smallest coherent subsystem before expanding to broader suites;
6. regression protection: after a shared-surface remediation, rerun the minimum
   already-accepted cases needed to prove that the fix did not regress their
   accepted boundary.

Current ordering interpretation:

- `UC1` is the bootstrap boundary for project-local activation. It must pass
  before ordinary initialized-project cases are accepted.
- `UC2` and `UC3` both exercise initialized-project normal-use recognition.
  They should be used as shared substrate checks for availability/capability
  guidance, not treated as unrelated serial tickets.
- `UC4` exercises the same initialized-project substrate plus a real
  ContextForge-served read-only service route. It is high priority whenever a
  service-route defect is suspected, because the defect can affect any later
  normal-use case that depends on an activated MCP service.
- Later use cases should be inserted by dependency and blast radius, not merely
  appended by number. A case that validates a shared service route or reset
  invariant may run before a narrower later-numbered case, while preserving
  acceptance dependencies.

For each dequeued use case, the controller must first assemble or refresh the
localized package before running acceptance loops.

Required `P[n]` package contents:

- use-case id, title, scope, and target clients;
- full specified story from virgin setup through terminal boundary;
- minimal natural prompt sequence;
- expected user-visible assistant replies;
- allowed supporting tool evidence;
- forbidden shortcuts and forbidden prompt coaching;
- deterministic setup contract;
- venv/dependency contract;
- non-ephemeral client/container contract;
- transcript capture and normalization contract;
- stepwise and total generation-report contract for every model-dependent
  prompt or continuation;
- verifier command and expected JSON shape, if a verifier exists;
- scorecard with per-step criteria and fatal failure criteria;
- standard narrative template for evaluator reports;
- remediation routing table;
- acceptance commands and regression tests.

No package may contain a truncated happy path. If a use case is underspecified,
the first loop task is package completion, not client acceptance.

## Reusable Method Layer

The method layer is stable across all use cases:

1. Preserve any prior evidence before reset.
2. Create or reuse an isolated current-worktree venv for the suite/use case.
3. Install only the minimum declared or observed dependencies needed by that
   suite.
4. Reset the target client through an idempotent command with fixed
   postconditions.
5. Reset the harness workspace to a virgin allowlisted state.
6. Start a fresh non-ephemeral target-client container or session.
7. Run the localized minimal natural prompts.
8. Wait long enough for local model responses, at least 90 seconds when needed.
9. Capture raw transcript, normalized transcript, tool index, stdout/stderr,
   timing, session id, client id, model, container id, and reset evidence.
10. Produce a generation report for each model-dependent step and for the full
    session. The report must include artifact refs, prompts, return codes,
    timeouts, observed event counts where available, assistant-output byte or
    character counts, tool-call counts, timing if available, model/client
    identity, and total generation count.
11. Run deterministic verifiers against captured evidence only for harness,
    environment, reset, artifact, command, and structured non-generative facts.
12. Delegate semantic judgment to a suitable dialogue evaluator.
13. Classify failures.
14. Reflect on learning surfaced by the attempt.
15. Remediate.
16. Rerun from a virgin target-client state.
17. Accept only after all client targets pass from clean starts.

## Reflective Learning

The queue is defined, but the behavior and requirements are expected to improve
as evidence accumulates. At every use-case loop boundary, the controller must
ask whether the attempt revealed a better requirement, prompt shape, DTO shape,
reset invariant, scoring criterion, skill instruction, or issue decomposition.

Do not ignore good ideas merely because they were not in the initial package.
Classify each idea before continuing:

- `incorporate_now`: the idea corrects a defect, prevents false acceptance, or
  improves the current use case without broadening it beyond its purpose;
- `promote_regression`: the idea belongs to an accepted lower-layer behavior
  and requires targeted reruns;
- `defer_with_owner`: the idea is real but belongs to a later use case, issue,
  PR, or roadmap item;
- `reject_with_rationale`: the idea is interesting but conflicts with current
  scope, idempotency, safety, or user-facing simplicity.

Reflection is not permission to churn. Make the smallest coherent improvement
that advances the actual ordinary user behavior. Preserve the distinction
between learned requirement refinement and opportunistic refactoring.

#287 is the current cross-client projection example of this rule. Treat it as
an architectural invariant and queue-shaping constraint, not as a dialogue use
case. It binds claims about project service graph, project-scoped service
instances, target-client projection, target-client visibility, reload state,
and target-client proof. It does not interrupt a per-client use case such as
UC11 when that use case uses explicitly pre-aligned target-client fixtures and
makes only target-client-scoped claims. If #286 or #285 later changes
cross-client disparity/readback or alignment behavior, rerun targeted UC9/UC10
regressions with disparity/alignment fixtures before using those behaviors in
UC12, UC14, or readiness handoff claims.

## Deterministic Responsibilities

The deterministic layer must be handled by scripts or direct commands, not by
language-model inference:

- evidence preservation;
- container and volume reset for only the target client under test;
- workspace reset and allowlist readback;
- venv creation under the current worktree;
- dependency installation into that venv;
- command invocation;
- transcript capture;
- JSON normalization;
- verifier execution;
- fixed pass/fail checks that do not require semantic judgment.

Deterministic reset must be idempotent. Re-running the reset must converge on
the same clean postcondition. A person or agent deciding which residue to remove
is not an acceptable reset mechanism.

Deterministic evaluation of generative outputs is disallowed unless the output
is a declared structured artifact such as JSON and the deterministic evaluation
is coupled with non-deterministic agent evaluation. Scripts may capture,
segment, count, index, and report model-generated text, tool-call traces, and
assistant replies. They may validate structured contracts such as JSON
parseability, schemas, required fields, command status, and artifact presence.
They may check structure, but not meaning. They must not assign semantic
pass/fail status, semantic observations, score criteria, or readiness claims to
free-form assistant behavior through matched strings, regexes, keywords, string
parsing, or other pattern-matching substitutes for model judgment.

No test, gate, score criterion, or acceptance claim may use matched strings or
regex over generated prose as its oracle. Pattern matching may be used only for
non-gating extraction, indexing, redaction, or navigation, and any resulting
semantic claim still belongs to the agent evaluator. The only exception is
declared structured model output such as JSON: deterministic code may verify
parseability, schema shape, required fields, and enum/value structure, but that
structural check must be paired with non-deterministic evaluator review. Any
model-dependent use-case acceptance package must give the agent evaluator both
stepwise generation reports and the total session generation report, and the
evaluator must score the generation quality against the localized criteria
before controller acceptance.

## Semantic Responsibilities

Language-model agents are used for high-dimensional judgment:

- evaluating whether the target assistant behaved like the intended user-facing
  interaction;
- scoring every model-dependent generation step and the total interaction from
  the runner-provided generation report;
- identifying whether prompts were too coached;
- distinguishing visible assistant behavior from hidden/tool evidence;
- writing a step-by-step narrative from real evidence;
- classifying failures as package, runner, tested-client, implementation,
  environment, or inconclusive defects;
- recommending remediation scope.

Semantic evaluators must not mutate code, decide final acceptance, or turn
coached diagnostic retries into passing evidence unless their lease explicitly
allows a bounded implementation task.

## Venv Policy

Every source or host-side suite must run in a current-worktree runtime.

Allowed:

- `.venv/bin/python` when it exists and imports the required dependencies;
- `run/test-venvs/<suite>/bin/python`;
- `run/holistic-orchestrator/venvs/<use-case>/<suite>/bin/python`;
- container-local harness runtimes such as `/opt/contextforge-helper-venv` when
  they are part of the Docker client image being tested.

Forbidden for acceptance evidence:

- borrowing `/home/dgk/workspace/cf-controlplane/.venv` or another sibling
  checkout runtime to make a test pass;
- reporting a missing dependency as blocked when an isolated worktree-local venv
  can be created;
- installing acceptance dependencies into an unrelated global runtime.

If a dependency is missing, create an isolated ignored venv for the specific
framework or suite, install the minimum dependencies, rerun, and record the
commands.

## Client Harness Policy

Each attempt starts from a virgin target-client state:

- preserve previous evidence first;
- remove stale containers only for the target client under test;
- reset only that target client's home/session volume when the package requires
  a fully clean client;
- reset `/workspace` to the package-defined virgin fixture;
- prove cleanup by fixed readback;
- launch a fresh non-ephemeral client container or session;
- preserve state only inside that single attempt so continuation/reload/new
  session behavior can be observed.

Never use `--rm`, `pi-ephemeral`, `opencode-ephemeral`, tmpfs workspace
services, or any mode that discards state between CLI calls within the same
attempt when the use case requires continuation.

## Prompt Policy

The localized prompt sequence must be minimal and natural. It should express
ordinary user intent and avoid revealing the evaluator's internal expectations.

Forbidden in passing prompts:

- helper tool names;
- expected JSON keys;
- challenge id or plan digest mechanics;
- exact internal tool order;
- evaluator pass/fail criteria;
- instructions to avoid known failures;
- instructions to use a workaround.

Coached diagnostic retries may be used after a failure to isolate root cause,
but they are diagnostic evidence, not acceptance evidence.

## Agent Model Policy

Use Spark only for bounded extraction, mapping, metadata audits, and tiny
mechanical patches. Spark must not own multi-turn LM-engaging client dialogue
evaluation or final readiness judgment.

Use stronger semantic models for:

- dialogue evaluation;
- architecture and prompt/guidance repair;
- final acceptance;
- cross-use-case risk assessment.

Every delegated task requires a lease with scope, allowed files/systems/tools,
forbidden actions, expected artifacts, required evidence, and stop condition.
Worker output is evidence, not acceptance.

## Failure Taxonomy

Each failed attempt is classified into exactly one primary class, with secondary
notes allowed:

- `package_defect`: localized story, criteria, expected result, or prompt
  sequence is incomplete, stale, or wrong.
- `runner_defect`: deterministic runner, reset, capture, timeout, or package
  assembly failed.
- `verifier_defect`: verifier flags the wrong thing or misses required evidence.
- `tested_client_defect`: Pi/OpenCode/Codex/Gemini did not surface or follow the
  required interaction under minimal prompts.
- `implementation_defect`: project code, helper flow, prompt, schema, plugin,
  shim, or harness implementation is wrong.
- `environment_defect`: Docker, dependency, venv, image, or local service setup
  is broken in a reproducible way.
- `inconclusive`: evidence is insufficient to classify honestly.

Remediation targets the primary class, then the use case is rerun from a virgin
state.

## Acceptance Standard

A use case is accepted only when every required target client passes from a
virgin start and the controller integrates:

- source/unit checks in current-worktree runtimes;
- runner output;
- verifier output;
- raw transcript;
- normalized transcript/tool index;
- semantic evaluator scorecard;
- semantic evaluator narrative;
- remediation history;
- residual risk with an owner and retirement condition, if any.

The controller must not accept evidence that depends on stale client state,
sibling venvs, pattern matching in place of semantic judgment, or language-model
guessing in place of deterministic reset.

## Use Case 1 Starting Point

Use Case 1 is the initial queue item. Its current intended terminal boundary:

1. The assistant presents the available ContextForge service list.
2. The user selects a service with a minimal natural response, e.g. `1`.
3. The assistant presents the installation package or approval request.
4. The user approves with a minimal natural response, e.g. `approve`.
5. The helper-owned installation applies.
6. The assistant says the selected ContextForge tools are installed and a new
   session or reload is required for the tools to register.
7. The flow ends. No post-install validation, service probing, reload
   interrogation, or low-level secret/key challenge is part of Use Case 1.

Known immediate work at loop entry:

- the broader project-init workflow suite now runs in an isolated venv but still
  contains stale validation-era failures;
- residual references to validation/reload-before-validation must be removed or
  rewritten where they conflict with the install-only Use Case 1 boundary;
- Case 1 must be rerun for each required target client from a clean harness
  state after remediation.

## SuperLoop Entry Algorithm

At each controller turn:

1. Read this specification.
2. Read active goal state.
3. Inspect repo status and current branch.
4. Inspect current use-case package and latest evidence.
5. If package incomplete, complete package before testing.
6. If deterministic harness incomplete, build or repair it before semantic
   evaluation.
7. If source tests fail, classify and remediate before claiming client pass.
8. If runner/verifier fails, classify and remediate.
9. If dialogue fails, classify and remediate.
10. Rerun only after resetting to virgin target-client state.
11. Accept current client only after evidence is complete.
12. Accept current use case only after all required clients pass.
13. Promote regression tests and durable package updates.
14. Dequeue the next use case.

The loop continues until all use cases in `Q` have controller-accepted evidence.
