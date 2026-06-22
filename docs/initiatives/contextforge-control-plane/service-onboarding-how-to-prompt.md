# ContextForge Service Onboarding How-To

Use this as internal process context for extended uncataloged MCP service
onboarding. Do not copy it to the user as visible prose.

The workflow is:

1. Start from the user's source lead or other concrete clue.
2. Research source evidence before making implementation claims.
   If source-research tooling is available, use it against the provided source
   lead. If it is unavailable, say that the source-research/apply surface is
   missing. Do not guess package names, commands, tools, transports, or config
   files.
   For GitHub or repository leads, prefer raw file/API/package metadata
   retrieval with source anchors. A rendered repository page, search-result
   snippet, or subagent summary is not enough to confirm technical claims. If
   you cannot reach raw files or package metadata, ask for a source-research
   surface or stop at an explicitly unconfirmed source-inspection checklist.
   When available, call the ContextForge source-research helper for the source
   lead before building the onboarding plan.
3. Build a source-only onboarding record naming service identity, transport,
   scope/locality, state footprint, credential boundary, implementation
   decisions, proof boundaries, and open questions.
4. Present key decisions methodically and keep the planning boundary clear.
   Normal code-assistant work is useful here: with user approval, you may
   draft auditable workspace-local onboarding artifacts when that helps
   preserve decisions and lets the user review the boundary. For the current
   npm-stdio onboarding target, the normal implementation artifacts are:
   - a managed npm-stdio service record for the shared ContextForge
     `npm-stdio-host` Docker service, naming the npm package, version or
     version policy, runtime hint, stdio command arguments, non-secret
     environment placeholders, required secret names, and bridge endpoint
     allocation;
   - a ContextForge API JSON definition that describes the transparent
     registration request, including gateway creation/update, expected tool
     refresh/readback, virtual-server creation/update, expected tool names, and
     rollback targets.
   These artifacts are intermediate work product, not proof of installation,
   registration, exposure, or availability. Use them as inputs to the
   ContextForge onboarding flow; do not let them become a parallel direct-client
   configuration path.
   When you need exact artifact paths or JSON shape, retrieve the non-mutating
   runtime/apply package from the ContextForge helper and use its
   `install_artifact_contract`. Do not infer a `.contextforge/services` schema,
   create generic metadata catalogs, or inspect a blank workspace to guess where
   the files belong.
   Choosing npm plus `stdio` identifies a service suitable for the shared
   npm-stdio host. It should not trigger a bespoke service Dockerfile by
   default. The Dockerfile belongs to the reusable host substrate, not to every
   onboarded npm MCP service. Omit the per-service managed npm-stdio record only
   when source evidence shows the upstream already exposes an approved native
   HTTP/SSE endpoint and the user approves direct native registration.
   The helper does not research these values for the assistant. It requires the
   assistant to confirm the exact npm package with the user, research and
   determine transport, environment variables, secret names, package/runtime
   arguments, tool schemas, and standard prompt-library content, then supply
   those fields before install/register packaging. If required fields are
   missing, the helper must refuse to attempt onboarding and identify the
   missing fields.
5. When the user asks to continue, use the ContextForge service-onboarding or
   service-management continuation surface. Do not treat an uncataloged service
   as an existing project-init activation choice.
6. When the user later approves runtime/apply work after continuation, first use
   the ContextForge service-onboarding runtime/apply package surface to retrieve
   the non-mutating package and `install_artifact_contract`. That package must
   name the service binding, shared npm-stdio host target, per-service managed
   runtime record, service-provision plan, ContextForge registration plan, and
   ContextForge API JSON target while still avoiding mutation unless an
   approved executor performs it.
   The service binding is ContextForge identity such as `time:canonical`;
   executable strings such as `uvx mcp-server-time` belong in backend command
   fields, not in the service binding.
7. Runtime/apply execution is a later approved surface. It must prove backend
   behavior, ContextForge registration, reload or new-session boundary,
   target-client-visible service listing, and a safe call before verified
   availability is claimed.
   If the shared host or ContextForge registration attempt fails, the helper
   should return the observed or abstracted error to the assistant and state
   that the assistant must determine the required correction. It must not
   prescribe service-specific fixes, rewrite arguments, or provide hidden
   correction coaching. Runtime/apply execution must be idempotent and
   transactional: if install, start, bridge, registration, tool refresh,
   prompt publication, or virtual-server association fails, the executor must
   cleanly uninstall/remove any partially created hosted-service, ContextForge,
   prompt-library, or bridge state before returning the stage-labeled error.

Claim boundaries:

- Source-only planning does not install, register, start, expose, import,
  validate, probe, or make a service available.
- Agent-authored local planning artifacts are allowed only as approved,
  source-derived onboarding work product. For the npm-stdio target, prefer the
  managed npm-stdio service record plus ContextForge API JSON pair over generic
  metadata catalogs or per-service Dockerfiles.
  They do not replace ContextForge continuation/runtime-apply tools and they do
  not prove target-client availability.
- If the runtime/apply package or executor surface is missing, say so directly
  as a generic support gap. Do not substitute direct client-local
  configuration.
- User approval to create arbitrary local client files is not a ContextForge
  runtime/apply surface. Do not write `.vscode/mcp.json`, `.opencode`, client
  config, or project activation files unless a ContextForge helper/apply surface
  performs that exact approved mutation.
- Use only conversation-visible and source-derived facts. Do not inject
  controller memory, evaluator criteria, or service-specific test fixtures.
- Do not outsource source truth to an unanchored subagent summary. If a
  delegated or tool-produced summary lacks file-level anchors, treat it as a
  lead to verify, not as evidence.
- Keep user-visible answers clean and concise; put internal mechanics only in
  hidden/tool context.
