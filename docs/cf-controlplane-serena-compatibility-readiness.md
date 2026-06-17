# cf-controlplane Serena Compatibility Readiness

Date: 2026-06-17

This note is part of issue #37 activation readiness. It does not provision
Serena, mutate live ContextForge, change global Codex config, alter systemd, or
edit the legacy `/home/dgk/workspace/legacy-controlplane-archive` checkout.

## Current State

`cf-controlplane` has project-local Codex activation evidence, but canonical
Serena provisioning is not complete. The readiness inspector derives the
expected canonical Serena identity from the current root:

```text
server-instances/serena-cf-controlplane-d46fe58a2a20
serena_cf_controlplane_d46fe58a2a20_server
serena:d46fe58a2a20
```

That canonical backend home is absent on `dev-root`. The existing
`server-instances/serena-cf-controlplane-d46fe58a2a20` tree points at
`/home/dgk/workspace/cf-controlplane`, but its slug, ContextForge gateway name,
virtual server name, and tool names are compatibility identifiers. Treat that
tree as compatibility evidence only, not proof that canonical
`cf-controlplane` Serena provisioning is complete.

The caller-owned Serena metadata under `.serena/project.yml` is not a
compatibility service slug. It should use the active project name
`cf-controlplane`; stale `project_name: "cf-controlplane"` values are now a
readiness concern in the dirty-checkout rebind preflight.

## Inspector Contract

`scripts/inspect_project_init_readiness.py` now reports:

- `activation_artifacts.serena_project_instance.expected` for the canonical
  `cf-controlplane` Serena identity;
- `activation_artifacts.serena_project_instance.legacy` for the compatibility
  `serena-cf-controlplane-d46fe58a2a20` tree;
- `activation_artifacts.serena_project_instance.readiness_decision` with
  `hard_requirement: true`;
- `activation_artifacts.compatibility_identifiers.references` with file-level
  `contextforge://cf-controlplane/` and `serena-cf-controlplane-d46fe58a2a20` references.

Use this readback to classify and retire active legacy naming through
GitHub-tracked slices. Do not broad-rename compatibility or historical
identifiers.

## Approval Boundary

The next Serena implementation slice must either:

- generate and validate the canonical
  `server-instances/serena-cf-controlplane-d46fe58a2a20` instance through the
  approved Serena/project-init path; or
- record an explicit validated compatibility decision that explains why the
  old slug remains the active service identity.

Either path needs separate approval before live registry, service, systemd,
global client config, hook/trust, or process state changes.

## Evidence Command

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  scripts/inspect_project_init_readiness.py \
  --project-root /home/dgk/workspace/cf-controlplane \
  --client-type codex \
  --no-processes \
  --pretty
```
