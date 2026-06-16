# Abeyant Intentions

This ledger captures real intentions that should not disrupt the active work.
Parked intentions may later become tasks, decisions, or open questions.

<!-- governance-crud:start id=ai-20260528-0001 -->
## ai-20260528-0001: Keep prior generated-fleet lessons visible without preserving that architecture

- Ledger: abeyant-intentions
- Status: parked
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: lessons,architecture,cleanup,contextforge

Prior work showed that custom generated translators, served-instance wrappers,
and bespoke registration scripts can prove endpoint mechanics, but they also
pull the project away from operating ContextForge as designed. Mine those
results only for verification expectations and transport edge cases; do not
carry the generated-fleet architecture forward.
<!-- governance-crud:end id=ai-20260528-0001 -->

<!-- governance-crud:start id=ai-20260528-0002 -->
## ai-20260528-0002: Add thin operational scripts only after stock behavior is proven

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: scripts,verification,operations,stock

Thin operator scripts are now present where stock behavior was first proven. scripts/register_tool_guidance.py registers prompt/resource documentation through ContextForge APIs, uses the stock content-security validator for preflight, and does not replace gateway/runtime behavior. Other operator scripts remain bounded to inventory, governance CRUD/MCP, user systemd installation, and ContextForge stdio wrapping.
<!-- governance-crud:end id=ai-20260528-0002 -->

<!-- governance-crud:start id=ai-20260528-0003 -->
## ai-20260528-0003: Promote sanitized examples only after live registration proof

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: templates,documentation,registration,secrets

Sanitized registration examples have been promoted only after live proof. scripts/register_tool_guidance.py now stores the repeatable prompt/resource guidance registration logic, with API readback and MCP client readback proving 80 prompts and 80 resources associated across all active canonical virtual servers, including GitHub and web-search. Runtime env files, bearer tokens, DB files, logs, screenshots, and host inventories remain ignored local state.
<!-- governance-crud:end id=ai-20260528-0003 -->

<!-- governance-crud:start id=ai-20260528-0004 -->
## ai-20260528-0004: Finish local gateway restart and verification

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: https,verification,local-runtime

Local gateway restart and Admin UI/API verification are complete for the current runtime. The gateway now runs on plain loopback HTTP at http://127.0.0.1:4444 with SSL=false per dec-20260528-0043. Earlier HTTPS/Admin UI verification proved the source-built Admin UI static bundle and ContextForge API behavior; current direct MCP client verification proves OpenCode, Gemini CLI, and Claude Code connect through authenticated HTTP virtual-server /mcp endpoints without local CA environment.
<!-- governance-crud:end id=ai-20260528-0004 -->

<!-- governance-crud:start id=ai-20260528-0005 -->
## ai-20260528-0005: Create backend homes for all enabled inventory services before broad registration

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: server-instances,inventory,registration

The earlier generated 22-entry backend-home pass was superseded by the canonical deduplicated service set. The repo-local governance service is now `mentality` at 9100, and each currently exposed canonical service has a backend home under `server-instances/`.
<!-- governance-crud:end id=ai-20260528-0005 -->

<!-- governance-crud:start id=ai-20260528-0006 -->
## ai-20260528-0006: Register remaining stdio MCP services in controlled batches

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: registration,stdio,bridges,contextforge

The remaining canonical service set has been registered and verified in controlled batches. Current active canonical virtual servers are mentality_server, ssh_tmux_server, context7_local_server, playwright_server, exa_search_server, openzeppelin_solidity_contracts_server, github_server, and web_search_server. Direct API readback and MCP stdio wrapper readback confirmed matching tool, resource, and prompt counts for each server.
<!-- governance-crud:end id=ai-20260528-0006 -->

<!-- governance-crud:start id=ai-20260530-0001 -->
## ai-20260530-0001: ContextForge as host-wide assistant control plane

- Ledger: abeyant-intentions
- Status: honored
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-29
- Updated: 2026-05-30
- Tags: contextforge,bootstrap,control-plane,project-init,governance,serena,lsp,rfc

The host-wide assistant control-plane intention is honored by the formal design RFC, implementation procedure, and Wave 0-12 outputs. Future continuity should cite docs/initiatives/contextforge-control-plane/design-rfc.md, docs/initiatives/contextforge-control-plane/design-rfc-procedure.md, implementation-runbook.md, acceptance-checklist.md, and the run evidence instead of treating the older dialogue plan as the active source of truth.
<!-- governance-crud:end id=ai-20260530-0001 -->

<!-- governance-crud:start id=ai-20260530-0002 -->
## ai-20260530-0002: Review prompt/resource library for inference-inclusive proof

- Ledger: abeyant-intentions
- Status: parked
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: inference-testing,prompts,resources,regression,qa

Review the ContextForge prompt/resource guidance library for inference-inclusive proof and regression testing. The review should confirm that registered prompts/resources support Python-invoked headless agent scenarios, structured evaluator verdicts, concrete evidence citations, inferential isolation, remediation handoffs, and repeatable regression evidence without relying on deterministic pattern matching for semantic claims.
<!-- governance-crud:end id=ai-20260530-0002 -->

<!-- governance-crud:start id=ai-20260531-0001 -->
## ai-20260531-0001: Continue project-init refinement after live staged inference pass

- Ledger: abeyant-intentions
- Status: parked
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-05-31
- Updated: 2026-05-31
- Tags: contextforge,project-init,inference-testing,regression,cleanup

Continue refining the ContextForge project-init flow from the current implementation rather than restarting the design. The current full unit suite and six-case live staged inference run passed on 2026-05-31 with run id live-staged-inference-20260531T230915Z and evidence under run/contextforge-control-plane-implementation/live-staged-inference/live-staged-inference-20260531T230915Z/. Future changes must preserve idempotency, target-client-visible validation, stable service identity ID handling, numbered/user-selectable choices, explicit reload instructions, ephemeral temp project cleanup, ContextForge service-instance cleanup, and the prohibition on deterministic semantic gates. Re-run the full unit suite and live staged inference validation after material prompt or helper changes.
<!-- governance-crud:end id=ai-20260531-0001 -->

<!-- governance-crud:start id=ai-20260609-0001 -->
## ai-20260609-0001: Generate identifiers deterministically instead of by agent discretion

- Ledger: abeyant-intentions
- Status: parked
- Repository: /home/dgk/workspace/context-portal
- Created: 2026-06-09
- Updated: 2026-06-09
- Tags: identifiers,determinism,project-init,governance

Future project-init and governance workflows should generate identifiers programmatically from stable inputs or monotonic ledger state instead of leaving identifier choice to agent discretion. The generated scheme should deterministically avoid duplicate identifiers, preserve existing stable IDs, and make any collision handling explicit and repeatable so retries, resumes, and concurrent-looking edits do not mint conflicting service, plan, ledger, challenge, consent, or validation identifiers.
<!-- governance-crud:end id=ai-20260609-0001 -->
