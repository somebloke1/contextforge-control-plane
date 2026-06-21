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
- `model`: qwen-backed tested assistant, currently local `qwen3.6-a3b` in the harness.
- `state`: target-client virgin reset; no stale container/home/workspace state.
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

## Prompt Shape

Prefer prompts like:

```text
Use Context7 to answer this: for Next.js, resolve the library id first, then look up documentation about server actions and authentication. Do not use shell commands, package installs, web search, or direct upstream calls as substitutes. Keep the report under 20 lines with the Context7 functions used, concise results, and issue target (#307 for context7, #316 for shared wrapper/client problems).
```

Avoid prompts that:

- ask the assistant to meta-test a service when an ordinary user task would
  naturally require the service tools.
- list low-level helper calls to perform unless testing helper behavior.
- pre-narrate the desired conclusion.
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
- qwen context blow-up or timeout caused by too much tool universe or prompt bulk
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

The runner does not decide semantic pass/fail. The evaluator narrative is part of the signal.

## Active Session Stewardship

Before starting a qwen-backed Pi/OpenCode slice, capture a short ownership
preflight:

```bash
nvidia-smi
ollama ps
ps -u "$USER" -o pid,stat,cmd
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Command}}'
```

Also read any active-slice ledger from the controlling issue comment,
controller notes, or latest `run-summary.json`. The ledger must name, at
minimum, the service, client, container, activation/test session ids, evidence
root, start time, current state, and owner. Keep it terse enough to update
often. Its purpose is not ceremony; it prevents the controller from launching a
second qwen turn merely because the conversational context forgot the first.

Interpretation rules:

- GPU memory held by a local model server is not by itself proof of active
  inference. Treat nonzero `GPU-Util`, active client runner processes, growing
  transcript files, or a live command session as stronger evidence of an active
  test turn.
- A model server such as `llama-server` holding many GiB with `GPU-Util` near
  0% is usually resident/idle model state. Do not kill it or declare a hung
  slice from memory residency alone.
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
- If GPU utilization is pegged, defer new qwen-backed launches until the active
  owner is identified. A controller may continue deterministic repo/GitHub work
  while waiting.

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
not dispatch another qwen-backed runner for that slice until the state is
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
