# ContextForge Client Harness

Local, headless Debian client containers for validating assistant clients
without binding runtime state to the stable Codex launch checkout.

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

Do not commit `env/local-llama.env`. Generate it from the host:

```sh
scripts/make-local-llama-env.sh
```

The script reads `LOCAL_LLAMA_KEY` from `~/.env` and writes a local env file
with mode `0600` semantics through `umask 077`.

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

## llama.cpp Qwen Probe

Only Pi and OpenCode are configured for the existing host llama.cpp endpoint:

```sh
scripts/probe-llama.sh
```

By default the containers reach the host endpoint through:

```text
http://host.docker.internal:8742/v1
```

and use model id:

```text
qwen3.6-a3b
```

This probe only checks endpoint/model visibility. Agent-level response probes
are run with:

```sh
scripts/smoke-agents.sh
```

The Pi config follows the public Pi custom model docs from:

- https://pi.dev/
- https://github.com/earendil-works/pi/tree/main/packages/coding-agent
- https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md

The OpenCode config follows the public OpenCode config/provider docs:

- https://opencode.ai/docs/config/
- https://opencode.ai/docs/providers/

The remaining launch-only clients are not configured against Qwen in this
harness yet. They are installed and version-checked only.

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

## Pi ContextForge Dev Gateway Path

Pi remains shim-first. The real Pi validation target is
`cf_contextforge_pi_validate` from `pi-extensions/contextforge-global-shim`,
not direct `/mcp` consumption. Container-local Pi validation needs the shim to
run against the development gateway with explicit wrapper overrides. The Debian
Pi image includes a container-local wrapper runtime under
`/opt/contextforge-wrapper-venv`, so it does not depend on the host repo
`.venv`:

- `CONTEXTFORGE_BASE_URL=http://host.docker.internal:4445`
- `CONTEXTFORGE_SERVER_ID` set to the dev virtual server id, avoiding broad
  `/servers` readback from the scoped client token
- `CONTEXTFORGE_BEARER_TOKEN` set to a scoped dev token
- `CONTEXTFORGE_TOKEN_CACHE` pointing at client-container local/ignored state

Run the Pi validation smoke with:

```sh
scripts/smoke-pi-contextforge-dev.sh
```

The script creates a disposable ignored `.project/context_forge_state.json`
inside the client-harness workspace, loads the shim through Pi's explicit
`--extension` flag, calls `cf_contextforge_pi_validate` against
`mentality_dev_docker_server`, writes evidence under ignored `evidence/`, and
revokes the scoped token before exit. It prints only the token id, never the raw
token value.

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
