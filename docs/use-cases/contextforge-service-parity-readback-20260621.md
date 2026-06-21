# ContextForge Service Parity Readback - 2026-06-21

Issue: #284.

Scope: read-only authenticated inventory of the local host ContextForge gateway
on `127.0.0.1:4444`, plus auth-boundary confirmation for the separate Docker
gateway on `127.0.0.1:4445`.

Operator update: the 4444 gateway is scheduled for decommissioning. Treat this
readback as a legacy/source-of-truth baseline for migration, not as an
indefinite operating target. The durable target is to make the successor
surface, currently represented by 4445, explicitly authenticated, inventoried,
and reconciled before 4444 is retired.

## Evidence

- 4444 full sanitized JSON:
  `generated/contextforge-284-full-pagination-readback-1782008501.local.json`
- 4444 tag analysis:
  `generated/contextforge-284-guidance-tag-analysis-1782008501.local.json`
- 4445 authenticated sanitized JSON:
  `generated/contextforge-284-4445-authenticated-readback-20260621T023120Z.local.json`
- 4445 authenticated summary:
  `generated/contextforge-284-4445-authenticated-summary-20260621T023120Z.local.md`
- 4445 Docker migration dry-run plan:
  `generated/contextforge-284-docker-migration-plan-20260621.local.json`
- 4445 Docker migration apply dry-run:
  `generated/contextforge-284-docker-migration-apply-dry-run-20260621.local.json`
- 4445 Docker migration safe-service apply:
  `generated/contextforge-284-docker-migration-apply-safe-services-20260621.local.json`
- 4445 Docker guidance dry-run/apply artifacts:
  `generated/contextforge-284-4445-guidance-safe-services-dry-run-20260621.local.json`,
  `generated/contextforge-284-4445-guidance-safe-services-apply-20260621.local.json`,
  and
  `generated/contextforge-284-4445-guidance-openzeppelin-retag-20260621.local.json`
- 4445 post-guidance readback and migration plan:
  `generated/contextforge-284-4445-post-guidance-readback-20260621.local.json`
  and
  `generated/contextforge-284-docker-migration-plan-post-guidance-20260621.local.json`
- 4445 Docker upstream reachability probe:
  `generated/contextforge-284-docker-upstream-reachability-20260621.local.json`
- 4445 boundary-guard no-op apply proof:
  `generated/contextforge-284-blocked-apply-guard-20260621.local.json`
- Token values were used only in memory and were not written to the artifacts.
- The initial readbacks and dry-runs performed no registry, service, prompt,
  resource, tool, or server mutation. The safe-service apply intentionally
  mutated only the Docker successor gateway on `127.0.0.1:4445` for services
  classified as non-blocked in the Docker migration plan.

## Host Gateway `127.0.0.1:4444`

Authenticated full-list readback with `limit=1000` returned:

| Endpoint | Count |
| --- | ---: |
| `/servers` | 9 |
| `/tools` | 104 |
| `/prompts` | 83 |
| `/resources` | 84 |

Server association readback returned:

| Server | Tools | Prompts | Resources |
| --- | ---: | ---: | ---: |
| `context7_local_server` | 2 | 2 | 2 |
| `exa_search_server` | 3 | 3 | 3 |
| `github_server` | 26 | 26 | 26 |
| `mentality_server` | 5 | 5 | 5 |
| `openzeppelin_solidity_contracts_server` | 8 | 8 | 8 |
| `playwright_server` | 23 | 23 | 23 |
| `serena_cf_controlplane_d46fe58a2a20_server` | 22 | 1 | 1 |
| `ssh_tmux_server` | 9 | 9 | 9 |
| `web_search_server` | 5 | 5 | 5 |

The canonical shared service set is present:

- `context7`
- `exa-search`
- `github`
- `mentality`
- `openzeppelin-solidity-contracts`
- `playwright`
- `ssh-tmux`
- `web-search`

The ninth server is the project-scoped Serena instance for this repository.

## Guidance Parity

`scripts/register_tool_guidance.py` currently defines 81 source tool-guidance
prompt/resource entries across the canonical services.

The first tag-analysis artifact counted 81 `tool-guidance` prompt records and
81 `tool-guidance` resource records by tag bucket. The later Docker migration
planner performs a stricter source-keyed comparison against the 81 tool names
currently defined by `scripts/register_tool_guidance.py` and found:

- 80 prompt records with a source-defined canonical tool tag.
- 80 resource records with a source-defined canonical tool tag.
- `openzeppelin-solidity-contracts-solidity-stablecoin` is missing as a
  canonical tool tag on both its 4444 prompt and resource records; those records
  carry `tool-guidance` plus the service tag only.
- No 4445 prompt or resource guidance records are present.

This means 4444 remains the legacy migration baseline, but the 4445 successor
should repair this guidance association defect rather than replicate it.

