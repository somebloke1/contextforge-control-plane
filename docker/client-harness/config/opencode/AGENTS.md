# ContextForge Harness Rules

When the user asks what ContextForge tools are available in an already
initialized project, use the ContextForge helper availability route. In the
visible final answer, preserve these facts from the helper response:

- project root;
- state revision;
- skipped or unavailable ContextForge service status;
- available ContextForge tool names.

Do not restart service selection, propose activation, apply project-init state,
validate or probe tools, mutate configuration, or mention hidden helper
mechanics in the visible answer.

When the user asks what you can do in this project or asks for available
project capabilities, use the ContextForge helper capability-summary route. In
the visible final answer, preserve these capability classes from the helper
response:

- available now;
- known but unavailable;
- available to enable or repair;
- concise current-project provenance.

Do not present unavailable services as already usable, and do not guide
arbitrary/new MCP service onboarding from a URL or source lead. ContextForge
service management is limited to known ContextForge service offerings surfaced
by the helper.

When the user asks to use this project's mentality capability, asks about
recorded project tasks, decisions, open questions, abeyant intentions,
governance ledgers, or governance status in an initialized ContextForge
project, use the ContextForge governance/mentality read-only route. If the user
asks for a specific recorded item, first identify it from the relevant ledger
when needed, then use the read-only route to read that item. If the user does
not name a ledger and asks for a small ordinary project task, prefer the tasks
ledger. Use the exact current project root path as the governance `repo`
argument; in the Docker harness project root this is `/workspace`, not
`workspace`. In the visible final answer, answer from the observed governance
evidence and include concise source signal such as ledger names, entry ids, or
entry titles when available.

Do not read or rewrite local ledger files directly, mutate governance entries,
restart service selection, propose activation, substitute helper availability
or capability-summary readback for a requested governance/mentality task, or
expose helper mechanics in the visible answer.

Do not end with an empty assistant message after a successful
governance/mentality list or read tool call. If a read result returns an entry,
answer with the entry id, title, status, and the relevant recorded detail.

When the user asks what ContextForge state you are using right now in an
initialized project, use the ContextForge state-readback route. In the visible
final answer, preserve the project root, initialized state, state revision,
target client, selected service bindings, visible/imported tools,
skipped/unavailable services, bounded errors, and readiness-layer distinction.

Do not claim interactive proof from readback alone. Do not restart service
selection, validate or probe tools, mutate project state, dump raw JSON, or
expose helper mechanics in the visible answer.

When diagnosing ContextForge configuration or authentication inside this
container, do not print raw env files, bearer headers, passwords, API keys,
tokens, JWTs, private keys, or credential values. Report key presence, file
existence, permissions, selected non-secret ids, and redacted values only. If a
transcript or evidence command must include env-like output, pipe it through
`/repo/docker/client-harness/scripts/redact-contextforge-secrets.py` before it
is written to `/evidence`, copied out of the container, or summarized.
