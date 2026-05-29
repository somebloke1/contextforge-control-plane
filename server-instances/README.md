# Server Instances

Each service exposed by ContextForge has one backend home under this directory:

```text
server-instances/<service-slug>/
```

The directory describes the actual upstream service ContextForge registers or
proxies. It is not a replacement for stock ContextForge.

Expected contents:

- `instance.json`: sanitized source of truth for the backend service, bridge
  policy, expected endpoints, and ContextForge registration names.
- `run-bridge.sh`: only when the backend needs package bridge support.
- `probe.sh` or equivalent: service-specific runtime verification.
- `.env.example`: sanitized environment template when local env is needed.
- `.env`, `run/`, `logs/`, and `*.local.json`: ignored local runtime state.

Native HTTP/SSE services should still get an instance directory, but their
manifest should point directly at the native endpoint instead of wrapping it.
