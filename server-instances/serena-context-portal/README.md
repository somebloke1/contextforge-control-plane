# serena-context-portal

Canonical Serena MCP backend for the ContextForge operator repository.

This instance runs Serena as a native streamable HTTP MCP server scoped to
`/home/dgk/workspace/contextforge-slices/repo-local-skills-and-governance`. Serena is project-scoped and stateful, so
this backend is only for that caller workspace and should not be shared for
unrelated workspaces.

Keep the ownership boundary explicit:

- The ContextForge operator owns the service instance: launcher, registration
  metadata, service home, logs, and global Serena config.
- The caller workspace owns project-unique Serena metadata under its `.serena/`
  directory.

For this instance the operator repo and caller workspace happen to be the same
directory on disk. That is incidental; the same split applies when ContextForge
publishes Serena for any other workspace.

The requested port `9107` is already used by the existing `web-search` backend
in this checkout. This instance therefore uses `127.0.0.1:9108` and records that
runtime adjustment in `instance.json`.
