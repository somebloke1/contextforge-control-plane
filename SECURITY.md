# Security Policy

## Reporting a vulnerability

This repository is a local operator workspace for a stock IBM ContextForge MCP
Gateway installation. We take security reports seriously.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately using GitHub's "Report a vulnerability" feature
on the **Security** tab, which creates a private security advisory visible only
to repository maintainers. Include:

- A description of the issue and its potential impact.
- The exact conditions, commands, or inputs needed to reproduce it.
- The local runtime, ContextForge version, and client involved (if relevant).
- Any suggested remediation.

## Scope

This policy covers this repository's tracked content: the ContextForge
operator scripts, helper/wrapper source, governance tooling, Docker harness
sources, configuration templates, and documentation.

It does **not** cover the upstream IBM ContextForge package itself; report
upstream ContextForge security issues through that project's own channels. It
also does not cover the MCP servers surfaced through ContextForge (for example
GitHub, web-search, exa-search, context7, playwright, ssh-tmux, openzeppelin,
or the local `mentality` governance service); report those through their
respective upstream projects.

## Supported versions

This workspace tracks a single active line of development on the `dev-root`
branch. Security fixes are applied to `dev-root` and flow into released work
from there. Only the latest state is eligible for fixes.

## Local secrets and trust hygiene

Contributors and operators must follow the project's secrets policy (see
[`AGENTS.md`](./AGENTS.md) and [`CONTRIBUTING.md`](./CONTRIBUTING.md)):

- **Never commit** real API keys, bearer tokens, passwords, generated JWTs, or
  client-local secret values.
- Runtime env files, tokens, databases, logs, generated inventories, and
  installed systemd state are local operational state and must stay out of Git.
  Keep them in ignored local paths such as `config/contextforge.env`,
  `server-instances/<name>/.env`, or installed `/etc/contextforge/*.env`.
- Inventory outputs ending in `.local.json` are host-specific and ignored.
- Do not bundle trust mutation (for example Codex/OpenCode project trust,
  OAuth, or trust-token changes) into generic project initialization. Handle
  trust only through brokered, separate human approval with receipt-backed
  evidence.
- Change ContextForge-owned state only through the ContextForge API or Admin UI
  behavior. **Direct ContextForge database writes are prohibited.**

## Disclosure

Maintainers will acknowledge private vulnerability reports promptly, coordinate
a fix on a private branch where appropriate, and publish a security advisory
with credit once a remediation is available.
