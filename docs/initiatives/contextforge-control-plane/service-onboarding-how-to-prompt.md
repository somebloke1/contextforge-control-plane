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
3. Build a source-only onboarding record naming service identity, transport,
   scope/locality, state footprint, credential boundary, implementation
   decisions, proof boundaries, and open questions.
4. Present key decisions methodically and keep the planning boundary clear.
5. When the user asks to continue, use the ContextForge service-onboarding or
   service-management continuation surface. Do not treat an uncataloged service
   as an existing project-init activation choice.
6. Runtime/apply work is a later approved surface. It must prove backend
   behavior, ContextForge registration, reload or new-session boundary,
   target-client-visible service listing, and a safe call before verified
   availability is claimed.

Claim boundaries:

- Source-only planning does not install, register, start, expose, import,
  validate, probe, or make a service available.
- If the runtime/apply surface is missing, say so directly as a generic
  support gap. Do not substitute direct client-local configuration.
- User approval to create arbitrary local client files is not a ContextForge
  runtime/apply surface. Do not write `.vscode/mcp.json`, `.opencode`, client
  config, or project activation files unless a ContextForge helper/apply surface
  performs that exact approved mutation.
- Use only conversation-visible and source-derived facts. Do not inject
  controller memory, evaluator criteria, or service-specific test fixtures.
- Keep user-visible answers clean and concise; put internal mechanics only in
  hidden/tool context.
