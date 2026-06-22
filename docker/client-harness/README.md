# ContextForge Client Harness

Local, headless Debian client containers for validating assistant clients
without binding runtime state to the stable Codex launch checkout.

Evidence freshness and PR citation rules for this harness are defined in
`../../docs/dev-docker-client-evidence-freshness-protocol.md`.

This harness intentionally does not build or select a ContextForge server
container. It only prepares client surfaces:

- Codex CLI
- Claude Code
- Gemini CLI
- OpenCode
- Pi Coding Agent

Each client is a separate container with its own home volume. The images start
from `debian:bookworm-slim` and install terminal applications from public
package sources; no application-published images are used.

## Secrets

Do not commit `env/semantic-model.env`. Generate it from the host or populate
it directly from `env/semantic-model.env.example`:

```sh
scripts/make-semantic-model-env.sh
```

Semantic-test runs choose one provider-agnostic model profile per run from
`semantic-model-profiles.json` unless `--semantic-model-profile env` or a
specific profile id is supplied. Profiles can name any supported provider kind,
model id, provider-specific key env, base URL env, client support set, and
route-preference list. The current profile pool is OpenRouter-backed and uses
`OPENROUTER_API_KEY`; route preferences are profile-specific, while empty
route lists leave routing to OpenRouter. The generated local env file is
written with mode `0600` semantics through `umask 077`.

`OPENROUTER_STICKY_KEY` is a non-secret cache-affinity key. It is passed as the
OpenRouter `x-session-id` header where the client config surface supports model
request headers. Use one stable base sticky key across the semantic-test profile
so Pi and OpenCode share provider sticky routing for prompt caching. At client
bootstrap/config render time the harness appends a coarse epoch bucket
controlled by `OPENROUTER_STICKY_EPOCH_SECONDS` and defaulting to two hours.
This keeps cache affinity stable within an active testing window while naturally
resetting it between testing epochs.

Do not print raw ContextForge env files, bearer headers, passwords, API keys,
tokens, JWTs, private keys, or credential values into terminal transcripts or
evidence packages. For diagnostics, report key presence/status, file
permissions, selected non-secret ids, and redacted values only. Pipe env-like
or transcript output through the shared redactor before it is written under
`evidence/`, exported from a container, or copied into GitHub:

```sh
docker/client-harness/scripts/redact-contextforge-secrets.py < raw.txt > redacted.txt
```

This includes local-only files such as
`docker/client-harness/client-scoped/contextforge.env` and keys such as
`CONTEXTFORGE_BEARER_TOKEN`; preserve their existence/permission evidence
without copying credential values. Target-client containers must not mount the
Docker ContextForge admin env. They may mount only the client-scoped file, which
must contain least-privilege server credentials such as `CONTEXTFORGE_BEARER_TOKEN`
and `CONTEXTFORGE_SERVER_ID`, never `PLATFORM_ADMIN_EMAIL` or
`PLATFORM_ADMIN_PASSWORD`.

## Build

```sh
docker compose -f compose.yml build
```

The current validated build installed these npm-package versions on 2026-06-16:

| Client | Package | Version |
| --- | --- | --- |
| Codex CLI | `@openai/codex` | `0.140.0` |
| Claude Code | `@anthropic-ai/claude-code` | `2.1.179` |
| Gemini CLI | `@google/gemini-cli` | `0.46.0` |
| OpenCode | `opencode-ai` | `1.17.7` |
| Pi Coding Agent | `@earendil-works/pi-coding-agent` | `0.79.6` |

## Launch Checks

```sh
scripts/check-versions.sh
```

This validates that all five client commands launch.

## Semantic Model Probe

Pi and OpenCode semantic-test paths read provider/model defaults and available
provider secrets from `env/semantic-model.env`:

```sh
scripts/probe-semantic-model.sh
```

By default the env file can reach OpenRouter through:

```text
https://openrouter.ai/api/v1
```

and begins with model id:

```text
google/gemma-4-26b-a4b-it
```

The current default multi-step semantic quorum is Gemma, Qwen Coder, and
DeepSeek v4-class model profiles. Diagnostic or future-candidate profiles may
remain listed but are excluded from random quorum selection unless explicitly
marked eligible.

Each comprehensive runner invocation records the selected semantic profile in
the evidence summary. Random profile selection is per test run, not per
inference, so one transcript has a stable model identity. This probe only
checks endpoint/model visibility. Agent-level response probes are run with:

```sh
scripts/smoke-agents.sh
```

The legacy `scripts/probe-llama.sh` name remains only as a compatibility
wrapper. Do not use it as a local llama-server check unless the configured
semantic-test profile is actually local-hosted.

