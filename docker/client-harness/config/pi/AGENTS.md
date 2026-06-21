# Pi Container Harness

Use the configured semantic-test model profile for local smoke tests. Do not
hard-code provider/model ids in prompts or commands; use
`CONTEXTFORGE_PI_DEFAULT_PROVIDER` and `CONTEXTFORGE_PI_DEFAULT_MODEL`.
Avoid file mutation unless the smoke command explicitly asks for it.

When diagnosing ContextForge configuration or authentication inside this
container, do not print raw env files, bearer headers, passwords, API keys,
tokens, JWTs, private keys, or credential values. Report key presence, file
existence, permissions, selected non-secret ids, and redacted values only. If a
transcript or evidence command must include env-like output, pipe it through
`/repo/docker/client-harness/scripts/redact-contextforge-secrets.py` before it
is written to `/evidence`, copied out of the container, or summarized.
