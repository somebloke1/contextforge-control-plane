# Ledger Shape

Entry shape:

```markdown
<!-- governance-crud:start id=<stable-id> -->
## <stable-id>: <title>

- Ledger: <decisions|abeyant-intentions|open-questions>
- Status: <finite-status>
- Repository: /home/dgk/workspace/context-portal
- Created: YYYY-MM-DD
- Updated: YYYY-MM-DD
- Tags: comma,separated,tags

Body text.
<!-- governance-crud:end id=<stable-id> -->
```

Conventions:

- Decision ids use `dec-YYYYMMDD-NNNN`.
- Open question ids use `oq-YYYYMMDD-NNNN`.
- Preserve old entries; mark them answered, superseded, or closed instead of
  removing continuity.
- Use exact file paths, commands, service names, ports, and dates when they are
  part of the durable decision.
- Do not let service-local memory supersede these ledgers. `mentality` exposes
  the ledgers; it does not replace them.
