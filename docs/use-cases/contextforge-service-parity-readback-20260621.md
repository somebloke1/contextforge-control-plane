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

- Full sanitized JSON:
  `generated/contextforge-284-full-pagination-readback-1782008501.local.json`
- Tag analysis:
  `generated/contextforge-284-guidance-tag-analysis-1782008501.local.json`
- Token value was used only in memory and was not written to the artifacts.
- No token was created, revoked, or modified.
- No registry, service, prompt, resource, tool, or server mutation was
  performed.

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

This confirms the two gateways are separate authenticated surfaces. It does not
prove 4445 parity, and it does not prove 4445 deficiency. The next step for
4445 requires an intentionally supplied or generated credential for that
surface, or a controller decision that 4445 is a dev/test comparison target
rather than a strict successor to 4444.

## Controller Disposition

#284 should remain In Review. The 4444 host gateway now has refreshed
full-list readback evidence showing canonical shared services and complete
81/81 prompt/resource guidance pairing by canonical tool tag. The remaining
unproven boundary is 4445 parity, which is blocked by authentication policy
rather than by a readback mismatch. Because 4444 is scheduled for
decommissioning, 4445 parity is not optional cleanup; it is the next required
migration-readiness slice before any claim that the replacement ContextForge
surface preserves the canonical service and guidance set.
