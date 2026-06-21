# Safe Client-Visible Validation Probe Catalog

Issue: #97
Open question: `oq-20260531-0001`

This catalog defines source-level acceptance rules for future ContextForge
target-client validation probes. It does not run probes, validate runtime
state, mutate clients, or approve service changes.

## Purpose

Project initialization and service onboarding must not mark a service or
client active from backend-only health, direct backend checks, skipped
validation, local shell substitutes, or presumed-working choices. A validation
claim needs target-client-visible ContextForge proof from the client surface
being claimed.

The catalog is the contract for deciding which probe semantics are safe enough
to implement later, one service at a time.

Use `docs/readiness-claim-guardrails.md` to report probe and readiness state.
Probe contracts can make a slice `source_ready`; only target-client-visible
list/call proof can support `target_client_ready`.

## Client Surfaces

| Client surface | Target-client proof must come from | Not sufficient |
| --- | --- | --- |
| Codex | Codex-visible MCP list/call proof through the project-local ContextForge helper or configured MCP surface. | ContextForge `/health`, direct backend checks, or local shell tools. |
| Pi client Docker | Pi-visible shim/helper/guidance or validation tools against the ContextForge dev Docker surface. | Codex hook banners or host Pi global state. |
| OpenCode client Docker | OpenCode-visible plugin/helper/MCP behavior against the ContextForge dev Docker surface. | Codex hook banners or host OpenCode global config. |
| Host Pi | Host Pi extension/shim readback after the separate #3 install/reload boundary is crossed. | Pi client Docker evidence or source fixture evidence alone. |

## Probe Status Classes

- `known_safe_probe`: harmless, read-only, target-client-visible semantics are
  already identified and can be implemented in a future service-specific
  validation slice.
- `conditional_probe`: a plausible safe probe exists, but credentials, cost,
  environment, target resource, or side effects must be bounded before runtime
  validation can claim success.
- `skip_until_probe_exists`: no safe target-client-visible payload is
  currently defined; validation must remain skipped or presumed-working with a
  reason.

## Catalog

| Service or surface | Status | Safe probe semantics | Forbidden substitutions |
| --- | --- | --- | --- |
| context7 | `known_safe_probe` | Target-client list-tools proof plus a small read-only documentation lookup for a harmless package or library. | Upstash/backend health, local package lookup, or direct bridge checks. |
| mentality | `known_safe_probe` | Target-client list/read proof for governance records only. | Decision writes, ledger mutation, or local file reads used as validation proof. |
| ssh-tmux | `known_safe_probe` | Target-client list-sessions or session metadata readback only. | Opening sessions, sending commands, cleanup, or shell process mutation. |
| OpenZeppelin Solidity Contracts | `known_safe_probe` | Target-client deterministic ERC-20 preview generation with constrained harmless arguments and no write/deploy target. | Treating remote availability, package docs, deployment, generated-code audit claims, or direct backend calls as target-client proof. |
| web-search | `conditional_probe` | Harmless low-cost search query only after provider credentials, rate limits, and output redaction are bounded. | Built-in web search, direct provider calls, or credential exposure. |
| Exa Search | `conditional_probe` | Harmless low-cost search query only after API-key, quota, and redaction boundaries are explicit. | Direct Exa calls outside the target client or broad internet queries without a bounded payload. |
| GitHub | `conditional_probe` | Read-only viewer, rate-limit, repository metadata, or issue metadata readback with credential scope confirmed. | Creating issues/PRs/comments, mutating labels, or using `gh` local auth as target-client proof. |
| Playwright | `conditional_probe` | Snapshot or title readback against a controlled fixture page. | Arbitrary URL browsing, unsafe code execution, screenshots of unknown pages, or browser state mutation. |
| Serena/project-scoped services | `conditional_probe` | Read-only status, tool-list, or language/profile metadata readback against the selected project instance. | Provisioning, activation, LSP writes, global config edits, or broad project scans. |
| Pi/OpenCode activation helpers | `conditional_probe` | Client-visible helper, guidance, or shim readback on the matching client surface. | Codex hook banners, host global state, or Docker evidence generalized to host installs. |
| Any unlisted service | `skip_until_probe_exists` | None until a service-specific safe payload is reviewed and tracked. | Presuming validation from backend health, local tools, or another service's probe. |

## Context7 Probe Contract

Context7 is the first known-safe probe contract. A future runtime validation
may use this contract only when the exact target client can see the
ContextForge-exposed Context7 tools.

- Required proof layers: target-client `list-tools` evidence plus one
  target-client safe `call-tool` result.
- Allowed tool names: `context7-local-resolve-library-id` and
  `context7-local-query-docs`.
- Default payload: call `context7-local-resolve-library-id` with
  `{"libraryName": "python", "query": "standard library documentation lookup"}`
  or an equivalent harmless library lookup. The current Context7 schema
  requires both `libraryName` and `query`.
- Accepted proof kinds: `target_client_safe_probe_result` or
  `pi_safe_probe_result`.
- Required successful result shape: `status: passed`,
  `target_client_visible: true`, `safe_probe_result: passed`,
  `safe_probe_id: resolve-library-id`, and at least one target-client trace
  reference.
- Forbidden substitutions: backend health, direct bridge calls, local package
  lookup, built-in web search, or direct Upstash/Context7 backend calls.

