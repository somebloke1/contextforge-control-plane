# ContextForge Control Plane Dialogue Plan

## Purpose

Formalize a host-wide ContextForge control-plane design before implementation. The goal is to let Codex, Gemini, Claude Code, OpenCode, and similar assistants begin with one stable ContextForge-facing interface, then discover and initialize project resources without repeatedly hand-configuring the same MCP server, prompt, REST tool, skill, or agent for each client.

## Current Working Thesis

ContextForge should become the durable local source of truth for assistant-facing services and initialization material. Client configs should be discovery and bootstrap surfaces, not canonical service identities. A user-global hook should inspect a project-local `.project/context_forge_state.json`; if that file or the relevant state variable is absent, the project is treated as `UNINITIALIZED`.

When an assistant enters an uninitialized project, ContextForge should provide instructions and CRUD-capable APIs that let the assistant identify available services, skills, agents, prompts, resources, and tool backends, present coherent choices to the user, provision only what the user accepts, and record explicit project state.

## Dialogue Sequence

1. Establish actors and boundaries.
   Confirm which clients are in scope, what a "project" means after canonical realpath resolution, and which host-wide versus project-local state each client is allowed to read or write.

2. Define project state.
   Specify the schema and lifecycle for `.project/context_forge_state.json`, including `UNINITIALIZED` as the default when no state exists, explicit initialized/declined/deferred states, migration behavior, and evidence required before a state transition is considered complete.

3. Define the ContextForge resource taxonomy.
   Decide canonical resource types for MCP services, virtual servers, REST/OpenAPI tools, hosted services, prompts, resources, skills, agents, language tooling profiles, environment templates, and user-facing guidance.

4. Define user choice and trust policy.
   Decide how assistants present available services, how the user accepts or declines each option, what may be inferred from project contents, and what must never be silently enabled. Keep client project trust explicit; do not broaden trust automatically.

5. Generalize language tooling.
   Research common programming-language support across the intended assistant ecosystem, ask the user to confirm the supported language set, and define reusable language profiles. Language-specific tooling must be generalized across all confirmed common languages instead of being hard-coded for one proof-of-concept language.

6. Decide LSP and service-coupled tool installation policy.
   Compare host-global, user-global, project-local, and ContextForge instance-local installation scopes. The current preferred direction is to couple optional language backends with the relevant ContextForge-managed service instance under that instance directory, while presenting install choices to the user rather than auto-installing.

7. Use Serena as the first empirical proof.
   Keep Serena project-scoped and ContextForge-mediated. Use it to validate project-root selection, virtual-server filtering, app-server verification, language profile selection, optional LSP capability gaps, and instance-local backend scaffolding.

8. Decide Serena memory versus governance registry roles.
   Research and assess Serena's memory system against the repository governance registry paradigm of decisions, abeyant intentions, and open questions. Decide which system is authoritative for durable project governance, which is suitable for tool-local working memory, whether any sync or reference mechanism is needed, and how to avoid conflicting or duplicated sources of truth.

9. Define CRUD APIs and verification contracts.
   Specify ContextForge-facing operations for reading and mutating project state, registering resources, updating prompt/material bundles, provisioning per-project services, and reporting health. Every claim should have an executable verification path through client-visible tools or ContextForge APIs.

10. Produce the implementation roadmap.
    Break the design into narrow increments: schema, global hook, ContextForge API surface, resource catalog, selection dialogue, Serena proof completion, language tooling profiles, cross-client adapters, migration, and operator diagnostics.

## Guiding Governance Intentions

- Single setup per canonical service: configure and operate each backend once through ContextForge unless isolation is required by project scope, credentials, or resource access.
- Explicit project state: absence means `UNINITIALIZED`; every transition after that should be intentional, inspectable, and reversible where practical.
- User-confirmed enablement: assistants may recommend services and tools, but installation, trust expansion, and durable project changes require explicit user acceptance.
- ContextForge as service identity: client config entries are consumers or discovery clues, not the authoritative identity of a backend service.
- Project scope by canonical root: project-local resources must bind to the real project root and must not escape to broad roots such as `/`, `/home/dgk`, or `/home/dgk/workspace`.
- Evidence-first completion: initialization succeeds only when the intended client path can see and call the expected ContextForge-served surface.
- Durable governance over incidental memory: repository decisions, intentions, and open questions remain the durable governance record unless the Serena memory review explicitly decides otherwise.
