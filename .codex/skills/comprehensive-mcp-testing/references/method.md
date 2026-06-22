# Comprehensive MCP Testing Method

## Service Issue Map

The current comprehensive testing issue set is:

- #307 context7
- #308 mentality
- #309 ssh-tmux
- #310 playwright
- #311 exa-search
- #312 github
- #313 web-search
- #314 openzeppelin-solidity-contracts
- #315 serena
- #316 cross-MCP themes and global findings

Verify live issue state before relying on this map if GitHub work has progressed.

## Slice Contract

Each test slice must declare:

- `service`: ContextForge service slug.
- `client`: `pi` or `opencode`.
- `model`: one semantic-test model profile selected for the test run. Record
  the selected profile id, provider kind, model id, key env name, base URL env,
  route-preference list, and client-specific default model variables. Do not
  hardcode a provider or model name in the test package, and do not change the
  model per inference within a run.
- `model_quorum`: acceptance requires the same semantic bundle to pass on at
  least three distinct eligible semantic-test model profiles. Single-profile
  runs are model-slice evidence only; they do not satisfy the test pass gate.
- `state`: target-client virgin reset; no stale container/home/workspace state.
- `behavior_bundle`: the small user-behavior slice being explored.
- `prompt`: natural, short, sufficient user request.
- `evidence`: raw turn transcripts, command ledger, run summary, runtime readback, and evaluator narrative.
- `acceptance`: every safe function is actually attempted through the tested assistant, mutating functions are skipped or constrained with a safe dry-run/no-op rationale, and defects are triaged to the correct issue.

The phrase "through the tested assistant" means through ContextForge-installed tools visible in that client session. Direct package execution, direct stdio JSON-RPC, shell scripts, or upstream tool calls outside the client-visible ContextForge tool surface do not satisfy the slice.

For ContextForge-hosted service slices, the runner must create a scoped token for the target virtual server and pass it into the client container via the temporary client-scoped env file the wrapper reads. A checked-in `contextforge.env.example` or an empty mounted client-scoped directory is not sufficient. The raw access token must not appear in summaries, command ledgers, GitHub comments, or transcripts, and the token must be revoked after the run.

For OpenCode command-mode harness runs, pass the project root explicitly (`--dir /workspace` in the Docker harness). `cd /workspace` alone can leave command sessions behaving as if only the home config is authoritative, which masks project-local MCP installation.

When the installed MCP wrapper reads `CONTEXTFORGE_CONFIG_ENV`, install the
scoped credential at the host-side client-scoped env file mounted read-only into
the container. Do not pass the bearer token with Docker `--env-from-file` as the
primary mechanism: OpenCode project-local MCP entries may not inherit the outer
container token environment, and Docker environment persistence makes secret
cleanup weaker. Delete the host-side client-scoped env file and wrapper token
cache after the run. For OpenCode slices, capture `opencode mcp list` before
cleanup as structural evidence of whether the client saw the MCP server as
connected, failed, or absent; do not use that structural status as a substitute
for semantic evidence that the assistant actually used the tool.

## Semantic Usability Bundle Design

Short of direct user involvement, the only acceptable usability approximation
is a broad, diverse set of small semantic bundles executed through actual
target clients by dispatched runner agents. Each bundle should explore one
plausible user behavior against one service/client surface, then return a
compact evidence package for semantic evaluator review.

Do not build one large monolithic test story. Tested assistants have finite
usable context even when the configured provider/model changes, and oversized
sessions hide the point of failure. Coverage should come from many smallish
tests with fresh state, compact prompts, and explicit evidence roots.

Useful behavior dimensions include:

- ordinary successful user task that naturally requires the service;
- minimal ambiguous request where the assistant should infer the service
  without being handed tool names;
- post-install or post-reload use where the assistant should avoid stale
  guidance and unnecessary technical noise;
- recovery from a missing/failed tool without bypassing ContextForge;
- user-facing clarity when service output is large, partial, or surprising;
- constrained mutating function, dry-run, or explicit skip path;
- cross-client comparison for the same behavior in Pi and OpenCode;
- credential/auth/token failure that should be explained without exposing
  secrets or blaming the wrong layer.