The raw URI comparison initially shows GitHub and web-search URI differences
because registered resources use upstream underscore names such as
`github://tools/add_issue_comment`, while a naive current-script comparison
without upstream `originalName` derives hyphenated forms such as
`github://tools/add-issue-comment`. The authoritative parity comparison for
this readback is the `tool-guidance` tag keyed to the canonical ContextForge
tool name.

## Docker Gateway `127.0.0.1:4445`

Using the 4444 bearer token against 4445 returned `401` for:

- `/servers`
- `/tools`
- `/prompts`
- `/resources`

This confirms the two gateways are separate authenticated surfaces.

After the operator clarified that 4444 is scheduled for decommissioning, the
controller ran an authenticated 4445 readback using the ignored Docker harness
admin env at `docker/contextforge-harness/env/contextforge.env`. The access
token was not recorded. Full-list readback with `limit=1000` returned:

| Endpoint | Count |
| --- | ---: |
| `/servers` | 2 |
| `/tools` | 7 |
| `/prompts` | 0 |
| `/resources` | 0 |

Server association readback returned:

| Server | Tools | Prompts | Resources |
| --- | ---: | ---: | ---: |
| `context7_local_server` | 2 | 0 | 0 |
| `mentality_dev_docker_server` | 5 | 0 | 0 |

Compared with the 4444 migration baseline, 4445 is missing eight of the nine
4444 servers, 102 of 104 4444 tools, all 83 4444 prompts, and all 84 4444
resources. The current 4445 service set is therefore a dev-Docker subset, not a
replacement-equivalent successor.

The existing manifest-driven registry recreation helper was not safe to apply
to 4445 without a Docker-specific migration layer: its default URLs are
host-local `127.0.0.1:910x` live-surface assumptions, which are not equivalent
to gateway-container-reachable compose or host endpoints.

The read-only Docker migration planner added for this issue classifies all nine
baseline services and emits a no-mutation successor profile:

- compose sidecars: `context7`, `mentality`;
- host-gateway projections requiring review: `ssh-tmux`, `playwright`,
  `exa-search`, `github`, `web-search`, and the project-scoped Serena service;
- direct remote target: `openzeppelin-solidity-contracts`;
- unsafe live defaults: every host-local `127.0.0.1:910x` service must be
  projected or redesigned before 4445 registration;
- approval-blocked services: credential-scoped services, single-user/session
  services, and project-scoped Serena.

The registry recreation apply helper now accepts explicit target metadata:
`--base-url`, `--env-file`, and `--docker-migration-plan`. In dry-run mode it
projects Docker-safe upstream URLs from the migration plan while continuing to
perform no ContextForge API calls and without reading env values. The generated
apply dry-run shows `context7` projected to
`http://context7-transceiver:9203/mcp` and records target base
`http://127.0.0.1:4445`.

The apply helper also now handles Docker successor canonical projection where a
dev-named gateway already owns the target upstream URL. If no gateway matches
the canonical name, the helper may match by identical URL and update that row
instead of attempting a duplicate create. This was required for the existing
`mentality-dev-docker` gateway at `http://mentality-transceiver:9201/mcp`.

Safe-service apply against 4445 completed for the three non-blocked services:

| Service | Gateway action | Server action | Tools |
| --- | --- | --- | ---: |
| `context7` | updated `context7-local` | updated `context7_local_server` | 2 |
| `mentality` | updated from URL match to `mentality` | created `mentality_server` | 5 |
| `openzeppelin-solidity-contracts` | created | created `openzeppelin_solidity_contracts_server` | 8 |

Post-apply authenticated 4445 readback returned:

| Endpoint | Count |
| --- | ---: |
| `/gateways` | 3 |
| `/servers` | 4 |
| `/tools` | 15 |
| `/prompts` | 0 |
| `/resources` | 0 |

The live server menu read model sees nine manifest-backed service choices and
marks these three services as matched:

- `context7:canonical`
- `mentality:static_repo_local`
- `openzeppelin-solidity-contracts:canonical`

The remaining services are still intentionally unmatched or not provisioned on
4445:

- `exa-search:credential_scoped`
- `github:canonical`
- `playwright:session_scoped`
- `ssh-tmux:session_scoped`
- `web-search:credential_scoped`
- `serena:8a2a6256eec8`

The old `mentality_dev_docker_server` virtual server remains present as
transitional Docker bootstrap residue and is associated with the same canonical
mentality tool IDs. It does not add an extra project-init menu item because
service discovery is manifest-backed and keys readback to expected virtual
server names, but it should be reconciled before claiming a fully clean
successor surface.

## 4445 Guidance Replay

`scripts/register_tool_guidance.py` now accepts explicit target metadata:
`--base-url`, `--env-file`, repeatable `--service`, `--dry-run`, and `--json`.
It resolves gateway IDs from live target gateway readback instead of relying on
the hardcoded 4444 gateway IDs in `SERVICE_META`.