## Context7 Result Builder Boundary

Issue #101 adds an executable source-level builder for Context7 validation
result JSON. The builder is a shaping contract only: it accepts metadata from a
target-client-visible tool listing and safe call that already happened, then
returns the result shape project-init may record.

The builder does not call Context7, start clients, mutate project state, rewrite
client config, run Docker, register services, handle secrets, or prove live
runtime validation. Wrong tools, unsupported proof kinds, missing target-client
trace refs, backend-only proof, or failed probe output must produce a
non-passing result instead of a validation claim.

## Mentality Probe Contract

Mentality has a known-safe source-level probe contract only for governance
list/read proof. A future runtime validation may use this contract only when
the exact target client can see the ContextForge-exposed Mentality governance
tools.

- Required proof layers: target-client `list-tools` evidence plus one
  target-client safe `call-tool` result.
- Allowed tool names: `mentality-governance-list`,
  `mentality-governance-read`, `governance_list`, and `governance_read`.
- Default payload: call `mentality-governance-list` with
  `{"repo": "PROJECT_ROOT", "ledger": "decisions"}` or an equivalent
  harmless governance listing for the selected project root.
- Accepted proof kinds: `target_client_safe_probe_result` or
  `pi_safe_probe_result`.
- Required successful result shape: `status: passed`,
  `target_client_visible: true`, `safe_probe_result: passed`,
  `safe_probe_id: governance-list`, and at least one target-client trace
  reference.
- Forbidden substitutions: governance create, governance update, governance
  delete, local ledger file reads used as validation proof, backend health,
  direct registry checks, or direct bridge checks.

## ssh-tmux Probe Contract

ssh-tmux has a known-safe source-level probe contract only for existing
session visibility. A future runtime validation may use this contract only
when the exact target client can see the ContextForge-exposed ssh-tmux tools.

- Required proof layers: target-client `list-tools` evidence plus one
  target-client safe `call-tool` result.
- Allowed tool names: `ssh-tmux-list-sessions`,
  `ssh-tmux-get-snapshot`, `list_sessions`, and `get_snapshot`.
- Default payload: call `ssh-tmux-list-sessions` with `{}` to list existing
  sessions or return an explicit empty listing without opening or mutating
  sessions.
- Accepted proof kinds: `target_client_safe_probe_result` or
  `pi_safe_probe_result`.
- Required successful result shape: `status: passed`,
  `target_client_visible: true`, `safe_probe_result: passed`,
  `safe_probe_id: list-sessions`, and at least one target-client trace
  reference.
- Forbidden substitutions: opening sessions, sending commands or keys,
  cleanup/deletion, closing sessions, remote file reads or writes as
  validation proof, direct shell or tmux commands, backend health, or local
  process inspection.

## OpenZeppelin Solidity Contracts Probe Contract

OpenZeppelin Solidity Contracts has a known-safe source-level probe contract
only for constrained deterministic ERC-20 preview generation. A future runtime
validation may use this contract only when the exact target client can see the
ContextForge-exposed OpenZeppelin tool.

- Required proof layers: target-client `list-tools` evidence plus one
  target-client safe `call-tool` result.
- Allowed tool name: `openzeppelin-solidity-contracts-solidity-erc20`.
- Default payload: call `openzeppelin-solidity-contracts-solidity-erc20` with
  fixed harmless preview arguments: name `ContextForgePreviewToken`, symbol
  `CFP`, premint `0`, disabled mint/burn/pause/permit/callback/votes,
  disabled flash minting and cross-chain bridging, access `none`, and
  upgradeability disabled.
- Accepted proof kinds: `target_client_safe_probe_result` or
  `pi_safe_probe_result`.
- Required successful result shape: `status: passed`,
  `target_client_visible: true`, `safe_probe_result: passed`,
  `safe_probe_id: solidity-erc20-preview`, and at least one target-client
  trace reference.
- Forbidden substitutions: remote OpenZeppelin availability, package
  documentation lookup, direct backend calls, generated code treated as
  audited, deployment or security approval, file writes, project mutation,
  wallet/private-key input, chain/RPC interaction, or any secret-bearing
  input.

## Claim Rules

- Report source, backend, ContextForge, and target-client readiness with
  `docs/readiness-claim-guardrails.md`; do not collapse those layers into one
  generic validation state.
- Record `validated` only after the exact target client lists and, where safe,
  calls the intended ContextForge-visible probe.
- Record `skipped` when no safe payload exists or the target-client probe tool
  is unavailable.
- Record `presumed_working` only when the operator explicitly chooses that
  state and no target-client proof is claimed.
- Keep credentials, bearer tokens, OAuth state, trust tokens, and secret-like
  payloads out of tracked files, shell output, issue comments, and probe
  records.
- A future implementation PR must name one service, one client surface, one
  safe payload, expected output shape, negative checks, and rollback or cleanup
  expectations.

## Non-Actions

This catalog does not approve live runtime/client validation, Docker/container
start/stop/rebuild, ContextForge registry mutation, service/process/systemd
mutation, client/Pi/global config changes, hook trust/state changes,
secret/OAuth/trust-token handling, helper/project-init approve/apply/recovery
mutation, Serena provisioning, `.project/context_forge_state.json` rewrites,
destructive git operations, or retired legacy checkout mutation.