When a model stops after the first safe tool call, do not immediately solve the
failure by making the prompt more technical. Classify the observed route first:
if the first tool result is ambiguous, incomplete, or not user-meaningful, that
is product-surface evidence. Prefer improving safe tool descriptions or safe
result normalization so a one-call-tolerant interaction still gives an ordinary
user useful output. If the result shape is already clear and complete, but one
model alone still fails while other models pass the same bundle, record a
model-adequacy finding and consider disabling that model from the default pool
for multi-step semantic tests.

For every bundle, record the mapping:

- behavior being explored;
- service and client surface;
- prompt given to the tested assistant;
- expected target-client-visible tool path;
- deterministic support checks allowed;
- semantic evaluator criteria;
- defect routing target if the bundle fails.

For every bundle, the evaluator must identify the actual route used. A
plausible or correct answer is not accepted if the assistant substituted
another channel, such as shell commands, web search, manual/OpenAI docs,
memory-only response, direct upstream execution, or a different installed MCP
service, when the bundle required the target ContextForge service. Treat this
as wrong-route substitution and classify it as service guidance, client
routing, or cross-MCP wrapper exposure depending on the evidence.

Keep per-slice claim boundaries crisp. Visibility, configured/readback state,
wrapper connection, safe tool call, ordinary semantic use, same-session
continuity, reload/refresh behavior, and readiness are separate claims. A
passing bundle proves only the layers it exercised and named.

The runner may help create, execute, package, and index these bundles. It must
not score the meaning of prose. Semantic evaluation belongs to the SO or a
gpt-5.5/non-Spark evaluator.

Use `docker/client-harness/scripts/run-comprehensive-mcp-model-quorum.py` for
acceptance-oriented execution. It selects or accepts at least three distinct
eligible model profiles, calls the single-profile dialogue runner once per
profile, preserves each profile's raw output, and writes a quorum summary under
`docker/client-harness/evidence/comprehensive-mcp-quorum/`. The quorum runner
only determines whether enough model-profile runs completed structurally; it
does not score semantic pass/fail.

## Three-Model Quorum

Every semantic test must pass on at least three distinct eligible model
profiles before it can be accepted. Eligible means the profile is available for
the target client, has the required provider credential, satisfies the current
minimum context-window floor, and is not excluded by the test package.

For a quorum run, keep these variables constant:

- service slug and issue;
- client type and target surface;
- reset and reload/session boundary discipline;
- prompt bundle and user-behavior story;
- allowed mutation/non-action policy;
- deterministic setup checks and evidence package shape.

Only the selected semantic-test model profile should vary. Record one
sub-evidence root per profile, then assemble a quorum packet that maps each
profile id to its raw artifacts and semantic evaluator verdict. A model that
fails is evidence, not noise; classify it before deciding whether to remediate,
rerun, or add another eligible profile. A test with one or two passing profiles
is `quorum_incomplete`, not passed.

The three-model quorum does not permit deterministic prose scoring. Each model
run still requires semantic evaluation for route use, user-facing clarity,
leakage, recovery, and behavioral acceptance.

## Model-Sized Evaluation Packets

Build evaluator packets for tested-assistant sessions as compact indexes, not
transcript dumps. Each packet should begin with a manifest that
names the use case or service slice, client, model, session ids, terminal
boundary, prompt count, generation count, raw artifact paths, verifier status,
fatal criteria, and defect-routing target.

Include a stepwise generation report for every model-dependent turn:

- prompt or user-action summary;
- raw artifact path;
- return code and timeout status;
- output size;
- target-client session id or continuation id;
- tool-call count when available;
- model/client id and token usage when available;
- whether the step is complete, interrupted, or continuation-safe.

Give the semantic evaluator targeted excerpts and exact raw-transcript
references for each disputed or decision-bearing step. Do not paste all raw
transcripts, prior UC history, or multi-service logs into one prompt. The
evaluator may request drill-down into named artifacts when the compact packet
is insufficient, but the first-pass packet should fit one focused service,
client, and behavior shape.

The evaluator narrative must walk the session step by step from its own
perspective: prompt, visible assistant reply, supporting tool evidence,
observed route, outcome, defect class, and whether the transcript is complete
enough for the claimed layer. This narrative is an additional signal for
isolating failures in the tested client, test package, runner, environment, or
evaluator instructions.

Deterministic verifiers should declare their scope in the packet, for example
`ok_scope: deterministic structure only` and
`semantic_acceptance: requires_agent_evaluation`. They may check manifest
shape, artifact existence, command status, and JSON structure, but not whether
free-form prose means the interaction passed.

## Evaluation Boundary

Allowed deterministic checks:

- process return codes and timeouts
- existence and schema of `run-summary.json`
- JSON validity for structured outputs
- command ledger completeness
- container/runtime readback
- tool inventory structure
- endpoint reachability and HTTP status classes

Disallowed deterministic checks:

- regex or string-match pass/fail over assistant prose
- pattern-matched claims that a function was semantically exercised
- treating hidden thinking/tool text as a substitute for user-visible success

Structured JSON may be checked structurally, but semantic adequacy still requires non-deterministic evaluation.

## Host-Side Validation And Dependency Gaps

Every branch/worktree used for comprehensive MCP testing must have a local
`.venv`. If it is absent, create it with `uv venv .venv` before host-side
validation. Do not leave a branch without a local environment, and do not use a
sibling checkout virtual environment as acceptance evidence.

Missing pytest is not an acceptable stopping condition for this repository.
The ordinary host-side validation fallback order is:

1. Run the focused `unittest` module or test case that covers the changed
   files.
2. Run `py_compile` for touched Python scripts and tests.
3. Run skill validation for changed skills.
4. Run Node syntax checks for touched JavaScript harness or plugin files.
5. Run the runner in the smallest no-build/dry-run mode that exercises the
   changed invocation path.

Only after those options are impossible should a dependency gap be reported as
a blocker. A valid blocker report must include:

- the current-worktree Python path that was used or missing;
- the focused commands attempted;
- why `unittest`/`py_compile`/skill validation could not cover the slice;
- the owning issue or PR where the blocker will be retired;
- the exact next remediation, such as creating `run/test-venvs/<suite>/` or
  adding a root dependency manifest.

Use the current worktree only. If `.venv` lacks a required package, install the
package into that `.venv` when it is a valuable or integral local enabler. If a
suite needs additional isolation, create an ignored isolated venv under
`run/test-venvs/<suite>/`. Do not borrow sibling checkout virtual environments
or replace executable validation with a passive PR note. The phrase "no root
dependency declaration" may explain why bootstrap is not standardized; it does
not by itself justify skipping focused validation.

## Prompt Shape

Prefer prompts like:

```text
Please use this project's documentation lookup capability to answer: In current Next.js, how should Server Actions handle authentication? Keep the answer concise and cite the documentation source you used.
```

The prompt should supply minimal natural user intent. Do not hand the tested
assistant exact low-level callable names, function suffixes, issue numbers,
expected call sequence, or anti-bypass checklists unless the behavior under
test is explicitly whether the assistant can follow user-supplied technical
tool instructions. Tool inventories, expected route maps, issue targets, and
bypass criteria belong in the evaluator packet and runner metadata, not in the
tested user's ordinary prompt.

Avoid prompts that:

- ask the assistant to meta-test a service when an ordinary user task would
  naturally require the service tools.
- list low-level helper calls to perform unless testing helper behavior.
- pre-narrate the desired conclusion.
- teach exact tool names or call order when testing natural service use.
- invite broad codebase exploration when the target is service use.
- activate every service when a single-service slice is under test.

## Bypass Evidence

A run may prove that an upstream MCP package works while still failing the ContextForge client test. Mark the run as not accepted when the assistant:

- writes a script to spawn the upstream MCP package directly.
- uses shell commands or package managers as the service invocation path.
- hand-drives JSON-RPC over stdio outside the client-visible tool interface.
- reports `target-client-visible=false` and then substitutes a direct upstream call.

Preserve those artifacts and triage them as useful isolation evidence, not as service-pass evidence.

## Failure Classification

