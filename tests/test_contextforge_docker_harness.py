from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContextForgeDockerHarnessTests(unittest.TestCase):
    def test_compose_defines_dev_mentality_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/mcp-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("mentality-transceiver:", compose)
        self.assertIn("contextforge-harness-mentality-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9201:9201"', compose)
        self.assertIn("../client-harness/workspace:/workspace", compose)
        self.assertIn("docker/contextforge-harness/mcp-transceiver/Dockerfile", compose)
        self.assertIn("PYTHONPATH=/opt/mentality/scripts", dockerfile)
        self.assertIn("python /opt/mentality/scripts/governance_mcp.py", dockerfile)

    def test_compose_defines_ssh_tmux_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/ssh-tmux-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("ssh-tmux-transceiver:", compose)
        self.assertIn("contextforge-harness-ssh-tmux-transceiver:latest", compose)
        self.assertIn("../../server-instances/ssh-tmux/.env", compose)
        self.assertIn("../../server-instances/ssh-tmux/auth:/run/contextforge-ssh-tmux:ro", compose)
        self.assertIn('"127.0.0.1:9202:9202"', compose)
        self.assertIn("docker/contextforge-harness/ssh-tmux-transceiver/Dockerfile", compose)
        self.assertIn("openssh-client", dockerfile)
        self.assertIn("sshpass", dockerfile)
        self.assertIn("tmux", dockerfile)
        self.assertIn("uv", dockerfile)
        self.assertIn("MCP_SSH_TMUX_VERSION=0.2.8", dockerfile)
        self.assertIn("mcp-ssh-tmux==${MCP_SSH_TMUX_VERSION}", dockerfile)
        self.assertIn("contextforge-ssh-wrapper.sh /root/.local/bin/ssh", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--stdio", dockerfile)
        self.assertIn("/root/.local/bin/mcp-ssh-tmux", dockerfile)
        self.assertIn("9202", dockerfile)

    def test_ssh_tmux_sidecar_ssh_wrapper_injects_ignored_auth_env(self) -> None:
        wrapper = (
            ROOT / "docker/contextforge-harness/ssh-tmux-transceiver/contextforge-ssh-wrapper.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_HOST", wrapper)
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_AUTH_MODE", wrapper)
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_PASSWORD", wrapper)
        self.assertIn("sshpass -e", wrapper)
        self.assertIn("SSHPASS=$TARGET_PASSWORD", wrapper)
        self.assertIn("UserKnownHostsFile=$KNOWN_HOSTS", wrapper)
        self.assertIn("StrictHostKeyChecking=$STRICT_HOST_KEY_CHECKING", wrapper)
        self.assertIn("-i \"$PRIVATE_KEY\"", wrapper)

    def test_compose_defines_dev_context7_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/context7-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("context7-transceiver:", compose)
        self.assertIn("contextforge-harness-context7-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9203:9203"', compose)
        self.assertIn("docker/contextforge-harness/context7-transceiver/Dockerfile", compose)
        self.assertIn('CONTEXT7_API_KEY: "${CONTEXT7_API_KEY:-}"', compose)
        self.assertIn("/opt/contextforge-transceiver-venv", dockerfile)
        self.assertIn("@upstash/context7-mcp@latest", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--expose-streamable-http", dockerfile)
        self.assertIn('"9203"', dockerfile)

    def test_compose_defines_exa_search_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/exa-search-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("exa-search-transceiver:", compose)
        self.assertIn("contextforge-harness-exa-search-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9205:9205"', compose)
        self.assertIn("docker/contextforge-harness/exa-search-transceiver/Dockerfile", compose)
        self.assertIn("../../server-instances/exa-search/.env", compose)
        self.assertIn("required: false", compose)
        self.assertIn("server-instances/exa-search/server.py", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--expose-streamable-http", dockerfile)
        self.assertIn('"9205"', dockerfile)

    def test_compose_defines_github_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/github-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("github-transceiver:", compose)
        self.assertIn("contextforge-harness-github-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9206:9206"', compose)
        self.assertIn("docker/contextforge-harness/github-transceiver/Dockerfile", compose)
        self.assertIn("../../server-instances/github/.env", compose)
        self.assertIn("required: false", compose)
        self.assertNotIn("- GITHUB_PERSONAL_ACCESS_TOKEN", compose)
        self.assertIn("mcp-contextforge-gateway", dockerfile)
        self.assertIn("ghcr.io/github/github-mcp-server:v1.4.0@sha256:", dockerfile)
        self.assertIn("COPY --from=github-mcp-server /server/github-mcp-server", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--expose-sse", dockerfile)
        self.assertIn("--expose-streamable-http", dockerfile)
        self.assertIn("--stdio", dockerfile)
        self.assertIn("github-mcp-server stdio", dockerfile)
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN required for github-transceiver", dockerfile)
        self.assertNotIn("@modelcontextprotocol/server-github", dockerfile)
        self.assertNotIn("npm install", dockerfile)
        self.assertNotIn("nodejs", dockerfile)
        self.assertIn("EXPOSE 9206", dockerfile)
        self.assertIn("--port 9206", dockerfile)

    def test_compose_defines_playwright_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/playwright-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("playwright-transceiver:", compose)
        self.assertIn("contextforge-harness-playwright-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9204:9204"', compose)
        self.assertIn("docker/contextforge-harness/playwright-transceiver/Dockerfile", compose)
        self.assertIn("mcr.microsoft.com/playwright:", dockerfile)
        self.assertIn("@playwright/mcp@0.0.76", dockerfile)
        self.assertIn("npm install -g", dockerfile)
        self.assertIn('CMD ["playwright-mcp"', dockerfile)
        self.assertIn("install-browser chrome-for-testing", dockerfile)
        self.assertIn("--browser=chromium", dockerfile)
        self.assertIn("--isolated", dockerfile)
        self.assertIn("--shared-browser-context", dockerfile)
        self.assertIn("--allowed-hosts", dockerfile)
        self.assertIn("localhost:9204,127.0.0.1:9204,playwright-transceiver:9204", dockerfile)
        self.assertIn("9204", dockerfile)

    def test_compose_defines_web_search_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/web-search-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("web-search-transceiver:", compose)
        self.assertIn("contextforge-harness-web-search-transceiver:latest", compose)
        self.assertIn("additional_contexts:", compose)
        self.assertIn("web_search: ../../../web_search", compose)
        self.assertIn('"127.0.0.1:9207:9207"', compose)
        self.assertIn("docker/contextforge-harness/web-search-transceiver/Dockerfile", compose)
        self.assertIn("../../server-instances/web-search/.env", compose)
        self.assertIn("required: false", compose)
        self.assertIn("COPY --from=web_search package.json package-lock.json tsconfig.mcp.json ./", dockerfile)
        self.assertIn("COPY --from=web_search *.ts ./", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--stdio", dockerfile)
        self.assertIn("node /workspace/web_search/dist/mcp-server.js", dockerfile)
        self.assertIn("npm run build", dockerfile)
        self.assertIn("npm prune --omit=dev", dockerfile)
        self.assertIn("9207", dockerfile)

    def test_compose_defines_serena_cf_controlplane_host_proxy(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/serena-host-proxy/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("serena-cf-controlplane-proxy:", compose)
        self.assertIn("contextforge-harness-serena-host-proxy:latest", compose)
        self.assertIn("network_mode: host", compose)
        self.assertIn('SERENA_PROXY_BIND: "172.17.0.1"', compose)
        self.assertIn('SERENA_PROXY_PORT: "9208"', compose)
        self.assertIn('SERENA_TARGET_HOST: "127.0.0.1"', compose)
        self.assertIn('SERENA_TARGET_PORT: "9108"', compose)
        self.assertIn("nc -z 172.17.0.1 9208", compose)
        entrypoint = (ROOT / "docker/contextforge-harness/serena-host-proxy/entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("nginx", dockerfile)
        self.assertIn("serena-host-proxy-entrypoint", dockerfile)
        self.assertIn("listen ${SERENA_PROXY_BIND}:${SERENA_PROXY_PORT}", entrypoint)
        self.assertIn("proxy_pass http://${SERENA_TARGET_HOST}:${SERENA_TARGET_PORT}", entrypoint)
        self.assertIn("proxy_set_header Host ${SERENA_TARGET_HOST}:${SERENA_TARGET_PORT}", entrypoint)
        self.assertIn("proxy_buffering off", entrypoint)

    def test_transceiver_dockerfile_uses_stock_contextforge_translate(self) -> None:
        dockerfile = (ROOT / "docker/contextforge-harness/mcp-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("scripts/governance_mcp.py", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--expose-sse", dockerfile)
        self.assertIn("--expose-streamable-http", dockerfile)
        self.assertIn('"9201"', dockerfile)

    def test_register_script_targets_dev_harness_names_and_network_url(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/register_mentality_dev.py").read_text(encoding="utf-8")

        self.assertIn('GATEWAY_NAME = "mentality-dev-docker"', source)
        self.assertIn('SERVER_NAME = "mentality_dev_docker_server"', source)
        self.assertIn('DEFAULT_UPSTREAM_URL = "http://mentality-transceiver:9201/mcp"', source)
        self.assertIn('DEFAULT_GATEWAY_BASE = "http://127.0.0.1:4445"', source)
        self.assertNotIn("127.0.0.1:4444", source)

    def test_context7_register_script_targets_dev_harness_names_and_network_url(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/register_context7_dev.py").read_text(encoding="utf-8")

        self.assertIn('GATEWAY_NAME = "context7-local"', source)
        self.assertIn('SERVER_NAME = "context7_local_server"', source)
        self.assertIn('DEFAULT_UPSTREAM_URL = "http://context7-transceiver:9203/mcp"', source)
        self.assertIn('DEFAULT_GATEWAY_BASE = "http://127.0.0.1:4445"', source)
        self.assertNotIn("127.0.0.1:4444", source)

    def test_context7_probe_uses_safe_probe_and_revokes_token(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/probe-context7-dev.py").read_text(encoding="utf-8")

        self.assertIn('DEFAULT_DIRECT_URL = "http://127.0.0.1:9203/mcp"', source)
        self.assertIn('"libraryName": "python"', source)
        self.assertIn('"query": "standard library documentation lookup"', source)
        self.assertIn("def create_probe_token", source)
        self.assertIn("def revoke_probe_token", source)
        self.assertIn('print(f"probe_token_id={probe_token_id}")', source)
        self.assertIn("virtual_safe_probe_status=passed", source)
        self.assertIn("terminate_on_close=False", source)
        self.assertNotIn("print(probe_token", source)
        self.assertNotIn("print(access_token", source)

    def test_probe_imports_registration_script_by_filename(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/probe-mentality-dev.py").read_text(encoding="utf-8")

        tree = ast.parse(source)
        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        self.assertIn("register_mentality_dev", imports)
        self.assertIn('DEFAULT_DIRECT_URL = "http://127.0.0.1:9201/mcp"', source)

    def test_probe_uses_ephemeral_catalog_token_for_virtual_mcp(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/probe-mentality-dev.py").read_text(encoding="utf-8")

        self.assertIn("def create_probe_token", source)
        self.assertIn('\"servers.use\"', source)
        self.assertIn('\"expires_in_days\": 1', source)
        self.assertIn("def revoke_probe_token", source)
        self.assertIn('\"DELETE\"', source)
        self.assertIn("terminate_on_close=False", source)
        self.assertIn('print(f\"probe_token_id={probe_token_id}\")', source)
        self.assertNotIn("print(probe_token", source)
        self.assertNotIn("print(access_token", source)

    def test_dockerignore_excludes_local_state_from_root_context(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        for pattern in [
            ".venv/",
            "docker/client-harness/env/semantic-model.env",
            "docker/contextforge-harness/env/contextforge.env",
            "docker/contextforge-harness/evidence/",
            "config/contextforge.env",
            "run/",
            "upstream/",
        ]:
            self.assertIn(pattern, dockerignore)

    def test_client_harness_reset_script_is_idempotent_and_target_scoped(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/reset-client-harness-state.py").read_text(encoding="utf-8")

        self.assertIn('"codex-cli"', source)
        self.assertIn('"pi"', source)
        self.assertIn('"opencode"', source)
        self.assertIn("contextforge-client-harness_codex-cli-home", source)
        self.assertIn("contextforge-client-codex-cli:authenticated", source)
        self.assertIn("authenticated_image_preserved", source)
        self.assertIn("contextforge-client-harness_pi-home", source)
        self.assertIn("contextforge-client-harness_opencode-home", source)
        self.assertIn("workspace-preserved-", source)
        self.assertIn("server-instances-preserved-", source)
        self.assertIn("canonical_project_root", source)
        self.assertIn('"project_scoped_service_reset"', source)
        self.assertIn('"allowlist": [".gitkeep"]', source)
        self.assertIn('"postcondition": entries == [".gitkeep"]', source)
        self.assertIn("--reset-home-volume", source)
        self.assertIn("remaining_target_volume_containers", source)
        self.assertIn("home_volume_absent", source)
        self.assertIn("command_failures", source)
        self.assertIn('"docker", "volume", "inspect"', source)
        self.assertIn("postcondition\": not remaining and not hard_failures and volume_absent", source)
        self.assertNotIn("docker system prune", source)
        self.assertNotIn("docker volume prune", source)

    def test_client_harness_project_init_uses_dev_virtual_server_names(self) -> None:
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        opencode_config = (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8")
        codex_entrypoint = (ROOT / "docker/client-harness/codex-cli/entrypoint.sh").read_text(encoding="utf-8")

        self.assertGreaterEqual(compose.count('CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER: "1"'), 4)
        self.assertIn('"CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER": "1"', opencode_config)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER:=1", codex_entrypoint)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER", codex_entrypoint)

    def test_codex_auth_check_uses_oauth_authenticated_image(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/check-auth-codex.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "docker/client-harness/scripts/run-codex-authenticated.sh").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("scripts/run-codex-authenticated.sh bash -lc", source)
        self.assertIn("codex login status", source)
        self.assertIn("codex doctor --summary --ascii", source)
        self.assertIn("Refusing Codex API-key auth", source)
        self.assertIn("API_KEY|*_API_KEY", source)
        self.assertIn("env_args", launcher)
        self.assertIn("API_KEY|*_API_KEY", launcher)
        self.assertIn("docker compose -f compose.yml run --rm --no-deps", launcher)
        self.assertIn("codex-cli-authenticated", launcher)
        self.assertIn("-e OPENAI_API_KEY=", launcher)
        self.assertIn("-e CODEX_API_KEY=", launcher)
        self.assertIn("-e ANTHROPIC_API_KEY=", launcher)
        self.assertIn("-e OPENROUTER_API_KEY=", launcher)
        self.assertIn("-e GOOGLE_API_KEY=", launcher)
        self.assertIn("-e GEMINI_API_KEY=", launcher)
        self.assertIn("-e PERPLEXITY_API_KEY=", launcher)
        self.assertIn("-e EXA_API_KEY=", launcher)
        self.assertIn("-e CONTEXT7_API_KEY=", launcher)
        self.assertIn('cli_auth_credentials_store = \\"file\\"', source)
        self.assertIn('model = \\"gpt-5.4-mini\\"', source)
        self.assertNotIn("docker compose -f compose.yml run --rm codex-cli bash", source)
        self.assertIn("Codex validation must use this authenticated image, not a raw API key", readme)
        self.assertIn("Host API-key environment variables must not enter the", readme)
        self.assertIn("gpt-5.4-mini", readme)
        self.assertIn("codex exec --json --sandbox read-only --skip-git-repo-check", readme)
        self.assertIn("contextforge-client-codex-cli:authenticated", readme)

    def test_client_normal_use_guidance_routes_docs_without_project_init_continuation(self) -> None:
        pi_source = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")
        opencode_source = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")

        for source in (pi_source, opencode_source):
            self.assertIn("For questions asking how to use the project docs lookup capability", source)
            self.assertIn("relevant docs/library entry", source)
            self.assertIn("concrete docs query through the project-scoped ContextForge docs lookup tool", source)
            self.assertIn("For ordinary docs, library, package, API, or configuration lookup questions", source)
            self.assertIn("call the Context7 resolve-library-id tool first", source)
            self.assertIn("then call the Context7 query-docs tool as needed", source)
        self.assertIn('cf_contextforge_guidance_lookup {"projectRoot"', pi_source)
        self.assertIn("fallback_guidance", pi_source)
        self.assertIn("contextforge-global-shim static fallback guidance", pi_source)
        self.assertIn("asksHowToUseProjectDocsLookupCapability", opencode_source)
        self.assertIn('"chat.message"', opencode_source)
        self.assertIn("projectDocsLookupCapabilityInstruction", opencode_source)
        self.assertIn("Use the project docs lookup capability as a two-step workflow", opencode_source)
        self.assertIn("Ask a concrete configuration question against that entry", opencode_source)
        self.assertIn("Do not call tools, do not add a preface", opencode_source)
        self.assertIn("do not mention internal tool, function, route, or server names", opencode_source)
        self.assertIn('role: "assistant"', opencode_source)
        self.assertIn("Repeat the previous assistant message exactly, with no added text.", opencode_source)
        self.assertNotIn('"tool.execute.before"', opencode_source)
        self.assertNotIn("projectDocsLookupGuidanceGuard", opencode_source)
        self.assertNotIn("Answer this project docs lookup guidance question directly, without tool use.", opencode_source)
        self.assertIn(
            "Do not call cf_project_init_get_context, cf_project_init_continue, cf_project_init_list_capabilities",
            pi_source,
        )
        self.assertIn(
            "Do not call contextforge-helper project-init continuation, availability, capability-summary, or state-readback routes before ordinary Context7 tool use",
            opencode_source,
        )

    def test_client_guidance_routes_explicit_uncataloged_service_onboarding_without_activation(self) -> None:
        pi_source = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")
        opencode_source = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")
        opencode_rules = (ROOT / "docker/client-harness/config/opencode/AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("explicit user requests to onboard or add an uncataloged/new MCP service", pi_source)
        self.assertIn("cf_project_service_onboarding_plan", pi_source)
        self.assertIn("copy assistant_visible_response/message exactly", pi_source)
        self.assertIn("Do not reformat it into tables, expose enum names, add helper fields", pi_source)
        self.assertIn("asksForUncatalogedServiceOnboarding", opencode_source)
        self.assertIn("build_service_onboarding_plan", opencode_source)
        self.assertIn("serviceOnboardingIntakeResponse", opencode_source)
        self.assertIn("serviceOnboardingPlanResponse", opencode_source)
        self.assertIn("produce a no-mutation source-only", opencode_rules)
        self.assertIn("do not restart project initialization", opencode_rules)

    def test_dev_harness_env_allows_compose_network_upstreams(self) -> None:
        env_example = (ROOT / "docker/contextforge-harness/env/contextforge.env.example").read_text(encoding="utf-8")

        self.assertIn("SSRF_ALLOW_PRIVATE_NETWORKS=true", env_example)
        self.assertIn("REQUIRE_USER_IN_DB=false", env_example)

    def test_gateway_preserves_stateful_virtual_mcp_sessions(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn('GUNICORN_WORKERS: "1"', compose)
        self.assertIn('USE_STATEFUL_SESSIONS: "true"', compose)
        self.assertIn('MCP_GET_STREAM_ENABLED: "true"', compose)

    def test_dev_harness_has_env_auth_preflight(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/ensure-env-auth.sh").read_text(encoding="utf-8")
        readme = (ROOT / "docker/contextforge-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("CONTEXTFORGE_DEV_ENV_SYNC_FROM", source)
        self.assertIn("/auth/login", source)
        self.assertIn("install -m 600", source)
        self.assertIn("env_auth_status=passed", source)
        self.assertIn("does not authenticate against the current dev gateway volume", source)
        self.assertIn("scripts/ensure-env-auth.sh", readme)

    def test_mentality_manifest_records_dev_docker_surface(self) -> None:
        manifest = (ROOT / "server-instances/mentality/instance.json").read_text(encoding="utf-8")

        self.assertIn('"compose_service": "mentality-transceiver"', manifest)
        self.assertIn('"compose_streamable_http_url": "http://mentality-transceiver:9201/mcp"', manifest)
        self.assertIn('"gateway_name": "mentality-dev-docker"', manifest)

    def test_compose_keeps_gateway_and_transceiver_as_separate_services(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        service_names = set(re.findall(r"^  ([a-z0-9-]+):$", compose, flags=re.MULTILINE))

        self.assertIn("contextforge-gateway", service_names)
        self.assertIn("mentality-transceiver", service_names)
        self.assertIn("context7-transceiver", service_names)
        self.assertIn("github-transceiver", service_names)
        self.assertIn("exa-search-transceiver", service_names)

    def test_service_locality_records_project_scoped_container_matrix(self) -> None:
        policy = (ROOT / "docker/contextforge-harness/SERVICE_LOCALITY.md").read_text(encoding="utf-8")

        self.assertIn("Project-Scoped MCP Container Matrix", policy)
        self.assertIn("Do not Dockerize every MCP backend by default", policy)
        self.assertIn("Shared canonical services", policy)
        self.assertIn("not project-specific by default", policy)
        self.assertIn("Project-scoped services", policy)
        self.assertIn("reads or writes project-local state", policy)
        self.assertIn("`Serena` is the current clear `instance_per_project` service", policy)
        self.assertIn("server-instances/serena-cf-controlplane-d46fe58a2a20", policy)
        self.assertIn("`project-inspector`", policy)
        self.assertIn("next plausible non-Serena project-scoped proof", policy)
        self.assertIn("explicit runtime approval boundary", policy)
        self.assertIn("Gateway-integrated services", policy)
        self.assertIn("Deferred exception", policy)

    def test_opencode_dev_smoke_uses_ephemeral_contextforge_token(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-opencode-contextforge-dev.sh").read_text(encoding="utf-8")

        self.assertIn("surface=OpenCode client Docker", source)
        self.assertIn("contextforge_surface=ContextForge dev Docker", source)
        self.assertIn("run/test-venvs/project-init-workflow/bin/python", source)
        self.assertIn("CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445", source)
        self.assertIn("CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445", source)
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server", source)
        self.assertIn("opencode mcp add", source)
        self.assertIn("opencode mcp list", source)
        self.assertIn("OPENCODE_SAFE_PROBE_ID", source)
        self.assertIn("OPENCODE_SAFE_PROBE_EXPECTED_TOOL", source)
        self.assertIn("OPENCODE_REQUIRE_SAFE_CALL", source)
        self.assertIn("OPENCODE_SAFE_CALL_COMMAND", source)
        self.assertIn("OPENCODE_SAFE_PROBE_SERVICE=\"${OPENCODE_SAFE_PROBE_SERVICE:-mentality}\"", source)
        self.assertIn("OPENCODE_SAFE_PROBE_ID=\"${OPENCODE_SAFE_PROBE_ID:-governance-list}\"", source)
        self.assertIn("safe_probe_service=%s", source)
        self.assertIn("safe_probe_id=%s", source)
        self.assertIn("safe_call_target_client_visible=false", source)
        self.assertIn("safe_call_target_client_visible=true", source)
        self.assertIn("safe_call_status=not_executed", source)
        self.assertIn("smoke_result=failed_missing_required_safe_call", source)
        self.assertIn("smoke_result=list_only_without_safe_call", source)
        self.assertIn("smoke_result=list_plus_safe_call", source)
        self.assertIn("OPENCODE_SAFE_CALL_COMMAND not set", source)
        self.assertIn("SAFE_CALL_COMMAND_TOOL_ALLOWED", source)
        self.assertIn("safe_call_command_status=rejected_unknown_tool", source)
        self.assertIn("before a scoped token or Docker client run is started", source)
        self.assertIn("mentality-governance-list,mentality-governance-read,governance_list,governance_read", source)
        self.assertIn("redact_token_stream", source)
        self.assertIn("redact-contextforge-secrets.py", source)
        self.assertIn("CONTEXTFORGE_REDACT_VALUES", source)
        self.assertIn("TOKEN_ENV_FILE", source)
        self.assertIn("chmod 0600", source)
        self.assertIn("--env-file \"${TOKEN_ENV_FILE}\"", source)
        self.assertIn("chown -R", source)
        self.assertIn("revoke_probe_token", source)
        self.assertIn("CONTEXTFORGE_DEV_BEARER_TOKEN", source)
        self.assertNotIn('-e CONTEXTFORGE_DEV_BEARER_TOKEN="${ACCESS_TOKEN}"', source)
        self.assertNotIn("127.0.0.1:4444", source)
        self.assertNotIn("/home/dgk/.pi", source)

    def test_client_harness_secret_redactor_redacts_secret_material(self) -> None:
        redactor = ROOT / "docker/client-harness/scripts/redact-contextforge-secrets.py"
        raw = "\n".join(
            [
                "PLATFORM_ADMIN_EMAIL=operator@example.invalid",
                "PLATFORM_ADMIN_PASSWORD=super-secret-password",
                "CONTEXTFORGE_BEARER_TOKEN=cf-secret-token",
                "MCP_BEARER_TOKEN=mcp-secret-token",
                "Authorization=Bearer abcdefghijklmnop",
                '{"access_token": "json-secret-token", "token_id": "tok_public_identifier"}',
                '{"credential_scope": "tenant-a", "credentialBoundary": "provider account", "downstream_credentials": "downstream-secret"}',
                "credential_required=false",
                "probe_token_id=tok_public_identifier",
                "server_id=srv_public_identifier",
            ]
        )

        result = subprocess.run(
            ["python3", str(redactor)],
            input=raw,
            text=True,
            check=True,
            capture_output=True,
        )

        output = result.stdout
        self.assertIn("[REDACTED_CONTEXTFORGE_SECRET]", output)
        self.assertNotIn("super-secret-password", output)
        self.assertNotIn("cf-secret-token", output)
        self.assertNotIn("mcp-secret-token", output)
        self.assertNotIn("abcdefghijklmnop", output)
        self.assertNotIn("json-secret-token", output)
        self.assertNotIn("downstream-secret", output)
        self.assertIn("PLATFORM_ADMIN_EMAIL=operator@example.invalid", output)
        self.assertIn('"credential_scope": "tenant-a"', output)
        self.assertIn('"credentialBoundary": "provider account"', output)
        self.assertIn("credential_required=false", output)
        self.assertIn("probe_token_id=tok_public_identifier", output)
        self.assertIn("server_id=srv_public_identifier", output)

    def test_client_harness_importable_redactor_redacts_nested_values(self) -> None:
        script = """
import json
import os
import sys
sys.path.insert(0, "docker/client-harness/scripts")
from harness_redaction import redact_value
os.environ["CONTEXTFORGE_REDACT_VALUES"] = "explicit-secret-value"
payload = {
    "command_text": "curl -H Authorization=Bearer bearer-secret-token",
    "stdout": {"access_token": "json-secret-token", "credential_scope": "safe"},
    "stderr": ["CONTEXTFORGE_BEARER_TOKEN=explicit-secret-value"],
}
print(json.dumps(redact_value(payload), sort_keys=True))
"""
        result = subprocess.run(
            ["python3", "-c", script],
            cwd=ROOT,
            text=True,
            check=True,
            capture_output=True,
        )

        output = result.stdout
        self.assertIn("[REDACTED_CONTEXTFORGE_SECRET]", output)
        self.assertNotIn("bearer-secret-token", output)
        self.assertNotIn("json-secret-token", output)
        self.assertNotIn("explicit-secret-value", output)
        self.assertIn('"credential_scope": "safe"', output)

    def test_dialogue_evidence_runners_redact_persisted_command_streams(self) -> None:
        for script_name in [
            "run-use-case-1-dialogue.py",
            "run-use-case-2-dialogue.py",
            "run-use-case-3-dialogue.py",
            "run-use-case-4-dialogue.py",
        ]:
            source = (ROOT / "docker/client-harness/scripts" / script_name).read_text(encoding="utf-8")
            self.assertIn("from harness_redaction import", source)
            self.assertIn("redact_text(str(result.get(\"stdout\") or \"\"))", source)
            self.assertIn("redact_text(str(result.get(\"stderr\") or \"\"))", source)
            self.assertIn("redact_text(str(result['command_text']))", source)
            self.assertIn("redact_value(reset_json)", source)
            self.assertIn("\"commands\": redact_value(commands)", source)

    def test_dialogue_runners_use_model_env_variables_not_static_model_fallbacks(self) -> None:
        defaults = (ROOT / "docker/client-harness/scripts/client_model_defaults.py").read_text(encoding="utf-8")

        self.assertIn('--provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}"', defaults)
        self.assertIn('--model "${CONTEXTFORGE_PI_DEFAULT_MODEL}"', defaults)
        self.assertIn("return \"${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}\"", defaults)
        self.assertNotIn("openrouter-gemini-flash-lite", defaults)
        self.assertNotIn("google/gemini-2.5-flash-lite", defaults)

    def test_comprehensive_mcp_runner_uses_natural_prompt_and_separate_inventory(self) -> None:
        runner = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py").read_text(
            encoding="utf-8"
        )
        services = json.loads((ROOT / "docker/client-harness/comprehensive-mcp-testing-services.json").read_text(encoding="utf-8"))

        self.assertIn("Please use this project's documentation lookup capability", runner)
        self.assertIn("MENTALITY_FIXTURE_TASK_ID", runner)
        self.assertIn("Please check the details recorded for task", runner)
        self.assertIn("Please inspect this project's active terminal session", runner)
        self.assertIn("report the visible terminal screen", runner)
        self.assertIn("TASKS.md", runner)
        self.assertTrue(all("service_binding" in service for service in services["services"]))
        self.assertIn("SEMANTIC_MODEL_OVERRIDE_KEYS", runner)
        self.assertIn("semantic_model_env_overrides", runner)
        self.assertIn("-e", runner)
        self.assertIn('"semantic_model_env_overrides": semantic_overrides', runner)
        self.assertIn("activation_postcondition_command", runner)
        self.assertIn("activation-postcondition.raw.txt", runner)
        self.assertIn('"activation_postcondition"', runner)
        self.assertIn('"service_test_executed": service_test_executed', runner)
        self.assertIn('activation_postcondition["returncode"] == 0', runner)
        self.assertIn('"service_fixture": service_fixture', runner)
        self.assertIn("What ContextForge tools are available in this project?", runner)
        self.assertIn('"tool_inventory": tool_inventory', runner)
        self.assertIn("tool-inventory-turn.raw.txt", runner)
        self.assertNotIn("resolve the library id first, then look up documentation", runner)
        self.assertNotIn("Context7 functions used", runner)

    def test_opencode_mentality_guidance_routes_ordinary_governance_tasks(self) -> None:
        guidance = (ROOT / "docker/client-harness/config/opencode/AGENTS.md").read_text(encoding="utf-8")
        guidance_wrapped = " ".join(guidance.split())

        self.assertIn("asks about recorded project tasks", guidance_wrapped)
        self.assertIn("first identify it from the relevant ledger", guidance_wrapped)
        self.assertIn("prefer the tasks ledger", guidance_wrapped)
        self.assertIn("exact current project root path", guidance_wrapped)
        self.assertIn("/workspace", guidance_wrapped)
        self.assertIn("substitute helper availability", guidance_wrapped)
        self.assertIn("Do not end with an empty assistant message", guidance_wrapped)
        self.assertIn("for a requested governance/mentality task", guidance_wrapped)

    def test_opencode_governance_hook_supports_read_route_without_task_interception(self) -> None:
        plugin = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('lowered.includes("task")', plugin)
        self.assertIn("governancePromptRequestsSpecificEntry", plugin)
        self.assertIn("mentality_governance_read", plugin)
        self.assertIn("governance_read", plugin)
        self.assertIn('"id":"ENTRY_ID_FROM_THE_USER_OR_LIST_RESULT"', plugin)
        self.assertIn("If the user only asks for a list or status summary", plugin)
        self.assertIn("produce a visible final answer", plugin)
        self.assertIn("Do not stop with an empty assistant message", plugin)
        self.assertNotIn("Do not use read, glob, grep", plugin)

    def test_pi_availability_readback_passes_live_runtime_tools_to_helper(self) -> None:
        pi_source = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")
        cli_source = (ROOT / "scripts/pi_project_init_helper_cli.py").read_text(encoding="utf-8")
        helper_source = (ROOT / "scripts/contextforge_helper_mcp.py").read_text(encoding="utf-8")

        self.assertIn('item.operation === "get_project_tool_availability"', pi_source)
        self.assertIn("payload.target_client_runtime = readbackSnapshot()", pi_source)
        self.assertIn("function readbackSnapshot()", pi_source)
        self.assertIn('target_client_runtime=data.get("target_client_runtime")', cli_source)
        self.assertIn("target_client_runtime: Mapping[str, Any] | None = None", helper_source)
        self.assertIn("tools_registered_observed", helper_source)

    def test_later_dialogue_runners_redact_custom_command_renderers(self) -> None:
        script = r'''
import importlib.util
import json
import os
import sys
from pathlib import Path

root = Path("docker/client-harness/scripts")
sys.path.insert(0, str(root.resolve()))
os.environ["CONTEXTFORGE_REDACT_VALUES"] = "explicit-secret-value"

def load(name):
    path = root / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

payload = {
    "command_text": "curl -H Authorization=Bearer bearer-secret-token CONTEXTFORGE_BEARER_TOKEN=explicit-secret-value",
    "command": ["curl", "Authorization=Bearer", "bearer-secret-token"],
    "cwd": "/workspace",
    "returncode": 0,
    "timeout": False,
    "stdout": "{\"access_token\":\"json-secret-token\",\"credential_scope\":\"safe\"}",
    "stderr": "MCP_BEARER_TOKEN=explicit-secret-value",
}

outputs = [
    load("run-use-case-9-dialogue.py").command_block(payload),
    load("run-use-case-10-dialogue.py").command_block(payload),
    load("run-use-case-12-dialogue.py").uc_render(payload),
]
print(json.dumps(outputs))
'''
        result = subprocess.run(
            ["python3", "-c", script],
            cwd=ROOT,
            text=True,
            check=True,
            capture_output=True,
        )

        output = result.stdout
        self.assertIn("[REDACTED_CONTEXTFORGE_SECRET]", output)
        self.assertNotIn("bearer-secret-token", output)
        self.assertNotIn("explicit-secret-value", output)
        self.assertNotIn("json-secret-token", output)
        self.assertIn("credential_scope", output)

    def test_later_dialogue_runners_route_persisted_json_through_redaction(self) -> None:
        for script_name in [
            "run-use-case-6-dialogue.py",
            "run-use-case-7-dialogue.py",
            "run-use-case-8-dialogue.py",
            "run-use-case-9-dialogue.py",
            "run-use-case-10-dialogue.py",
            "run-use-case-11-dialogue.py",
            "run-use-case-12-dialogue.py",
            "run-use-case-14-readiness-report.py",
            "run-use-case-15-handoff.py",
        ]:
            source = (ROOT / "docker/client-harness/scripts" / script_name).read_text(encoding="utf-8")
            self.assertIn("from harness_redaction import", source, msg=script_name)
            self.assertIn("redact_value(", source, msg=script_name)

    def test_source_evidence_runners_redact_metadata_and_command_streams(self) -> None:
        for path in sorted((ROOT / "docker/client-harness/scripts").glob("run-use-case-5[a-l]-*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertIn("from harness_redaction import redact_text, redact_value", source, msg=str(path))
            self.assertIn("redact_text(str(item['command_text']))", source, msg=str(path))
            self.assertIn("redact_text(str(item.get(\"stdout\") or \"\"))", source, msg=str(path))
            self.assertIn("redact_text(str(item.get(\"stderr\") or \"\"))", source, msg=str(path))
            self.assertIn("redact_text(item['command_text'])", source, msg=str(path))
            self.assertIn("metadata = redact_value(metadata)", source, msg=str(path))

    def test_controlled_dev_runner_redacts_metadata_and_ledger_package(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from harness_redaction import redact_value", source)
        self.assertIn("safe_metadata = redact_value(metadata)", source)
        self.assertIn("ledger = redact_value(ledger)", source)
        self.assertIn("json.dumps(safe_metadata", source)

    def test_client_harness_redaction_guidance_covers_all_active_clients(self) -> None:
        opencode_rules = (ROOT / "docker/client-harness/config/opencode/AGENTS.md").read_text(encoding="utf-8")
        pi_rules = (ROOT / "docker/client-harness/config/pi/AGENTS.md").read_text(encoding="utf-8")
        codex_entrypoint = (ROOT / "docker/client-harness/codex-cli/entrypoint.sh").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")
        method = (ROOT / "docker/client-harness/DIALOGUE_EVALUATION_METHOD.md").read_text(encoding="utf-8")
        uc1_gate = (ROOT / "docker/client-harness/USE_CASE_1_E2E_GATE.md").read_text(encoding="utf-8")

        for source in (opencode_rules, pi_rules, codex_entrypoint, readme, method, uc1_gate):
            normalized = source.lower()
            self.assertIn("raw", normalized)
            self.assertIn("env", normalized)
            self.assertIn("credential", normalized)
            self.assertIn("redact-contextforge-secrets.py", source)

    def test_contextforge_dev_smokes_route_output_through_shared_redactor(self) -> None:
        for script_name in [
            "smoke-opencode-contextforge-dev.sh",
            "smoke-pi-contextforge-dev.sh",
            "smoke-codex-contextforge-dev.sh",
        ]:
            source = (ROOT / "docker/client-harness/scripts" / script_name).read_text(encoding="utf-8")
            self.assertIn("redact-contextforge-secrets.py", source)
            self.assertIn("tee -a", source)

    def test_pi_image_provisions_container_local_contextforge_wrapper_runtime(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/pi/Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("python3-venv", dockerfile)
        self.assertIn("/opt/contextforge-wrapper-venv", dockerfile)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON", dockerfile)
        self.assertIn("/opt/contextforge-wrapper-venv/bin/python", dockerfile)
        self.assertIn("contextforge-pi-bootstrap.sh", dockerfile)
        self.assertIn("pi-wrapper.sh", dockerfile)
        self.assertIn("CONTEXTFORGE_PI_REAL_BIN=/usr/bin/pi", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)

    def test_pi_image_wraps_bare_pi_for_interactive_harness_sessions(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/pi/Dockerfile").read_text(encoding="utf-8")
        wrapper = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        bootstrap = (ROOT / "docker/client-harness/pi/contextforge-pi-bootstrap.sh").read_text(encoding="utf-8")

        self.assertIn("COPY --chown=agent:agent pi-wrapper.sh /usr/local/bin/pi", dockerfile)
        self.assertIn(": \"${CONTEXTFORGE_PI_REAL_BIN:=/usr/bin/pi}\"", wrapper)
        self.assertIn(": \"${CONTEXTFORGE_PI_DEFAULT_PROVIDER:=openrouter-gemini-flash-lite}\"", wrapper)
        self.assertIn(": \"${CONTEXTFORGE_PI_DEFAULT_MODEL:=${OPENROUTER_MODEL:-google/gemini-2.5-flash-lite}}\"", wrapper)
        self.assertIn(". /usr/local/bin/contextforge-pi-bootstrap", wrapper)
        self.assertIn("default_args+=(--provider \"${CONTEXTFORGE_PI_DEFAULT_PROVIDER}\")", wrapper)
        self.assertIn("default_args+=(--model \"${CONTEXTFORGE_PI_DEFAULT_MODEL}\")", wrapper)
        self.assertIn("exec \"${CONTEXTFORGE_PI_REAL_BIN}\"", wrapper)
        self.assertIn('cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"', bootstrap)
        self.assertIn('source = Path("/config/pi/models.json")', bootstrap)
        self.assertIn('provider["baseUrl"] = os.environ["OPENROUTER_BASE_URL"]', bootstrap)
        self.assertIn('provider["apiKey"] = os.environ["OPENROUTER_API_KEY"]', bootstrap)
        self.assertIn('os.environ.get("OPENROUTER_PROVIDER_ROUTES", "")', bootstrap)
        self.assertIn('provider["compat"].pop("openRouterRouting", None)', bootstrap)
        self.assertIn("Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR", bootstrap)
        self.assertNotIn("/home/dgk/.pi", dockerfile + wrapper + bootstrap)

    def test_pi_shim_clarifies_ssh_tmux_session_list_results(self) -> None:
        shim = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")

        self.assertIn("function importedToolDescription", shim)
        self.assertIn('non-empty result lines such as "- bash" are active session IDs', shim)
        self.assertIn("call the ssh-tmux get-snapshot tool with that session_id", shim)
        self.assertIn("async function normalizeSshTmuxToolResult", shim)
        self.assertIn("await route.client.callTool(snapshotName", shim)
        self.assertIn("ssh-tmux active sessions:", shim)
        self.assertIn("- session_id: ${sessionId}", shim)
        self.assertIn("Visible terminal screen for session_id ${firstSessionId}:", shim)

    def test_pi_and_opencode_default_to_openrouter_semantic_model_profile(self) -> None:
        pi_models = json.loads((ROOT / "docker/client-harness/config/pi/models.json").read_text(encoding="utf-8"))
        opencode_config = json.loads((ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8"))
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        opencode_entrypoint = (ROOT / "docker/client-harness/opencode/entrypoint.sh").read_text(encoding="utf-8")
        env_example = (ROOT / "docker/client-harness/env/semantic-model.env.example").read_text(encoding="utf-8")

        self.assertIn("./env/semantic-model.env", compose)
        self.assertIn("OPENROUTER_API_KEY=replace-with-openrouter-secret", env_example)
        self.assertIn("CONTEXTFORGE_TEST_MODEL=google/gemini-2.5-flash-lite", env_example)
        self.assertIn("CONTEXTFORGE_TEST_PROVIDER_ROUTE=google-ai-studio", env_example)
        self.assertIn("OPENROUTER_PROVIDER_ROUTES=google-ai-studio", env_example)
        self.assertIn("OPENROUTER_STICKY_KEY=contextforge-semantic-test", env_example)
        self.assertIn("OPENROUTER_STICKY_EPOCH_SECONDS=7200", env_example)

        pi_provider = pi_models["providers"]["openrouter-gemini-flash-lite"]
        self.assertEqual("$OPENROUTER_BASE_URL", pi_provider["baseUrl"])
        self.assertEqual("$OPENROUTER_API_KEY", pi_provider["apiKey"])
        self.assertEqual("$OPENROUTER_STICKY_KEY", pi_provider["headers"]["x-session-id"])
        self.assertNotIn("cacheControlFormat", pi_provider["compat"])
        self.assertEqual(["google-ai-studio"], pi_provider["compat"]["openRouterRouting"]["only"])
        self.assertEqual(["google-ai-studio"], pi_provider["compat"]["openRouterRouting"]["order"])
        self.assertFalse(pi_provider["compat"]["openRouterRouting"]["allow_fallbacks"])
        self.assertEqual("google/gemini-2.5-flash-lite", pi_provider["models"][0]["id"])

        self.assertEqual("{env:CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}", opencode_config["model"])
        openrouter_provider = opencode_config["provider"]["openrouter"]
        self.assertNotIn("options", openrouter_provider)
        self.assertEqual({}, openrouter_provider["models"])
        opencode_dockerfile = (ROOT / "docker/client-harness/opencode/Dockerfile").read_text(encoding="utf-8")
        opencode_renderer = (ROOT / "docker/client-harness/opencode/render-config.py").read_text(encoding="utf-8")
        self.assertIn("contextforge-opencode-render-config", opencode_dockerfile)
        self.assertNotIn("contextforge-opencode-real", opencode_dockerfile)
        self.assertIn("OPENROUTER_STICKY_EPOCH_SECONDS", opencode_renderer)
        self.assertIn('return f"{base}-e{bucket}"', opencode_renderer)
        self.assertIn(
            'model_id = openrouter_model_component(os.environ.get("OPENROUTER_OPENCODE_MODEL", "google/gemini-2.5-flash-lite"))',
            opencode_renderer,
        )
        self.assertIn(
            'os.environ.get("OPENROUTER_PROVIDER_ROUTES", "")',
            opencode_renderer,
        )
        self.assertIn(
            'data["model"] = opencode_model_id(os.environ.get("CONTEXTFORGE_OPENCODE_DEFAULT_MODEL"), model_id)',
            opencode_renderer,
        )
        self.assertNotIn("setCacheKey", opencode_renderer)
        self.assertIn('"only": routes', opencode_renderer)
        self.assertIn('"order": routes', opencode_renderer)
        self.assertIn('"allow_fallbacks": False', opencode_renderer)
        self.assertIn('"x-session-id": effective_sticky_key()', opencode_renderer)
        self.assertIn('data["openrouter"] = {"type": "api", "key": os.environ["OPENROUTER_API_KEY"]}', opencode_renderer)
        self.assertIn("target.chmod(0o600)", opencode_renderer)

    def test_semantic_model_profiles_are_provider_abstract_and_run_scoped(self) -> None:
        profiles_doc = json.loads((ROOT / "docker/client-harness/semantic-model-profiles.json").read_text(encoding="utf-8"))
        runner = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py").read_text(encoding="utf-8")
        models = {profile["model"]: profile for profile in profiles_doc["profiles"]}

        self.assertEqual("per_test_run", profiles_doc["selection_scope"])
        self.assertEqual("random", profiles_doc["default_selection_mode"])
        self.assertIn("google/gemini-2.5-flash-lite", models)
        self.assertIn("google/gemma-4-26b-a4b-it", models)
        self.assertIn("nvidia/nemotron-3-super-120b-a12b:free", models)
        self.assertIn("xiaomi/mimo-v2.5", models)
        self.assertIn("openrouter/owl-alpha", models)
        self.assertIn("qwen/qwen3-coder-next", models)
        self.assertIn("tencent/hy3-preview", models)
        self.assertIn("deepseek/deepseek-v4-flash", models)
        self.assertNotIn("google/gemini-2.5-flash", models)
        self.assertNotIn("google/gemini-2.5-pro", models)
        self.assertNotIn("qwen3.6-a3b", models)
        self.assertEqual(["google-ai-studio"], models["google/gemini-2.5-flash-lite"]["route_preferences"])
        self.assertFalse(models["google/gemini-2.5-flash-lite"]["multi_step_quorum_eligible"])
        self.assertIn("single_shot", models["google/gemini-2.5-flash-lite"]["usage_modes"])
        self.assertEqual([], models["qwen/qwen3-coder-next"]["route_preferences"])
        for profile in profiles_doc["profiles"]:
            self.assertIn("provider_kind", profile)
            self.assertIn("api_key_env", profile)
            self.assertIn("base_url_env", profile)
            self.assertGreaterEqual(profile["context_window"], 262144)
            self.assertIsInstance(profile["route_preferences"], list)

        self.assertIn("--semantic-model-profile", runner)
        self.assertIn('if selector == "random"', runner)
        self.assertIn("profile_multi_step_quorum_eligible(profile)", runner)
        self.assertIn("random.choices", runner)
        self.assertIn("MIN_SEMANTIC_CONTEXT_WINDOW = 262144", runner)
        self.assertIn("profile_context_window(profile) >= MIN_SEMANTIC_CONTEXT_WINDOW", runner)
        self.assertIn("route_preferences(profile)", runner)
        self.assertIn('env["OPENROUTER_PROVIDER_ROUTE"] = ""', runner)
        self.assertIn('else "openrouter"', runner)
        self.assertIn('"selection_scope": "per_test_run"', runner)
        self.assertIn('"minimum_context_window"', runner)
        self.assertIn('"api_key_present"', runner)
        self.assertIn('launch_command.extend(["-e", key])', runner)
        self.assertNotIn('launch_command.extend(["-e", f"{key}={os.environ[key]}"])', runner)

    def test_flash_lite_is_explicit_only_for_multi_step_quorum(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profiles = module.load_semantic_model_profiles(ROOT / "docker/client-harness")
        by_model = {profile["model"]: profile for profile in profiles}
        flash_lite = by_model["google/gemini-2.5-flash-lite"]

        self.assertFalse(module.profile_multi_step_quorum_eligible(flash_lite))
        explicit = module.choose_semantic_model_profile(
            ROOT / "docker/client-harness",
            "pi",
            "openrouter-google-gemini-2.5-flash-lite-google-ai-studio",
            {"OPENROUTER_API_KEY": "present"},
        )
        random_candidates = [
            profile
            for profile in profiles
            if module.profile_supports_client(profile, "pi")
            and module.profile_available(profile, {"OPENROUTER_API_KEY": "present"})
            and module.profile_context_window(profile) >= module.MIN_SEMANTIC_CONTEXT_WINDOW
            and module.profile_weight(profile) > 0
            and module.profile_multi_step_quorum_eligible(profile)
        ]

        self.assertEqual(flash_lite["id"], explicit["id"])
        self.assertNotIn(flash_lite["id"], {profile["id"] for profile in random_candidates})

    def test_pi_openrouter_profiles_without_route_use_generic_provider(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        routed_env, _ = module.selected_profile_env(
            {
                "id": "routed",
                "provider_kind": "openrouter",
                "provider_label": "OpenRouter",
                "model": "google/gemini-2.5-flash-lite",
                "display_name": "Gemini routed",
                "context_window": 1048576,
                "api_key_env": "OPENROUTER_API_KEY",
                "base_url_env": "OPENROUTER_BASE_URL",
                "route_preferences": ["google-ai-studio"],
            },
            "pi",
            {},
        )
        unrouted_env, _ = module.selected_profile_env(
            {
                "id": "unrouted",
                "provider_kind": "openrouter",
                "provider_label": "OpenRouter",
                "model": "qwen/qwen3-coder-next",
                "display_name": "Qwen via OpenRouter",
                "context_window": 262144,
                "api_key_env": "OPENROUTER_API_KEY",
                "base_url_env": "OPENROUTER_BASE_URL",
                "route_preferences": [],
            },
            "pi",
            {"CONTEXTFORGE_PI_DEFAULT_PROVIDER": "openrouter-gemini-flash-lite"},
        )

        self.assertEqual("openrouter-gemini-flash-lite", routed_env["CONTEXTFORGE_PI_DEFAULT_PROVIDER"])
        self.assertEqual("openrouter", unrouted_env["CONTEXTFORGE_PI_DEFAULT_PROVIDER"])
        self.assertEqual("", unrouted_env["OPENROUTER_PROVIDER_ROUTES"])
        self.assertEqual("", unrouted_env["OPENROUTER_PROVIDER_ROUTE"])

    def test_comprehensive_mcp_semantic_tests_require_three_model_quorum(self) -> None:
        skill = (ROOT / ".codex/skills/comprehensive-mcp-testing/SKILL.md").read_text(encoding="utf-8")
        method = (ROOT / ".codex/skills/comprehensive-mcp-testing/references/method.md").read_text(
            encoding="utf-8"
        )
        quorum_runner = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-model-quorum.py").read_text(
            encoding="utf-8"
        )
        skill_line_wrapped = " ".join(skill.split())
        method_line_wrapped = " ".join(method.split())
        profiles = json.loads((ROOT / "docker/client-harness/semantic-model-profiles.json").read_text(encoding="utf-8"))[
            "profiles"
        ]

        self.assertGreaterEqual(len(profiles), 3)
        for phrase in [
            "at least three distinct eligible semantic-test model profiles",
            "A one-model pass is useful slice evidence, not a test pass",
            "The quorum is about model diversity over the same behavior",
        ]:
            self.assertIn(phrase, skill_line_wrapped)
        for phrase in [
            "`model_quorum`",
            "Single-profile runs are model-slice evidence only",
            "A test with one or two passing profiles is `quorum_incomplete`, not passed",
            "The three-model quorum does not permit deterministic prose scoring",
            "run-comprehensive-mcp-model-quorum.py",
            "does not score semantic pass/fail",
        ]:
            self.assertIn(phrase, method_line_wrapped)
        for phrase in [
            "MIN_MODEL_QUORUM = 3",
            "semantic_acceptance",
            "requires_non_spark_evaluator_per_model_and_quorum",
            "quorum_run_incomplete",
            "ready_for_evaluator",
            "quorum runner does not score free-form assistant prose",
            "varies only semantic model profile across runs",
        ]:
            self.assertIn(phrase, quorum_runner)

    def test_opencode_renderer_normalizes_accidental_home_marker_in_model_env(self) -> None:
        renderer_path = ROOT / "docker/client-harness/opencode/render-config.py"
        spec = importlib.util.spec_from_file_location("contextforge_opencode_render_config_test", renderer_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "opencode.source.json"
            target = root / "opencode.json"
            source.write_text(
                json.dumps(
                    {
                        "$schema": "https://opencode.ai/config.json",
                        "model": "{env:CONTEXTFORGE_OPENCODE_DEFAULT_MODEL}",
                        "provider": {"openrouter": {"models": {}}},
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "CONTEXTFORGE_OPENCODE_CONFIG_SOURCE": str(source),
                "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(target),
                "OPENROUTER_OPENCODE_MODEL": "~google/gemini-2.5-flash-lite",
                "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "openrouter/~google/gemini-2.5-flash-lite",
            }
            with unittest.mock.patch.dict(os.environ, env, clear=False):
                module.render_config()

            data = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual("openrouter/google/gemini-2.5-flash-lite", data["model"])
        self.assertEqual(["google/gemini-2.5-flash-lite"], list(data["provider"]["openrouter"]["models"]))

    def test_opencode_image_provisions_container_local_contextforge_helper_runtime(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/opencode/Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("python3-venv", dockerfile)
        self.assertIn("/opt/contextforge-helper-venv", dockerfile)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON=/opt/contextforge-helper-venv/bin/python", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)
        self.assertIn("CONTEXTFORGE_HELPER_SCRIPT: /repo/scripts/contextforge_helper_mcp.py", compose)

    def test_codex_image_provisions_container_local_contextforge_helper_runtime(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/codex-cli/Dockerfile").read_text(encoding="utf-8")
        entrypoint = (ROOT / "docker/client-harness/codex-cli/entrypoint.sh").read_text(encoding="utf-8")
        hook = (ROOT / "docker/client-harness/codex-cli/contextforge-codex-project-init-hook").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("python3-venv", dockerfile)
        self.assertIn("/opt/contextforge-helper-venv", dockerfile)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("contextforge-codex-entrypoint", dockerfile)
        self.assertIn("contextforge-codex-project-init-hook", dockerfile)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON=/opt/contextforge-helper-venv/bin/python", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)
        self.assertIn("CONTEXTFORGE_HELPER_SCRIPT: /repo/scripts/contextforge_helper_mcp.py", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_SCRIPT: /repo/scripts/contextforge_mcp_wrapper.py", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV: /run/contextforge-client-scoped/contextforge.env", compose)
        self.assertIn("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH: /home/agent/.local/state/contextforge-client-harness-runtime/project-init/codex-latest-user-message.json", compose)
        self.assertIn("CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT: \"1\"", compose)
        self.assertIn("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH: /home/agent/.local/state/contextforge-client-harness-runtime/project-init/pi-latest-user-message.json", compose)
        self.assertIn("CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE: codex", compose)
        self.assertIn("../..:/repo:ro", compose)
        self.assertIn("./client-scoped:/run/contextforge-client-scoped:ro", compose)
        self.assertIn('[mcp_servers.contextforge-helper]', entrypoint)
        self.assertIn('[[hooks.SessionStart]]', entrypoint)
        self.assertIn('[[hooks.UserPromptSubmit]]', entrypoint)
        self.assertIn('model = "gpt-5.4-mini"', entrypoint)
        self.assertIn('^model[[:space:]]*=', entrypoint)
        self.assertIn("replaced = 1", entrypoint)
        self.assertIn("API_KEY|*_API_KEY", entrypoint)
        self.assertIn("codex_project_init_hook.py", hook)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env", hook)

    def test_pi_dev_smoke_uses_shim_against_dev_gateway(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-pi-contextforge-dev.sh").read_text(encoding="utf-8")

        self.assertIn("surface=Pi client Docker", source)
        self.assertIn("contextforge_surface=ContextForge dev Docker", source)
        self.assertIn("run/test-venvs/project-init-workflow/bin/python", source)
        self.assertIn("CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445", source)
        self.assertIn("CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445", source)
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server", source)
        self.assertIn("cf_contextforge_pi_readback", source)
        self.assertNotIn("cf_contextforge_pi_validate", source)
        self.assertIn("pi-extensions/contextforge-global-shim/index.ts", source)
        self.assertIn("CONTEXTFORGE_SERVER_ID", source)
        self.assertIn("CONTEXTFORGE_BEARER_TOKEN", source)
        self.assertIn("TOKEN_ENV_FILE", source)
        self.assertIn("chmod 0600", source)
        self.assertIn("--env-file \"${TOKEN_ENV_FILE}\"", source)
        self.assertNotIn('-e CONTEXTFORGE_BEARER_TOKEN="${ACCESS_TOKEN}"', source)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python", source)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env", source)
        self.assertIn("CONTEXTFORGE_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json", source)
        self.assertIn("revoke_probe_token", source)
        self.assertIn("probe_token_revoked", source)
        self.assertIn("workspace/.project/context_forge_state.json", source)
        self.assertNotIn("127.0.0.1:4444", source)
        self.assertNotIn("/home/dgk/.pi", source)

    def test_pi_context7_dev_smoke_uses_context7_safe_probe(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-pi-context7-dev.sh").read_text(encoding="utf-8")

        self.assertIn("surface=Pi client Docker", source)
        self.assertIn("contextforge_surface=ContextForge dev Docker", source)
        self.assertIn("run/test-venvs/project-init-workflow/bin/python", source)
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-context7_local_server", source)
        self.assertIn("register_context7_dev", source)
        self.assertIn("probe-context7-dev.py", source)
        self.assertIn("context7:canonical", source)
        self.assertIn("cf_contextforge_pi_readback", source)
        self.assertIn("pi_readback_status=passed", source)
        self.assertNotIn("cf_contextforge_pi_validate", source)
        self.assertIn("CONTEXTFORGE_SERVER_ID", source)
        self.assertIn("CONTEXTFORGE_BEARER_TOKEN", source)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python", source)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env", source)
        self.assertIn("revoke_probe_token", source)
        self.assertIn("probe_token_revoked", source)
        self.assertIn("redact_token_stream", source)
        self.assertIn("redact-contextforge-secrets.py", source)
        self.assertIn("CONTEXTFORGE_REDACT_VALUES", source)
        self.assertIn("| redact_token_stream | tee -a", source)
        self.assertNotIn("mktemp \"${ROOT}/evidence", source)
        self.assertIn("workspace/.project/context_forge_state.json", source)
        self.assertNotIn("127.0.0.1:4444", source)
        self.assertNotIn("/home/dgk/.pi", source)

    def test_client_helper_baseline_contract_records_issue_62_gap(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("Issue #62 identified a real gap", contract)
        self.assertIn("ordinary ad hoc client sessions", contract)
        self.assertIn("specialized ContextForge smoke flows", contract)
        self.assertIn("docker/client-harness/scripts/smoke-pi-contextforge-dev.sh", contract)
        self.assertIn("docker/client-harness/scripts/smoke-opencode-contextforge-dev.sh", contract)
        self.assertIn("CONTEXTFORGE_HELPER_BASELINE.md", readme)

    def test_client_helper_baseline_contract_limits_surface_and_mutations(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")

        self.assertIn("Pi client Docker", contract)
        self.assertIn("OpenCode client Docker", contract)
        self.assertIn("generated semantic-test model profile", contract)
        self.assertIn("ContextForge development Docker surface", contract)
        self.assertIn("Codex CLI, Claude Code, and Gemini CLI client expansion", contract)
        self.assertIn("Host Pi install, host Pi reload, or user-global Pi extension mutation", contract)
        self.assertIn("Host user-global OpenCode config or plugin mutation", contract)
        self.assertIn("Legacy/live ContextForge registry, token, service, or process mutation", contract)
        self.assertIn("Runtime Docker rebuild/run proof", contract)

    def test_client_helper_baseline_contract_defines_pi_and_opencode_routes(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")

        self.assertIn("Pi remains shim-first", contract)
        self.assertIn("scripts/start-pi-contextforge-baseline.sh", contract)
        self.assertIn("config/pi/start-contextforge-baseline.sh", contract)
        self.assertIn("pi-extensions/contextforge-global-shim/index.ts", contract)
        self.assertIn("cf_project_init_*", contract)
        self.assertIn("container-local Pi extension directory", contract)
        self.assertIn("avoid host Pi installs, host `/reload`, or host/global Pi state mutation", contract)
        self.assertIn("Container-local writes under `/home/agent/.pi/agent/extensions` are harness", contract)
        self.assertIn("normal container-user global OpenCode plugin surface", contract)
        self.assertIn("contextforge-helper", contract)
        self.assertIn("container-local Python environment", contract)
        self.assertIn("scripts/start-opencode-contextforge-baseline.sh", contract)
        self.assertIn("config/opencode/start-contextforge-baseline.sh", contract)
        self.assertIn("config/opencode/plugins/contextforge-project-init.js", contract)
        self.assertIn("docker/client-harness/config/opencode", contract)
        self.assertIn("scripts/opencode_project_init_hook.py", contract)
        self.assertIn("/home/agent/.config/opencode/plugins/contextforge-project-init.js", contract)
        self.assertIn("Approved selected MCP services remain", contract)
        self.assertIn("project-local in `opencode.json` plus `.project/context_forge_state.json`", contract)
        self.assertIn("avoid host user-global OpenCode config or plugin writes", contract)

    def test_client_helper_baseline_compose_mounts_repo_only_for_pi_and_opencode(self) -> None:
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE: /config/opencode/plugins/contextforge-project-init.js", compose)
        self.assertIn("CODEX_HOME: /home/agent/.codex", compose)
        self.assertIn('OPENAI_API_KEY: ""', compose)
        self.assertIn('CODEX_API_KEY: ""', compose)
        self.assertIn('ANTHROPIC_API_KEY: ""', compose)
        self.assertIn('OPENROUTER_API_KEY: ""', compose)
        self.assertIn('GOOGLE_API_KEY: ""', compose)
        self.assertIn('GEMINI_API_KEY: ""', compose)
        self.assertIn('PERPLEXITY_API_KEY: ""', compose)
        self.assertIn('EXA_API_KEY: ""', compose)
        self.assertIn('CONTEXT7_API_KEY: ""', compose)
        self.assertIn("OPENCODE_CONFIG: /home/agent/.config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_SOURCE: /config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_TARGET: /home/agent/.config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET: /home/agent/.config/opencode/plugins/contextforge-project-init.js", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK: /repo/scripts/opencode_project_init_hook.py", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_SCRIPT: /repo/scripts/contextforge_mcp_wrapper.py", compose)
        self.assertIn("CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV: /run/contextforge-client-scoped/contextforge.env", compose)
        self.assertIn(
            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT: /home/agent/.local/state/contextforge-client-harness-runtime/project-init",
            compose,
        )
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn(
            "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH: /home/agent/.local/state/contextforge-client-harness-runtime/project-init/opencode-latest-user-message.json",
            compose,
        )
        self.assertIn("CONTEXTFORGE_HELPER_SCRIPT: /repo/scripts/contextforge_helper_mcp.py", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_EXTENSION: /repo/pi-extensions/contextforge-global-shim/index.ts", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_INSTALL_DIR: /home/agent/.pi/agent/extensions/contextforge-global-shim", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WRAPPER: /repo/scripts/contextforge_mcp_wrapper.py", compose)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV: /run/contextforge-client-scoped/contextforge.env", compose)
        self.assertIn("CONTEXTFORGE_BASE_URL: http://host.docker.internal:4445", compose)
        self.assertIn("CONTEXTFORGE_TOKEN_CACHE: /tmp/contextforge-wrapper-token.local.json", compose)
        self.assertIn("CONTEXTFORGE_TOKEN_LOCK: /tmp/contextforge-wrapper-token.local.json.lock", compose)
        self.assertIn(
            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT: /home/agent/.local/state/contextforge-client-harness-runtime/project-init",
            compose,
        )
        self.assertIn('CONTEXTFORGE_SERENA_NO_SYSTEMD: "1"', compose)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS: /workspace", compose)

        for service in ("opencode", "pi"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertIn("- ../..:/repo:ro", match.group(0))
            self.assertIn("- ../../server-instances:/repo/server-instances:ro", match.group(0))
            self.assertIn("- ./client-scoped:/run/contextforge-client-scoped:ro", match.group(0))
            self.assertIn("- ./workspace:/workspace", match.group(0))
            self.assertNotIn("contextforge-harness/env:/config/contextforge", match.group(0))

        for service in ("opencode-ephemeral", "pi-ephemeral"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertIn("- ../..:/repo:ro", match.group(0))
            self.assertIn("- ../../server-instances:/repo/server-instances:ro", match.group(0))
            self.assertIn("- ./client-scoped:/run/contextforge-client-scoped:ro", match.group(0))
            self.assertIn("tmpfs:", match.group(0))
            self.assertIn("- /workspace:uid=1000,gid=1000,mode=0755", match.group(0))
            self.assertNotIn("- ./workspace:/workspace", match.group(0))
            self.assertNotIn("contextforge-harness/env:/config/contextforge", match.group(0))

        for service in ("codex-cli", "codex-cli-authenticated"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertIn("- ../..:/repo:ro", match.group(0))
            self.assertIn("- ../../server-instances:/repo/server-instances:ro", match.group(0))
            self.assertIn("- ./client-scoped:/run/contextforge-client-scoped:ro", match.group(0))
            self.assertNotIn("contextforge-harness/env:/config/contextforge", match.group(0))
            self.assertIn("- ./workspace:/workspace", match.group(0))

        for service in ("claude-code", "gemini-cli"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertNotIn("- ../..:/repo:ro", match.group(0))

    def test_target_client_services_do_not_mount_admin_contextforge_env(self) -> None:
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        scoped_example = (ROOT / "docker/client-harness/client-scoped/contextforge.env.example").read_text(
            encoding="utf-8"
        )

        self.assertIn("CONTEXTFORGE_BEARER_TOKEN=", scoped_example)
        self.assertIn("CONTEXTFORGE_SERVER_ID=", scoped_example)
        self.assertNotIn("PLATFORM_ADMIN_EMAIL", scoped_example)
        self.assertNotIn("PLATFORM_ADMIN_PASSWORD", scoped_example)

        for service in ("codex-cli", "codex-cli-authenticated", "opencode", "opencode-ephemeral", "pi", "pi-ephemeral"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            service_block = match.group(0)
            self.assertIn("- ./client-scoped:/run/contextforge-client-scoped:ro", service_block)
            self.assertIn("- ../../server-instances:/repo/server-instances:ro", service_block)
            self.assertNotIn("../contextforge-harness/env:/config/contextforge", service_block)
            self.assertNotIn("- ../../server-instances:/repo/server-instances\n", service_block)

    def test_pi_baseline_launcher_loads_shim_without_host_global_mutation(self) -> None:
        container_launcher = (ROOT / "docker/client-harness/config/pi/start-contextforge-baseline.sh").read_text(encoding="utf-8")
        host_launcher = (ROOT / "docker/client-harness/scripts/start-pi-contextforge-baseline.sh").read_text(encoding="utf-8")
        bootstrap = (ROOT / "docker/client-harness/pi/contextforge-pi-bootstrap.sh").read_text(encoding="utf-8")
        wrapper = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        combined = container_launcher + bootstrap + wrapper

        self.assertIn(". /usr/local/bin/contextforge-pi-bootstrap", container_launcher)
        self.assertIn("CONTEXTFORGE_PI_SHIM_INSTALL_DIR:=${PI_CODING_AGENT_DIR}/extensions/contextforge-global-shim", combined)
        self.assertIn("Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR", combined)
        self.assertIn("rm -rf \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", combined)
        self.assertIn("cp -R \"$(dirname \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\")\" \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", combined)
        self.assertIn("contextforge-root.json", combined)
        self.assertNotIn("--extension \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\"", combined)
        self.assertIn('--provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}"', container_launcher)
        self.assertIn('--model "${CONTEXTFORGE_PI_DEFAULT_MODEL}"', container_launcher)
        self.assertNotIn("openrouter-gemini-flash-lite", container_launcher)
        self.assertNotIn("google/gemini-2.5-flash-lite", container_launcher)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON:=/opt/contextforge-wrapper-venv/bin/python", combined)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WRAPPER:=/repo/scripts/contextforge_mcp_wrapper.py", combined)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env", combined)
        self.assertIn("CONTEXTFORGE_BASE_URL:=http://host.docker.internal:4445", combined)
        self.assertIn("CONTEXTFORGE_TOKEN_CACHE:=/tmp/contextforge-wrapper-token.local.json", combined)
        self.assertIn("CONTEXTFORGE_TOKEN_LOCK:=${CONTEXTFORGE_TOKEN_CACHE}.lock", combined)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init", combined)
        self.assertIn("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/pi-latest-user-message.json", combined)
        self.assertIn("CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH: /home/agent/.local/state/contextforge-client-harness-runtime/project-init/pi-latest-user-message.json", compose)
        self.assertIn("mkdir -p \"${PI_CODING_AGENT_DIR}\" \"${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}\"", combined)
        self.assertIn("latest_prompt", wrapper)
        self.assertIn("--arg text \"${latest_prompt}\"", wrapper)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace", combined)
        self.assertIn("docker compose -f compose.yml run --rm --no-deps", host_launcher)
        self.assertIn("-v \"${REPO_ROOT}:/repo:ro\"", host_launcher)
        self.assertNotIn("/home/dgk/.pi", combined + host_launcher)

    def test_opencode_baseline_launcher_installs_user_home_plugin_fixture(self) -> None:
        container_launcher = (ROOT / "docker/client-harness/config/opencode/start-contextforge-baseline.sh").read_text(encoding="utf-8")
        host_launcher = (ROOT / "docker/client-harness/scripts/start-opencode-contextforge-baseline.sh").read_text(encoding="utf-8")
        plugin = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")
        rules = (ROOT / "docker/client-harness/config/opencode/AGENTS.md").read_text(encoding="utf-8")
        entrypoint = (ROOT / "docker/client-harness/opencode/entrypoint.sh").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/client-harness/opencode/Dockerfile").read_text(encoding="utf-8")
        opencode_config = (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("OPENCODE_CONFIG:=/home/agent/.config/opencode/opencode.json", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=/home/agent/.config/opencode/plugins/contextforge-project-init.js", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_RULES_SOURCE:=/config/opencode/AGENTS.md", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_RULES_TARGET:=/home/agent/.config/opencode/AGENTS.md", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445", container_launcher)
        self.assertIn(
            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init",
            container_launcher,
        )
        self.assertIn(
            "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/opencode-latest-user-message.json",
            container_launcher,
        )
        self.assertIn("exec opencode \"$@\"", container_launcher)
        self.assertIn("docker compose -f compose.yml run --rm --no-deps", host_launcher)
        self.assertIn("-v \"${REPO_ROOT}:/repo:ro\"", host_launcher)
        self.assertIn("ENTRYPOINT [\"/usr/local/bin/contextforge-opencode-entrypoint\"]", dockerfile)
        self.assertIn("OPENCODE_CONFIG_DIR:=/home/agent/.config/opencode", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_TARGET:=${OPENCODE_CONFIG_DIR}/opencode.json", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=${OPENCODE_CONFIG_DIR}/plugins/contextforge-project-init.js", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_RULES_TARGET:=${OPENCODE_CONFIG_DIR}/AGENTS.md", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/run/contextforge-client-scoped/contextforge.env", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445", entrypoint)
        self.assertIn(
            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/home/agent/.local/state/contextforge-client-harness-runtime/project-init",
            entrypoint,
        )
        self.assertIn(
            "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH:=${CONTEXTFORGE_PROJECT_INIT_RUN_ROOT}/opencode-latest-user-message.json",
            entrypoint,
        )
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV: /run/contextforge-client-scoped/contextforge.env", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL: http://host.docker.internal:4445", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE: /tmp/contextforge-wrapper-token.local.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_RULES_SOURCE: /config/opencode/AGENTS.md", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_RULES_TARGET: /home/agent/.config/opencode/AGENTS.md", compose)
        self.assertNotIn("../contextforge-harness/env:/config/contextforge", compose)
        self.assertIn("cp \"${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE}\" \"${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}\"", entrypoint)
        self.assertIn("cp \"${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE}\" \"${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}\"", entrypoint)
        self.assertIn("cp \"${CONTEXTFORGE_OPENCODE_RULES_SOURCE}\" \"${CONTEXTFORGE_OPENCODE_RULES_TARGET}\"", entrypoint)
        self.assertIn("state revision", rules)
        self.assertIn("skipped or unavailable ContextForge service status", rules)
        self.assertIn('const HOOK_EVENT = "experimental.chat.messages.transform"', plugin)
        self.assertNotIn("experimental.chat.system.transform", plugin)
        self.assertIn("spawnSync", plugin)
        self.assertIn("recordLatestUserMessage", plugin)
        self.assertIn("opencode-latest-user-message.json", plugin)
        self.assertIn("call only `contextforge-helper_cf_project_init_continue`", plugin)
        self.assertIn("looksLikeServiceSelection", plugin)
        self.assertIn("The latest user reply is a natural-language service selection.", plugin)
        self.assertIn("The latest user reply is Serena language input", plugin)
        self.assertIn("Do not shorten the response to only `Approve`", plugin)
        self.assertIn("/workspace` is already the valid project root", plugin)
        self.assertIn("/workspace` is a valid project root even when it is a virgin harness workspace", plugin)
        self.assertIn("There are no separate OpenCode approval or apply tools", plugin)
        self.assertIn("After continuation reports installation succeeded", plugin)
        self.assertIn("Do not call any further project-init tools after installation succeeds.", plugin)
        self.assertIn("a new OpenCode session from this project root is required before the tools register", plugin)
        self.assertNotIn("cf_project_init_record_client_reload", plugin)
        self.assertNotIn("cf_project_init_record_validation", plugin)
        self.assertNotIn("validation_mode", plugin)
        self.assertIn('"permission.ask"', plugin)
        self.assertIn("CONTEXTFORGE_OPENCODE_DENY_RAW_WORKSPACE_MUTATION", plugin)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON", plugin)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK", plugin)
        self.assertIn("opencode_project_init_hook.py", plugin)
        self.assertIn("hookSpecificOutput", plugin)
        self.assertIn("additionalContext", plugin)
        self.assertIn("freshInitialization", plugin)
        self.assertIn("ContextForge first-prompt trigger:", plugin)
        self.assertIn("ContextForge continuation trigger:", plugin)
        self.assertIn("The current project already has ContextForge project-init state.", plugin)
        self.assertIn("Do not restart service selection.", plugin)
        self.assertIn("output.messages.unshift", plugin)
        self.assertIn("export default ContextForgeProjectInit", plugin)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace", container_launcher)
        self.assertIn('"contextforge-helper"', opencode_config)
        self.assertIn('"{env:CONTEXTFORGE_HELPER_PYTHON}"', opencode_config)
        self.assertIn('"{env:CONTEXTFORGE_HELPER_SCRIPT}"', opencode_config)
        self.assertIn('"CONTEXTFORGE_HELPER_DEFAULT_CLIENT_TYPE": "opencode"', opencode_config)
        self.assertIn('"CONTEXTFORGE_HELPER_REQUIRE_USER_APPROVAL_TEXT": "1"', opencode_config)
        self.assertNotIn('"CONTEXTFORGE_HELPER_REQUIRE_USER_RELOAD_TEXT"', opencode_config)
        self.assertNotIn('"CONTEXTFORGE_HELPER_REQUIRE_USER_VALIDATION_TEXT"', opencode_config)
        self.assertNotIn('"CONTEXTFORGE_HELPER_RECORD_RELOAD_ON_VALIDATION_REQUEST"', opencode_config)
        self.assertIn('"CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH"', opencode_config)
        self.assertIn('"CONTEXTFORGE_OPENCODE_DENY_RAW_WORKSPACE_MUTATION": "1"', opencode_config)
        self.assertIn("contextforge-client-harness-runtime", opencode_config)
        self.assertNotIn("/workspace/.opencode/plugins", container_launcher + entrypoint + plugin)
        self.assertNotIn("/repo/run", container_launcher + entrypoint + plugin)
        self.assertNotIn("/home/dgk/.config/opencode", container_launcher + host_launcher + plugin + entrypoint)
        self.assertNotIn("opencode mcp add", container_launcher + host_launcher + plugin)
        self.assertNotIn("opencode mcp list", container_launcher + host_launcher + plugin)

    def test_client_helper_baseline_contract_requires_future_runtime_evidence(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("separately approved runtime", contract)
        self.assertIn("Runtime Evidence Boundary", contract)
        self.assertIn("Pi ad hoc session lists or can invoke", contract)
        self.assertIn("OpenCode ad hoc session receives project-init helper/hook context", contract)
        self.assertIn("Both clients continue using the configured semantic-test model profile", contract)

    def test_use_case_13_package_runner_and_verifier_define_controlled_dev_validation(self) -> None:
        package = (ROOT / "docs/use-cases/use-case-13/package.md").read_text(encoding="utf-8")
        runner = (ROOT / "docker/client-harness/scripts/run-use-case-13-controlled-dev-validation.py").read_text(encoding="utf-8")
        verifier = (ROOT / "docker/client-harness/scripts/verify-use-case-13-controlled-dev-evidence.py").read_text(encoding="utf-8")
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("Issue: #255", package)
        self.assertIn("run/test-venvs/project-init-workflow/bin/python", package)
        self.assertIn("host.docker.internal:4445", package)
        self.assertIn("list-only evidence", package)
        self.assertIn("Codex authenticated Docker", package)
        self.assertIn("gpt-5.4-mini", package)
        self.assertIn("must not use string matching, regexes, keyword searches", package)
        self.assertIn('"run" / "test-venvs" / "project-init-workflow" / "bin" / "python"', runner)
        self.assertIn("reset-client-harness-state.py", runner)
        self.assertIn("smoke-pi-contextforge-dev.sh", runner)
        self.assertIn("smoke-opencode-contextforge-dev.sh", runner)
        self.assertIn("smoke-codex-contextforge-dev.sh", runner)
        self.assertIn("OPENCODE_REQUIRE_SAFE_CALL", runner)
        self.assertIn("selected_use_case_dialogue_evidence", runner)
        self.assertIn("not_a_dialogue_semantic_acceptance", runner)
        self.assertIn('"codex": "codex-cli"', runner)
        self.assertIn("current_worktree_test_venv", verifier)
        self.assertIn("legacy_live_contextforge_mutated", verifier)
        self.assertIn('"codex": "codex-cli"', verifier)
        self.assertIn("semantic_evaluator_required", verifier)
        self.assertIn("no semantic judgment over generated prose", verifier)
        self.assertIn("revoked before exit", contract)
        self.assertIn("Docker build/run/rebuild operations", contract)
        self.assertIn("ContextForge registry or token mutation", contract)
        self.assertIn("helper approve/apply/recovery state mutation", contract)
        self.assertIn("dev-time testing affordances", readme)
        self.assertIn("not production deployment modes", readme)
        self.assertIn("representative", readme)
        self.assertIn("code-assistant consumers", readme)
        self.assertIn("helper service and the services that the", readme)
        self.assertIn("facilitates; code-assistant runtimes", readme)
        self.assertIn("not as", readme)
        self.assertIn("surfaces owned by this control plane", readme)
        self.assertIn("semantic-test install/readback samples", readme)
        self.assertIn("thin consumers", readme)
        self.assertIn("less-mediated model behavior", readme)
        self.assertIn("multi-session persistence in `/workspace`", readme)
        self.assertIn("should not leave duplicate, stale,", readme)
        self.assertIn("or orphaned library/config artifacts", readme)
        self.assertIn("pi-ephemeral", readme)
        self.assertIn("opencode-ephemeral", readme)

    def test_pi_baseline_launcher_mounts_canonical_repo_as_workspace_root(self) -> None:
        host_launcher = (ROOT / "docker/client-harness/scripts/start-pi-contextforge-baseline.sh").read_text(encoding="utf-8")

        self.assertIn('-v "${REPO_ROOT}:/workspace:ro"', host_launcher)

    def test_pi_baseline_state_file_is_present_but_not_pi_bound(self) -> None:
        state = json.loads((ROOT / ".project/context_forge_state.json").read_text(encoding="utf-8"))
        services = state.get("services", {})

        self.assertIsInstance(services, dict)
        for service in services.values():
            target_clients = service.get("target_clients", {})
            self.assertIsInstance(target_clients, dict)
            self.assertNotIn("pi", target_clients)

    def test_pi_baseline_contract_documents_residual_no_target_clients_pi(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")

        self.assertIn(
            "project state has no approved target_clients.pi service bindings",
            contract,
        )

    def test_semantic_model_probe_records_exact_advertised_model_identity(self) -> None:
        probe = (ROOT / "docker/client-harness/scripts/probe-semantic-model.sh").read_text(encoding="utf-8")
        legacy_probe = (ROOT / "docker/client-harness/scripts/probe-llama.sh").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("client_model_identity.py", probe)
        self.assertIn("--expected-model-id \"${OPENROUTER_MODEL}\"", probe)
        self.assertIn("--fail-on-stale", probe)
        self.assertIn("evidence/pi-semantic-model-identity.json", probe)
        self.assertIn("evidence/opencode-semantic-model-identity.json", probe)
        self.assertIn('exec "${ROOT}/scripts/probe-semantic-model.sh" "$@"', legacy_probe)
        self.assertIn("scripts/probe-semantic-model.sh", readme)
        self.assertIn("legacy `scripts/probe-llama.sh` name remains only as a compatibility", readme)
        self.assertIn("exact advertised model identity reports", readme)
        self.assertIn("current`, `stale`, or `unverified`", readme)

    def test_comprehensive_mcp_gpu_stewardship_is_local_profile_conditional(self) -> None:
        skill = (ROOT / ".codex/skills/comprehensive-mcp-testing/SKILL.md").read_text(encoding="utf-8")
        method = (ROOT / ".codex/skills/comprehensive-mcp-testing/references/method.md").read_text(
            encoding="utf-8"
        )
        skill_line_wrapped = " ".join(skill.split())
        method_line_wrapped = " ".join(method.split())

        self.assertIn("Determine the selected provider/model profile first", skill_line_wrapped)
        self.assertIn("Randomize profiles per test run, not per inference", skill_line_wrapped)
        self.assertIn("Only run local-model/GPU stewardship checks", skill_line_wrapped)
        self.assertIn("Only check local model servers, `nvidia-smi`, or `ollama ps`", method_line_wrapped)
        self.assertIn("when that profile is actually hosted by the local model stack", method_line_wrapped)
        self.assertIn("For local-hosted profiles only, add:", method)
        self.assertIn("Do not spend time checking `nvidia-smi`, `ollama ps`, or a", method_line_wrapped)
        self.assertIn("when the active profile is OpenRouter or another remote provider", method_line_wrapped)

    def test_comprehensive_mcp_live_target_credentials_stay_out_of_prompts(self) -> None:
        method = (ROOT / ".codex/skills/comprehensive-mcp-testing/references/method.md").read_text(
            encoding="utf-8"
        )
        method_line_wrapped = " ".join(method.split())

        self.assertIn("keep credentials in the runtime boundary", method_line_wrapped)
        self.assertIn("do not teach the tested assistant a password or token", method_line_wrapped)
        self.assertIn("sidecar-local wrapper that consumes secrets without printing them", method_line_wrapped)
        self.assertIn("proves only the backend/auth layer", method_line_wrapped)


if __name__ == "__main__":
    unittest.main()