The script also now uses deterministic short guidance tags for ContextForge tag
values longer than 50 characters. This repairs the OpenZeppelin stablecoin
association problem without depending on an over-limit tag that the stock
ContextForge API silently drops. The stablecoin source tool
`openzeppelin-solidity-contracts-solidity-stablecoin` maps to the short tag
`tool-1d3cda5a19e32f4a` on 4445 prompt/resource records.

Bounded guidance dry-run for `context7`, `mentality`, and
`openzeppelin-solidity-contracts` planned:

| Service | Resources | Prompts |
| --- | ---: | ---: |
| `context7` | 2 | 2 |
| `mentality` | 5 | 5 |
| `openzeppelin-solidity-contracts` | 8 | 8 |

The bounded apply created 15 resources and 15 prompts on 4445. After introducing
the short stablecoin guidance tag, a follow-up OpenZeppelin-only apply updated 8
resources and 8 prompts without creating new rows.

Post-guidance authenticated 4445 readback returned:

| Endpoint | Count |
| --- | ---: |
| `/gateways` | 3 |
| `/servers` | 4 |
| `/tools` | 15 |
| `/prompts` | 15 |
| `/resources` | 15 |

Server association readback:

| Server | Tools | Prompts | Resources |
| --- | ---: | ---: | ---: |
| `context7_local_server` | 2 | 2 | 2 |
| `mentality_server` | 5 | 5 | 5 |
| `openzeppelin_solidity_contracts_server` | 8 | 8 | 8 |
| `mentality_dev_docker_server` | 5 | 0 | 0 |

The post-guidance planner reports 15 target prompt guidance tags and 15 target
resource guidance tags out of 81 source-defined guidance keys. The remaining
66 missing keys correspond to the unresolved credential-scoped, session-scoped,
and project-scoped services.

## Remaining Boundary Analysis

Read-only boundary analysis after the guidance replay classified the next work
as policy/runtime sequencing, not blind bulk registration:

- credential-scoped services (`exa-search`, `github`, `web-search`) should not
  have secrets copied into the gateway container; any 4445 registration must
  explicitly approve the credential scope and, for GitHub, the mutating tool
  exposure.
- session/single-user services (`playwright`, `ssh-tmux`) need isolated or
  explicitly shared successor runtime decisions. `ssh-tmux` is especially
  sensitive because its tools can send keys, write files, close sessions, and
  clean up sessions.
- project-scoped Serena must use the canonical cf-controlplane project root and
  preserve the virtual-server exclusion of `activate_project`; it should not be
  rebound to this issue worktree as if that were the durable project identity.

The planner and manifest drift identified by that analysis has been reconciled:
`server-instances/ssh-tmux/instance.json` now records the ninth canonical
`ssh-tmux-cleanup-dead-sessions` tool, and the Docker migration planner records
`scripts/register_tool_guidance.py` as reusable after target parameterization
rather than unsafe due to hardcoded gateway IDs.

Host-gateway projections in the Docker migration plan should be treated as
explicit interim migration projections unless a later architecture decision
promotes one to durable successor topology.

## Docker Upstream Reachability Guard

The controller added a non-mutating Docker-upstream reachability probe,
`scripts/probe_contextforge_docker_upstreams.py`, that executes from inside the
4445 ContextForge container and checks the target URLs from the Docker
successor migration plan. The live probe found:

- reachable from the 4445 container: `context7`, `mentality`, and
  `openzeppelin-solidity-contracts`;
- unreachable from the 4445 container: `exa-search`, `github`, `playwright`,
  `serena-cf-controlplane-d46fe58a2a20`, `ssh-tmux`, and `web-search`;
- the host-gateway projected services failed with connection refused from
  `host.docker.internal:910x`, even though the corresponding host processes are
  listening on `127.0.0.1:910x`.

That evidence means host-gateway projection is not currently a valid successor
runtime topology for the remaining host-local services. The next implementation
slice must either create Docker-reachable sidecar/transceiver services or make
an explicit, safer host-binding architecture decision before registering those
services on 4445.

`scripts/apply_contextforge_registry_recreation.py` now guards this boundary:
services marked approval-blocked in the Docker migration plan are skipped during
`--apply` unless the controller passes an explicit
`--boundary-approved-service <slug>` flag. A no-op apply attempt for
`ssh-tmux` produced zero registry/API calls, did not read env values, and
recorded `mutation_performed=false`.

## Controller Disposition

#284 should remain Active or In Review only after explicit controller
disposition. The 4444 host gateway now has refreshed full-list readback
evidence showing canonical shared services and near-complete source guidance
coverage, with one known stablecoin tag defect that should be repaired during
successor migration. The 4445 successor surface now has authenticated readback
evidence and partial safe-service apply evidence. Because 4444 is scheduled for
decommissioning, 4445 parity is not optional cleanup; it is the next required
migration-readiness slice before any claim that the replacement ContextForge
surface preserves the canonical service and guidance set. Remaining work:
Docker-reachable topology for the remaining credential/session/project-scoped
services, guidance replay for those services after registration, cleanup of
stale dev bootstrap residue, and a final parity readback.