Classify as cross-MCP (#316) when the dominant failure is:

- reload/session lifecycle
- wrapper startup, closed transport, or idle timeout
- client token/auth propagation
- noisy helper state shown to user
- target-client reset/idempotency
- semantic-model context blow-up or timeout caused by too much tool universe or prompt bulk
- runner/evidence package defect

Classify as service-specific when the dominant failure is:

- missing or wrong service tool
- upstream service unavailable or malformed
- service-specific credentials or token scope
- function schema mismatch
- service-specific guidance defect
- one service's mutating-function safety policy

When uncertain, write the finding to #316 with a link to the service issue and make the uncertainty explicit.

## Evidence Package

A complete package includes:

- `run-summary.json`
- one raw transcript per activation/test turn
- command ledger with exact client commands
- reset result and postcondition
- runtime readback
- evaluator narrative that describes the session step by step from the evaluator's perspective
- issue triage recommendation with evidence paths

Aggregate evidence packages must name exact source artifacts by slice id,
client, service, timestamp, and path. Do not use broad globs, newest-file
selection, or inferred timestamp matching as acceptance evidence for readiness
or handoff artifacts. If an aggregate report consumes prior evidence, include
the exact manifest used and let deterministic verification check manifest
completeness only, not semantic adequacy.

The runner does not decide semantic pass/fail. The evaluator narrative is part of the signal.

## Active Session Stewardship

Before starting a model-backed Pi/OpenCode slice, capture a short ownership
preflight. First identify the configured semantic profile from the env file and
client defaults. Always check active runners and slice-owned containers. Only
check local model servers, `nvidia-smi`, or `ollama ps` when that profile is
actually hosted by the local model stack.

```bash
ps -u "$USER" -o pid,stat,cmd
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Command}}'
```

For local-hosted profiles only, add:

```bash
nvidia-smi
ollama ps
```

Also read any active-slice ledger from the controlling issue comment,
controller notes, or latest `run-summary.json`. The ledger must name, at
minimum, the service, client, container, activation/test session ids, evidence
root, start time, current state, and owner. Keep it terse enough to update
often. Its purpose is not ceremony; it prevents the controller from launching a
second model-backed turn merely because the conversational context forgot the
first.

Interpretation rules:

- GPU and local model server signals are relevant only for a local-hosted
  semantic profile. Do not spend time checking `nvidia-smi`, `ollama ps`, or a
  llama server when the active profile is OpenRouter or another remote provider.
- For local-hosted profiles, GPU memory held by a local model server is not by
  itself proof of active inference. Treat nonzero `GPU-Util`, active client
  runner processes, growing transcript files, or a live command session as
  stronger evidence of an active test turn.
- For local-hosted profiles, a local model server process holding many GiB with
  `GPU-Util` near 0% is usually resident/idle model state. Do not kill it or
  declare a hung slice from memory residency alone.
- Running `cf-mcp-<service>-<client>-*` containers are slice ownership evidence.
  Reuse, inspect, or stop only containers whose names and evidence paths belong
  to the current comprehensive MCP testing loop.
- If a slice-owned container is still running, inspect the corresponding
  evidence root, command ledger, raw transcript mtimes, and runner process list
  before deciding it is stale. Prefer attaching/readback to understand the
  state over starting a duplicate session.
- If ownership is unclear, do not kill model servers or client containers
  speculatively. Record the ambiguity and ask the SO, or isolate the next test
  with a new explicit container name and evidence directory only after resource
  contention is understood.
- If a stale slice-owned container is idle, preserve its transcript/evidence
  before cleanup. Cleanup should reset by deleting the whole slice-owned
  container/home/workspace state, not by hand-calculating deltas inside it.
- If GPU utilization is pegged during a local-model profile, defer new
  model-backed launches until the active owner is identified. A controller may
  continue deterministic repo/GitHub work while waiting.

State transitions:

- `planned`: issue/package exists, no runner launched.
- `running`: runner/client command in progress or transcript still growing.
- `awaiting-evaluator`: raw evidence exists and no client generation is active.
- `stale-needs-preservation`: slice-owned container remains but no transcript
  or process progress is visible.
- `closed`: evidence preserved, token/cache cleanup recorded, and container
  reset or intentionally retained with owner.

Before fan-out, there should be no ambiguous `running` or
`stale-needs-preservation` slice for the same client/service. If there is, do
not dispatch another model-backed runner for that slice until the state is
resolved.

## Controller Discipline

Before dispatching wider runners:

1. Run at least one control slice yourself.
2. Fix runner/package defects exposed by the control slice.
3. Push the branch and record the evidence in GitHub.
4. Dispatch bounded agents only after the invocation pattern is stable.

While agents run, maintain GitHub and branch hygiene rather than idling.

## Learning Capture

At the end of every slice, record one controller learning disposition:

- `skill-update-needed`: the short operating rules should change before more agents rely on the method.
- `method-update-needed`: the detailed reference, runner invocation, or evidence package rules should change.
- `candidate-only`: the observation may matter but needs another example before becoming a rule.
- `no-method-change`: the failure belongs to product code, service config, credentials, or the tested client, not the testing method.

Make durable edits immediately when the lesson would prevent repeated bad runs. Validate the skill after edits and mention the refinement in the same GitHub evidence stream as the slice that produced it.