The probe writes exact advertised model identity reports to ignored local
evidence files:

```text
evidence/pi-semantic-model-identity.json
evidence/opencode-semantic-model-identity.json
```

Each report records the expected harness model id, the endpoint-advertised
model ids, the exercised client surface, and a `current`, `stale`, or `unverified`
status. A mismatch marks the evidence stale rather than silently
accepting a nearby alias.

The Pi config follows the public Pi custom model docs from:

- https://pi.dev/
- https://github.com/earendil-works/pi/tree/main/packages/coding-agent
- https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md

The OpenCode config follows the public OpenCode config/provider docs:

- https://opencode.ai/docs/config/
- https://opencode.ai/docs/providers/

Prompt caching is provider-level. For Gemini through OpenRouter, keep stable
prompt prefixes across turns and use the shared sticky key so repeated agent
sessions route to the same provider cache context for the current epoch. Inspect
`usage.prompt_tokens_details.cached_tokens` where raw responses are available.
Do not add Anthropic-style `cache_control` markers for this Gemini profile;
Google prompt caching is implicit for eligible repeated prefixes.
Do not enable or evaluate OpenRouter response caching via `X-OpenRouter-Cache`;
that caches identical whole responses and is not the semantic-test objective.

The remaining launch-only clients do not consume this semantic-test model
profile yet. They are installed and version-checked only.

## ContextForge Helper Baseline

See `CONTEXTFORGE_HELPER_BASELINE.md` for the Pi/OpenCode baseline contract
that closes the gap between specialized ContextForge smoke scripts and ordinary
ad hoc client sessions.

See `USE_CASE_1_E2E_GATE.md` for the required PR #271 / Use Case 1 gate before
human review. Human review must be preceded by passing Pi and OpenCode full
command-line agent-session transcripts, with stable session ids and observed
tool outputs, verified by
`scripts/verify-use-case-1-e2e-evidence.py`.

See `../../docs/client-visible-activation-matrix.md` for the client-specific
activation/readiness observables. Pi and OpenCode are not expected to show a
Codex-style hook banner; they have their own shim/plugin/helper readback paths.

The harness-owned baseline launchers are:

```sh
scripts/start-pi-contextforge-baseline.sh
scripts/start-opencode-contextforge-baseline.sh
```

They mount this repository read-only at `/repo`, with the narrow exception that
`/repo/server-instances` is writable for helper-managed project-scoped service
backends such as Serena. They keep generated client state in the client
container/workspace volumes, keep Pi/OpenCode on the configured semantic-test
model profile, seed only container-user helper/plugin bootstrap where needed,
and avoid host Pi/OpenCode global config mutation. Runtime
proof still requires separate approval to rebuild or run Docker client
containers.

The persistent and ephemeral Compose services are dev-time testing affordances.
They are not production deployment modes, but they make ordinary use cases
repeatable during staging.

Pi, OpenCode, Gemini, Codex, and similar tools are representative
code-assistant consumers in this harness. ContextForge production
responsibility reaches the helper service and the services that the helper
facilitates; code-assistant runtimes are exercised as consumers, not as runtime
surfaces owned by this control plane. Pi and OpenCode are the currently
configured semantic-test install/readback samples because they are thin consumers,
especially Pi, and expose less-mediated model behavior during development
checks.

Use the ordinary `pi` and `opencode` Compose services when a dev-time test
needs multi-session persistence in `/workspace`, such as exercising project
init through install plus reload/new-session-required. Persistent tests must
also prove idempotency: rerunning the same activation/resume flow should
converge on the same project-local state and should not leave duplicate, stale,
or orphaned library/config artifacts behind.

The Pi service also wraps bare `pi` commands inside the container. A developer
who enters the persistent container with `docker compose -f
docker/client-harness/compose.yml run pi bash` and then runs `pi` gets the same
container-local semantic model file and ContextForge shim bootstrap as the baseline
launcher, without touching host/global Pi state.

Use `pi-ephemeral` and `opencode-ephemeral` when a dev-time test needs a clean
project workspace on each container run. These services mount `/workspace` as
tmpfs, so project-local state is discarded when the container stops while the
repo and container user-home bootstrap surfaces remain unchanged:

```sh
docker compose -f docker/client-harness/compose.yml run --rm pi-ephemeral bash
docker compose -f docker/client-harness/compose.yml run --rm opencode-ephemeral bash
```

## OpenCode ContextForge Dev Gateway Smoke

After the ContextForge development Docker gateway and `mentality-transceiver`
from `../contextforge-harness` are running and registered, OpenCode can validate
the remote MCP client surface without touching the legacy/live gateway:

```sh
scripts/smoke-opencode-contextforge-dev.sh
```

The script creates a one-day scoped token for
`mentality_dev_docker_server`, runs `opencode mcp add` and
`opencode mcp list` inside the OpenCode client container against
`http://host.docker.internal:4445/servers/<server-id>/mcp/`, writes evidence
under ignored `evidence/`, and revokes the token before exit. It prints only
the token id, never the raw token value.

Issue #144 requires this smoke to distinguish connection/list evidence from a
real target-client safe call through the `mentality` route. By default, the
script now requires an explicitly reviewed OpenCode command in
`OPENCODE_SAFE_CALL_COMMAND` and fails with
`smoke_result=failed_missing_required_safe_call` if that command is absent. The
safe-call contract is:

- surface labels: `OpenCode client Docker` against `ContextForge dev Docker`;
- route: `mentality_dev_docker_server` through the OpenCode remote MCP entry;
- safe probe id: `governance-list`;
- allowed tools: `mentality-governance-list`,
  `mentality-governance-read`, `governance_list`, and `governance_read`;
- default expected tool: `mentality-governance-list`;
- accepted result: `opencode mcp list` evidence plus
  `safe_call_status=passed` from the same OpenCode container run.

This repository slice does not claim the exact OpenCode CLI command for MCP
tool invocation is proven. When runtime execution is later approved, set
`OPENCODE_SAFE_CALL_COMMAND` to the reviewed target-client invocation and keep
the command from printing raw bearer tokens. The smoke transcript is still
redacted for the scoped token before it is appended to evidence. For list-only
diagnostics that must not be cited as target-client safe-call proof, set
`OPENCODE_REQUIRE_SAFE_CALL=0`; that path records
`smoke_result=list_only_without_safe_call`.

## Pi ContextForge Dev Gateway Path

Pi remains shim-first. The Pi client Docker smoke uses
`cf_contextforge_pi_readback` from `pi-extensions/contextforge-global-shim`,
not direct `/mcp` consumption. Container-local Pi readback needs the shim to run
against the development gateway with explicit wrapper overrides. The Debian Pi
image includes a container-local wrapper runtime under
`/opt/contextforge-wrapper-venv`, so it does not depend on the host repo
`.venv`:

- `CONTEXTFORGE_BASE_URL=http://host.docker.internal:4445`
- `CONTEXTFORGE_SERVER_ID` set to the dev virtual server id, avoiding broad
  `/servers` readback from the scoped client token
- `CONTEXTFORGE_BEARER_TOKEN` set to a scoped dev token
- `CONTEXTFORGE_TOKEN_CACHE` pointing at client-container local/ignored state

Run the Pi readback smoke with:

```sh
scripts/smoke-pi-contextforge-dev.sh
```

The script creates a disposable ignored `.project/context_forge_state.json`
inside the client-harness workspace, loads the shim through Pi's explicit
`--extension` flag, calls `cf_contextforge_pi_readback` against
`mentality_dev_docker_server`, writes evidence under ignored `evidence/`, and
revokes the scoped token before exit. It prints only the token id, never the raw
token value. Project init itself stops after install plus reload/new-session
required; service-specific tool use is a separate client exercise.

Do not install or reload the host user-global Pi extension for this harness
without separate approval.

## Authenticated Container State

The default client images are clean tool images. When an authenticated state
needs to travel with a runnable local container, capture it into a local-only
derived image. Do not push these images to a registry.

Authenticated image names and Vertex AI defaults below describe this host's
current local validation setup. They are not portable credentials or project
requirements. Override `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and
`GOOGLE_GENAI_USE_VERTEXAI` for another operator or environment, and recapture
authenticated images locally after user login.

The current local Gemini authenticated image is:

```text
contextforge-client-gemini-cli:authenticated
```

The current local Codex authenticated image is:

```text
contextforge-client-codex-cli:authenticated
```

It was captured from a user-authenticated Codex CLI container and contains only
the minimal `~/.codex` auth/config identity files. Session logs, history,
cache, temp files, and SQLite state databases are excluded.

Run the authenticated Codex image directly through compose:

```sh
docker compose -f compose.yml run --rm codex-cli-authenticated codex login status
```

Or attach to it:

```sh
docker compose -f compose.yml run --rm -it codex-cli-authenticated bash
```

Codex validation must use this authenticated image, not a raw API key. The
accepted Codex test model for this harness is:

```text
gpt-5.4-mini
```

The current authenticated image has this model pinned in
`/home/agent/.codex/config.toml`:

```toml
cli_auth_credentials_store = "file"
model = "gpt-5.4-mini"
```

The Codex compose services force known API-key variables to empty strings,
including `OPENAI_API_KEY`, `CODEX_API_KEY`, `ANTHROPIC_API_KEY`,
`OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`,
`PERPLEXITY_API_KEY`, `EXA_API_KEY`, and `CONTEXT7_API_KEY`. Codex auth checks
and smoke commands must launch through `scripts/run-codex-authenticated.sh`;
that wrapper strips every host environment variable named `API_KEY` or ending
in `_API_KEY` before invoking Docker Compose, then applies explicit empty
container overrides. Host API-key environment variables must not enter the
Codex Docker runtime.

Run a contained OAuth-backed Codex smoke from the authenticated image with:

```sh
scripts/run-codex-authenticated.sh \
  codex exec --json --sandbox read-only --skip-git-repo-check \
  "Reply with exactly: codex-auth-ok"
