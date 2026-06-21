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
- Token values were used only in memory and were not written to the artifacts.
- No registry, service, prompt, resource, tool, or server mutation was performed
  by these readbacks.

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

`scripts/register_tool_guidance.py` currently defines 81 tool-guidance
prompt/resource entries across the canonical services.

Tag-based comparison on the 4444 readback found:

- 81 `tool-guidance` prompt records keyed by canonical tool tag.
- 81 `tool-guidance` resource records keyed by canonical tool tag.
- No prompt tool tags missing a corresponding resource tool tag.
- No resource tool tags missing a corresponding prompt tool tag.

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

The existing manifest-driven registry recreation helper is not safe to apply to
4445 without a Docker-specific migration layer: its default URLs are
host-local `127.0.0.1:910x` live-surface assumptions, which are not equivalent
to gateway-container-reachable compose or host endpoints.

## Controller Disposition

#284 should remain In Review. The 4444 host gateway now has refreshed
full-list readback evidence showing canonical shared services and complete
81/81 prompt/resource guidance pairing by canonical tool tag. The 4445
successor surface now has authenticated readback evidence too, and that
evidence shows a concrete parity gap rather than an auth-only boundary.
Because 4444 is scheduled for decommissioning, 4445 parity is not optional
cleanup; it is the next required migration-readiness slice before any claim
that the replacement ContextForge surface preserves the canonical service and
guidance set.
