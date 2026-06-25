# Link issues that this pull request addresses (for example "Closes #123").
Closes:

## Summary

<!-- What does this change do, and why? -->

## Verification

<!-- Evidence that the change works. Use current local files, command output,
     service state, and HTTP probes as authority. -->

- [ ] Local validation ran in `.venv` (branch has its own `.venv`).
- [ ] No real secrets, tokens, or generated JWTs are committed.
- [ ] Runtime env files, tokens, databases, logs, and `*.local.json` outputs
      are kept out of Git.

## Type of change

- [ ] Bug fix
- [ ] Feature / ideal-form
- [ ] Validation / testing
- [ ] Documentation
- [ ] Governance ledger edit (via `scripts/governance_crud.py`)
- [ ] Other

## Non-actions / boundaries

<!-- Anything this change intentionally does NOT do, for example: must not
     mutate runtime services, registry state, trust, or Pi/global client
     config. -->

## ContextForge-owned state

<!-- If this changes ContextForge registry/catalog state, confirm it is done
     through the ContextForge API or Admin UI behavior, not direct database
     writes (direct DB writes are prohibited). If not applicable, write N/A. -->