```

The idempotent client reset script may remove the unauthenticated
`contextforge-client-harness_codex-cli-home` volume, but it must preserve the
local-only `contextforge-client-codex-cli:authenticated` image. That image is
the repeatable OAuth state carrier for Docker Codex tests.

It was captured from a user-authenticated Gemini CLI container, includes Vertex
AI ADC state, and defaults to:

```text
GOOGLE_CLOUD_PROJECT=main-sunset-499523-m6
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
```

Run the authenticated Gemini image directly through compose:

```sh
docker compose -f compose.yml run --rm gemini-cli-authenticated \
  gemini --skip-trust --output-format text -p "Reply with exactly: gemini-auth-ok"
```

Or attach to it:

```sh
docker compose -f compose.yml run --rm -it gemini-cli-authenticated bash
```

The clean unauthenticated Codex CLI and Gemini CLI services still use named
home volumes:

- `contextforge-client-harness_codex-cli-home`
- `contextforge-client-harness_gemini-cli-home`

Start a Codex CLI container and authenticate inside it:

```sh
docker compose -f compose.yml run --rm -it codex-cli bash
mkdir -p ~/.codex
printf '\ncli_auth_credentials_store = "file"\n' >> ~/.codex/config.toml
codex login --device-auth
codex login status
exit
```

Then verify from a fresh container:

```sh
scripts/check-auth-codex.sh
```

To recapture Gemini after reauthenticating or changing local defaults, start a
named clean Gemini container:

```sh
docker compose -f compose.yml run --name gemini-auth-capture -it gemini-cli bash
```

Authenticate/configure inside that container, then leave it running or exit
normally. Capture the mounted home volume into a local image with a no-volume
seed container:

```sh
docker rm -f gemini-auth-image-seed 2>/dev/null || true
docker create \
  --name gemini-auth-image-seed \
  -e GOOGLE_CLOUD_PROJECT=main-sunset-499523-m6 \
  -e GOOGLE_CLOUD_LOCATION=us-central1 \
  -e GOOGLE_GENAI_USE_VERTEXAI=true \
  contextforge-client-gemini-cli:latest \
  sleep infinity
docker start gemini-auth-image-seed
docker exec gemini-auth-capture tar -C /home/agent -cf - . \
  | docker exec -i -u root gemini-auth-image-seed tar -C /home/agent -xf -
docker exec -u root gemini-auth-image-seed chown -R agent:agent /home/agent
docker commit \
  --change 'ENV GOOGLE_CLOUD_PROJECT=main-sunset-499523-m6' \
  --change 'ENV GOOGLE_CLOUD_LOCATION=us-central1' \
  --change 'ENV GOOGLE_GENAI_USE_VERTEXAI=true' \
  --change 'WORKDIR /workspace' \
  --change 'CMD ["bash"]' \
  gemini-auth-image-seed \
  contextforge-client-gemini-cli:authenticated
docker rm -f gemini-auth-image-seed
```

Then verify without a home volume:

```sh
docker run --rm contextforge-client-gemini-cli:authenticated \
  bash -lc 'gcloud auth application-default print-access-token >/dev/null &&
    gemini --skip-trust --output-format text -p "Reply with exactly: gemini-auth-ok"'
```

If the Gemini browser callback cannot complete from inside the container, keep
the image unchanged and adjust only the volume-backed auth flow.

## Alpine Experiment

The validated baseline remains Debian. For comparison, this harness also
contains experimental Alpine Pi and OpenCode images:

```sh
docker compose -f compose.yml build pi-alpine
scripts/smoke-pi-alpine.sh

docker compose -f compose.yml build opencode-alpine
scripts/smoke-opencode-alpine.sh
```

This checks whether `@earendil-works/pi-coding-agent` and `opencode-ai` can
install and run on musl-based Alpine.
