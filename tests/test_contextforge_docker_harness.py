from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys_path = sys.path
    sys_path.insert(0, str(path.parent))
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys_path.remove(str(path.parent))
        except ValueError:
            pass
    return module


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
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_ALIAS", wrapper)
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_AUTH_MODE", wrapper)
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_PASSWORD", wrapper)
        self.assertIn("HostName=$TARGET_HOST", wrapper)
        self.assertIn("-l \"$TARGET_USER\"", wrapper)
        self.assertIn("sshpass -e", wrapper)
        self.assertIn("SSHPASS=$TARGET_PASSWORD", wrapper)
        self.assertIn("UserKnownHostsFile=$KNOWN_HOSTS", wrapper)
        self.assertIn("StrictHostKeyChecking=$STRICT_HOST_KEY_CHECKING", wrapper)
        self.assertIn("-i \"$PRIVATE_KEY\"", wrapper)

        env_example = (ROOT / "server-instances/ssh-tmux/.env.example").read_text(encoding="utf-8")
        self.assertIn("CONTEXTFORGE_SSH_TMUX_TEST_ALIAS=contextforge-live-target", env_example)

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

    def test_compose_defines_time_development_foil_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/time-transceiver/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("time-transceiver:", compose)
        self.assertIn("contextforge-harness-time-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9209:9209"', compose)
        self.assertIn("docker/contextforge-harness/time-transceiver/Dockerfile", compose)
        self.assertIn('LOCAL_TIMEZONE: "${LOCAL_TIMEZONE:-UTC}"', compose)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("mcp-server-time", dockerfile)
        self.assertIn("mcpgateway.translate", dockerfile)
        self.assertIn("--stdio", dockerfile)
        self.assertIn("mcp-server-time --local-timezone", dockerfile)
        self.assertIn("--expose-sse", dockerfile)
        self.assertIn("--expose-streamable-http", dockerfile)
        self.assertIn("EXPOSE 9209", dockerfile)
        self.assertIn("--port 9209", dockerfile)

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

    def test_time_register_script_targets_dev_harness_names_and_network_url(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/register_time_dev.py").read_text(encoding="utf-8")

        self.assertIn('GATEWAY_NAME = "time-dev-docker"', source)
        self.assertIn('SERVER_NAME = "time_dev_docker_server"', source)
        self.assertIn('DEFAULT_UPSTREAM_URL = "http://time-transceiver:9209/mcp"', source)
        self.assertIn('DEFAULT_GATEWAY_BASE = "http://127.0.0.1:4445"', source)
        self.assertIn('"development-foil"', source)
        self.assertNotIn("127.0.0.1:4444", source)

    def test_time_probe_uses_safe_probe_and_revokes_token(self) -> None:
        source = (ROOT / "docker/contextforge-harness/scripts/probe-time-dev.py").read_text(encoding="utf-8")

        self.assertIn('DEFAULT_DIRECT_URL = "http://127.0.0.1:9209/mcp"', source)
        self.assertIn('SAFE_TIME_ARGS = {"timezone": "UTC"}', source)
        self.assertIn("get_current_time", source)
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
            ".contextforge/service-onboarding/runtime-apply-packages/",
            ".contextforge/service-onboarding/runtime-drafts/",
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

    def test_client_guidance_does_not_route_uncataloged_service_onboarding(self) -> None:
        pi_source = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")
        opencode_source = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")
        pi_rules = (ROOT / "docker/client-harness/config/pi/AGENTS.md").read_text(encoding="utf-8")
        opencode_rules = (ROOT / "docker/client-harness/config/opencode/AGENTS.md").read_text(encoding="utf-8")

        for source in (opencode_source, pi_rules, opencode_rules):
            self.assertNotIn("cf_project_service_onboarding", source)
            self.assertNotIn("get_service_onboarding_how_to", source)
            self.assertNotIn("source-only onboarding", source)
            self.assertNotIn("managed npm-stdio", source)
            self.assertNotIn("runtime/apply", source)
            self.assertNotIn("uncataloged MCP service", source)
        self.assertIn("known\nContextForge service offerings", pi_rules)
        self.assertIn("known ContextForge service offerings", opencode_rules)
        self.assertIn("list, enable, disable, remove, repair, and details", pi_rules)
        self.assertNotIn("serviceOnboardingPlannedSessions", opencode_source)
        self.assertNotIn("serviceOnboardingPlanInstruction", opencode_source)
        self.assertNotIn("asksForUncatalogedServiceOnboarding", opencode_source)
        self.assertIn("For questions asking how to use the project docs lookup capability", pi_source)

    def test_opencode_transform_does_not_intercept_uncataloged_onboarding_requests(self) -> None:
        plugin_uri = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").as_uri()
        user_text = (
            "I want to add this MCP service to the project: "
            "https://github.com/modelcontextprotocol/servers/tree/main/src/time. "
            "It is the Time MCP service, stdio, shared canonical, stateless, "
            "no credentials, expected tools get_current_time and convert_time."
        )
        script = f"""
const mod = await import({json.dumps(plugin_uri)});
const plugin = await mod.ContextForgeProjectInit({{ directory: "/workspace" }});
const hook = plugin["experimental.chat.messages.transform"];
const userText = {json.dumps(user_text)};
const first = {{
  messages: [
    {{
      info: {{ id: "msg-1", role: "user", sessionID: "session-1" }},
      parts: [{{ type: "text", text: userText }}],
    }},
  ],
}};
await hook({{}}, first);
const flatten = (messages) => messages
  .flatMap((message) => message.parts || [])
  .map((part) => part.text || "")
  .join("\\n");
console.log(JSON.stringify({{
  firstCount: first.messages.length,
  firstRoute: first.messages[0].parts[0].text,
  firstVisibleContext: flatten(first.messages),
}}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "CONTEXTFORGE_HELPER_PYTHON": sys.executable,
                "CONTEXTFORGE_PROJECT_INIT_HELPER_CLI": str(ROOT / "scripts/pi_project_init_helper_cli.py"),
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(1, parsed["firstCount"])
        self.assertEqual(user_text, parsed["firstRoute"])
        self.assertIn("https://github.com/modelcontextprotocol/servers/tree/main/src/time", parsed["firstVisibleContext"])
        self.assertIn("get_current_time", parsed["firstVisibleContext"])
        self.assertNotIn("contextforge-helper_cf_project_service_onboarding", parsed["firstVisibleContext"])
        self.assertNotIn("<contextforge-service-onboarding>", parsed["firstVisibleContext"])

    def test_onboarding_semantic_process_gate_uses_real_clients_and_composite_persona(self) -> None:
        gate = (ROOT / "docker/client-harness/ONBOARDING_SEMANTIC_PROCESS_GATE.md").read_text(encoding="utf-8")
        method = (ROOT / "docker/client-harness/DIALOGUE_EVALUATION_METHOD.md").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")
        dialogue_runner = (
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py"
        ).read_text(encoding="utf-8")
        quorum_runner = (
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-quorum.py"
        ).read_text(encoding="utf-8")
        comprehensive_skill = (ROOT / ".codex/skills/comprehensive-mcp-testing/SKILL.md").read_text(
            encoding="utf-8"
        )
        comprehensive_method = (
            ROOT / ".codex/skills/comprehensive-mcp-testing/references/method.md"
        ).read_text(encoding="utf-8")
        dialogue_skill = (ROOT / ".codex/skills/code-assistant-dialogue-validation/SKILL.md").read_text(
            encoding="utf-8"
        )
        onboarding_skill = (
            ROOT / ".codex/skills/contextforge-onboarding-semantic-testing/SKILL.md"
        ).read_text(encoding="utf-8")
        scenarios = json.loads(
            (ROOT / "docker/client-harness/onboarding-semantic-process-scenarios.json").read_text(encoding="utf-8")
        )
        semantic_profiles = json.loads(
            (ROOT / "docker/client-harness/semantic-model-profiles.json").read_text(encoding="utf-8")
        )["profiles"]
        eligible_profile_ids = [
            profile["id"]
            for profile in semantic_profiles
            if profile.get("multi_step_quorum_eligible") is not False
        ]

        self.assertIn("real Pi or OpenCode client session", gate)
        self.assertIn("Codex-only onboarding run proves nothing", gate)
        self.assertIn("installer equivalence", gate)
        self.assertIn("Harness-only, AGENTS-only, hidden, or otherwise non-product", gate)
        self.assertIn("preserve installer equivalence", method)
        self.assertIn("installer equivalence", onboarding_skill)
        self.assertIn("randomly compose a", gate)
        self.assertIn("five-dimensional disposition space", gate)
        self.assertIn("stable for the whole dialogue", gate)
        self.assertIn("must not evaluate generated assistant meaning through", gate)
        self.assertIn("string or regex matching", gate)
        self.assertEqual(["pi", "opencode"], scenarios["target_clients"])
        self.assertEqual(3, scenarios["minimum_luna_run_quorum_per_client"])
        self.assertEqual(
            ["litellm-codex-gpt-5.6-luna"],
            eligible_profile_ids,
        )
        self.assertEqual(
            "random_composition_per_client_luna_run",
            scenarios["persona_sampling"]["selection_scope"],
        )
        self.assertEqual(
            "five_dimensional_persona_vector_plus_help_determination_multiplier",
            scenarios["persona_sampling"]["composition_model"],
        )
        self.assertEqual(15, scenarios["persona_sampling"]["help_determination"]["default"])
        self.assertEqual("n/20", scenarios["persona_sampling"]["help_determination"]["scale"])
        self.assertEqual([1, 20], scenarios["persona_sampling"]["help_determination"]["bounds"])
        self.assertEqual(
            "+2 for the next quorum batch",
            scenarios["persona_sampling"]["help_determination"]["batch_adaptation"]["all_three_fail"],
        )
        self.assertEqual(
            [
                "domain_knowledge",
                "goal_specificity",
                "risk_posture",
                "technical_fluency",
                "interaction_style",
            ],
            [dimension["id"] for dimension in scenarios["persona_sampling"]["dimensions"]],
        )
        self.assertIn(
            "does not use Codex subagents as tested-client substitutes",
            scenarios["runner_non_actions"],
        )
        foils = {foil["id"]: foil for foil in scenarios["foils"]}
        self.assertEqual("legacy_development_foil_not_clean_for_acceptance", foils["time"]["candidate_status"])
        self.assertEqual(1, foils["memory"]["order"])
        self.assertTrue(foils["time"]["invalid_if_preexisting_contextforge_artifacts"])
        self.assertIn("time:canonical", foils["time"]["forbidden_existing_contextforge_bindings"])
        self.assertIn("service_bound_prompts", foils["time"]["preexisting_contextforge_artifact_scope"])
        self.assertIn("service_bound_resources", foils["time"]["preexisting_contextforge_artifact_scope"])
        self.assertTrue(foils["memory"]["source_lead_only"])
        self.assertIn("memory:canonical", foils["memory"]["forbidden_existing_contextforge_bindings"])
        self.assertEqual("@modelcontextprotocol/server-memory", foils["memory"]["npm_package_metadata_evidence"]["package"])
        self.assertEqual("mcp-server-memory", foils["memory"]["npm_package_metadata_evidence"]["bin"])
        self.assertIn("already exists in ContextForge", " ".join(method.split()))
        self.assertIn("preexisting-foil", onboarding_skill)
        self.assertIn("available-capabilities", gate)
        self.assertIn("Use this skill for onboarding-process proof", onboarding_skill)
        self.assertIn("not for already-registered MCP service-use proof", onboarding_skill)
        self.assertIn("For ordinary service-use proof", onboarding_skill)
        self.assertIn("contextforge-onboarding-semantic-testing", comprehensive_skill)
        self.assertIn("contextforge-onboarding-semantic-testing", comprehensive_method)
        self.assertIn("contextforge-onboarding-semantic-testing", dialogue_skill)
        self.assertIn("contextforge-onboarding-semantic-testing", method)
        for source in [method, comprehensive_skill, comprehensive_method, dialogue_skill, onboarding_skill]:
            normalized_source = " ".join(source.split())
            self.assertIn("Pi or OpenCode", normalized_source)
            self.assertIn("Codex subagent", normalized_source)
            self.assertIn("three", normalized_source)
            self.assertIn("Luna/medium", normalized_source)
        for source in [gate, method, comprehensive_method]:
            normalized_source = " ".join(source.split())
            self.assertIn("domain knowledge", normalized_source)
            self.assertIn("goal specificity", normalized_source)
            self.assertIn("risk posture", normalized_source)
            self.assertIn("technical fluency", normalized_source)
            self.assertIn("interaction style", normalized_source)
        for persona_dimension in [
            "`domain_knowledge`",
            "`goal_specificity`",
            "`risk_posture`",
            "`technical_fluency`",
            "`interaction_style`",
        ]:
            self.assertIn(persona_dimension, onboarding_skill)
        for source in [dialogue_runner, quorum_runner]:
            self.assertIn("requires_sol_evaluator", source)
            self.assertIn("deterministic_semantic_oracles_allowed", source)
            self.assertIn("does not score free-form assistant prose", source)
            self.assertIn("Codex as tested assistant", source)
        self.assertIn("choices=[\"pi\", \"opencode\"]", dialogue_runner)
        self.assertIn("choices=[\"pi\", \"opencode\"]", quorum_runner)
        self.assertIn("separate_simulated_human_responder_required", dialogue_runner)
        self.assertIn("agent_supplied_prompt_sequence", dialogue_runner)
        self.assertIn("agent_supplied_prompt_file", dialogue_runner)
        self.assertIn("runner seeded prompts are structural scaffolding", dialogue_runner)
        self.assertIn("invalid_preexisting_foil_artifacts", dialogue_runner)
        self.assertIn("preflight-contextforge-foil-clean-readback.json", dialogue_runner)
        self.assertIn("preflight-contextforge-available-capabilities.json", dialogue_runner)
        self.assertIn('"contextforge_servers": registry_parsed.get("contextforge_servers") or []', dialogue_runner)
        self.assertIn('choices=["pi", "model", "seeded"]', dialogue_runner)
        self.assertIn('default="pi"', dialogue_runner)
        self.assertIn("pi_litellm_terra_simulated_human_responder", dialogue_runner)
        self.assertIn("acceptance_matrix_eligibility", dialogue_runner)
        self.assertIn("dialogue_summary_acceptance_eligible", quorum_runner)
        self.assertIn("contextforge-client-pi:latest", dialogue_runner)
        evaluation_docs = gate + method + onboarding_skill + readme
        self.assertIn("codex/gpt-5.6-terra", gate + onboarding_skill + dialogue_runner)
        self.assertIn("Terra", onboarding_skill)
        self.assertIn("Demanding does not mean cantankerous", gate)
        self.assertIn("Demanding does not mean cantankerous", onboarding_skill)
        self.assertIn("not a hostile", dialogue_runner)
        self.assertIn("Do not become cantankerous", dialogue_runner)
        self.assertIn("Do not use latent technical knowledge", dialogue_runner)
        self.assertIn("persona's ignorance boundary", gate)
        self.assertIn("persona's ignorance boundary", onboarding_skill)
        self.assertIn("alternate non-ContextForge routes", dialogue_runner)
        pi_shim = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")
        self.assertNotIn("Do not put prose explanations in value", pi_shim)
        self.assertNotIn("runtimeApplyPackageId", pi_shim)
        self.assertNotIn("do not reconstruct the full package payload from memory", pi_shim)
        opencode_plugin = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")
        self.assertNotIn("runtime_apply_package_id", opencode_plugin)
        self.assertNotIn("Prefer that id over reconstructing the full package payload from memory", opencode_plugin)
        self.assertIn("continue_conversation", dialogue_runner)
        self.assertIn("simulated_human_declared_complete", dialogue_runner)
        interaction_style = next(
            dimension
            for dimension in scenarios["persona_sampling"]["dimensions"]
            if dimension["id"] == "interaction_style"
        )
        self.assertIn("not cantankerous or hostile", interaction_style["rule"])
        self.assertIn("should not become cantankerous or hostile", method)
        self.assertIn("15/20", gate)
        self.assertIn("n/20", onboarding_skill)
        self.assertIn("32 tested-assistant turns or 600 seconds", gate)
        self.assertIn("32 tested-assistant turns or 600", onboarding_skill)
        self.assertIn("evaluate every user/assistant turn", method)
        self.assertIn("does not require one evaluator invocation per turn", " ".join(method.split()))
        self.assertIn("do not call an evaluator inside the live conversation loop", onboarding_skill)
        self.assertIn("litellm/codex/gpt-5.6-sol", evaluation_docs)
        self.assertIn("Sol", evaluation_docs)
        self.assertIn("high", evaluation_docs)
        self.assertIn("suppress raw reasoning tokens", evaluation_docs)
        self.assertIn("dry_run", dialogue_runner)
        self.assertIn("if not args.dry_run", dialogue_runner)
        self.assertIn("MIN_RUN_QUORUM = 3", quorum_runner)
        self.assertIn("select_persona_indices", quorum_runner)
        self.assertIn("persona_coverage", quorum_runner)
        self.assertIn("parallel_isolated", quorum_runner)
        self.assertIn("at least three independent Luna/medium tested-assistant runs", " ".join(onboarding_skill.split()))

        dialogue_module = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_semantic_dialogue_test",
        )
        quorum_module = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-quorum.py",
            "onboarding_semantic_quorum_test",
        )
        self.assertEqual(32, dialogue_module.DEFAULT_ONBOARDING_TURNS)
        self.assertEqual(600, dialogue_module.DEFAULT_DIALOGUE_SECONDS)
        self.assertEqual(15, dialogue_module.DEFAULT_HUMAN_HELP_DETERMINATION)
        self.assertEqual("contextforge-client-pi:latest", dialogue_module.DEFAULT_PI_RESPONDER_IMAGE)
        self.assertEqual("litellm", dialogue_module.DEFAULT_PI_RESPONDER_PROVIDER)
        self.assertEqual("codex/gpt-5.6-terra", dialogue_module.DEFAULT_PI_RESPONDER_MODEL)
        self.assertEqual("high", dialogue_module.DEFAULT_PI_RESPONDER_THINKING)
        self.assertEqual(32, quorum_module.DEFAULT_ONBOARDING_TURNS)
        self.assertEqual(600, quorum_module.DEFAULT_DIALOGUE_SECONDS)
        self.assertEqual(15, quorum_module.DEFAULT_HUMAN_HELP_DETERMINATION)
        self.assertEqual(1, dialogue_module.bounded_help_determination(-5))
        self.assertEqual(20, dialogue_module.bounded_help_determination(99))
        self.assertIn(
            "determination_to_help_assistant_succeed_at_onboarding: 15/20",
            "\n".join(dialogue_module.help_determination_lines(15)),
        )
        self.assertIn("7/20", "\n".join(dialogue_module.help_determination_lines(7)))
        self.assertNotIn("/10", "\n".join(dialogue_module.help_determination_lines(7)))
        self.assertEqual(12, quorum_module.next_batch_help_determination(10, failure_count=3))
        self.assertEqual(11, quorum_module.next_batch_help_determination(10, failure_count=2))
        self.assertEqual(10, quorum_module.next_batch_help_determination(10, failure_count=1))
        self.assertEqual(9, quorum_module.next_batch_help_determination(10, failure_count=0))
        self.assertEqual(20, quorum_module.next_batch_help_determination(19, failure_count=3))
        self.assertEqual(
            "target-session-fresh-1",
            dialogue_module.fresh_target_session_id("target-session", 1),
        )
        persona = dialogue_module.compose_persona(scenarios, seed=17, index=1)
        self.assertEqual(
            {
                "domain_knowledge",
                "goal_specificity",
                "risk_posture",
                "technical_fluency",
                "interaction_style",
            },
            set(persona),
        )
        prompts = dialogue_module.persona_prompt_sequence(scenarios["foils"][0], persona, 2)
        self.assertEqual(2, len(prompts))
        self.assertIn(scenarios["foils"][0]["source_lead"], prompts[0])
        persona_indices = quorum_module.select_persona_indices(dialogue_module, scenarios, 3, 17)
        personas = [
            dialogue_module.compose_persona(scenarios, seed=17, index=index)
            for index in persona_indices
        ]
        coverage = quorum_module.persona_coverage(personas)
        self.assertTrue(coverage["ready_for_acceptance_matrix"])
        self.assertTrue(
            dialogue_module.acceptance_matrix_eligibility(
                dry_run=False,
                responder_mode="pi_litellm_terra_simulated_human_responder",
                manual_prompting=False,
                allow_preexisting_foil_artifacts=False,
                preflight_status="passed",
            )["eligible"]
        )
        seeded_eligibility = dialogue_module.acceptance_matrix_eligibility(
            dry_run=False,
            responder_mode="seeded_default_persona_prompts",
            manual_prompting=False,
            allow_preexisting_foil_artifacts=False,
            preflight_status="passed",
        )
        self.assertFalse(seeded_eligibility["eligible"])
        self.assertIn("simulated_human_responder_not_pi_litellm_terra", seeded_eligibility["disqualifiers"])
        manual_eligibility = dialogue_module.acceptance_matrix_eligibility(
            dry_run=False,
            responder_mode="pi_litellm_terra_simulated_human_responder",
            manual_prompting=True,
            allow_preexisting_foil_artifacts=False,
            preflight_status="passed",
        )
        self.assertFalse(manual_eligibility["eligible"])
        self.assertIn("manual_or_seeded_prompt_sequence", manual_eligibility["disqualifiers"])
        self.assertTrue(
            quorum_module.dialogue_summary_acceptance_eligible(
                {"acceptance_matrix_eligibility": {"eligible": True}}
            )
        )
        self.assertFalse(
            quorum_module.dialogue_summary_acceptance_eligible(
                {"acceptance_matrix_eligibility": seeded_eligibility}
            )
        )

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

    def test_time_harness_readme_uses_repo_venv_for_probe_scripts(self) -> None:
        readme = (ROOT / "docker/contextforge-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/probe-time-dev.py --direct-only", readme)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/register_time_dev.py", readme)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/apply_onboarding_runtime_package.py", readme)
        self.assertIn("--package-json /path/to/runtime-apply-package.json", readme)
        self.assertIn("--upstream-url http://time-transceiver:9209/mcp", readme)
        self.assertIn("The script defaults to a dry run", readme)
        self.assertIn("It does not create Docker", readme)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/probe-time-dev.py", readme)
        self.assertIn("target-client readiness still needs", readme)

    def test_npm_stdio_host_substrate_is_declared_in_compose_and_readme(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/contextforge-harness/npm-stdio-host/Dockerfile").read_text(encoding="utf-8")
        readme = (ROOT / "docker/contextforge-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("npm-stdio-host:", compose)
        self.assertIn("docker/contextforge-harness/npm-stdio-host/Dockerfile", compose)
        self.assertIn("../../server-instances:/workspace/server-instances", compose)
        self.assertIn('user: "${CONTEXTFORGE_HARNESS_UID:-1000}:${CONTEXTFORGE_HARNESS_GID:-1000}"', compose)
        self.assertIn("node:24-bookworm-slim", dockerfile)
        self.assertIn("mcp-contextforge-gateway", dockerfile)
        self.assertIn("npm_stdio_host_records.py", dockerfile)
        self.assertIn("npm_stdio_host_runtime.py", dockerfile)
        self.assertIn("npm_stdio_host_runtime.py", compose)
        self.assertIn("Managed npm-stdio Host Substrate", readme)
        self.assertIn("managed-record plus runtime CRUD", readme)
        self.assertIn("managed bridge process inside the shared Docker host", readme)
        self.assertIn("not root-owned on the host", readme)
        self.assertIn("does not yet claim", readme)
        self.assertIn("Pi/OpenCode/Codex target-client readiness", readme)

    def test_time_onboarding_foil_cleanup_readback_identifies_all_required_artifact_scopes(self) -> None:
        cleanup = _load_script_module(
            ROOT / "docker/contextforge-harness/scripts/clean_onboarding_foil.py",
            "clean_onboarding_foil_test",
        )
        live = {
            "gateways": [{"id": "gateway-time", "name": "time-dev-docker", "enabled": True}],
            "tools": [
                {
                    "id": "tool-time",
                    "name": "time-dev-docker-get-current-time",
                    "gatewayId": "gateway-time",
                    "enabled": True,
                }
            ],
            "servers": [
                {
                    "id": "server-time",
                    "name": "time_dev_docker_server",
                    "associatedToolIds": ["tool-time"],
                    "associatedPromptIds": ["prompt-time"],
                    "associatedResourceIds": ["resource-time"],
                    "enabled": True,
                }
            ],
            "prompts": [{"id": "prompt-time", "name": "time-abstract-spec", "enabled": True}],
            "resources": [
                {
                    "id": "resource-time",
                    "name": "time abstract spec",
                    "uri": "contextforge://time/abstract-spec",
                    "enabled": True,
                }
            ],
        }

        manifest = cleanup.build_manifest(
            foil_id="time",
            base_url="http://127.0.0.1:4445",
            live=live,
            apply=False,
        )

        self.assertEqual("dirty", manifest["status"])
        self.assertEqual(
            {
                "mcp_service": 1,
                "service_bound_prompts": 1,
                "service_bound_resources": 1,
                "service_tools": 1,
                "virtual_server": 1,
            },
            manifest["counts"],
        )
        self.assertEqual(
            ["virtual_server", "service_bound_prompts", "service_bound_resources", "service_tools", "mcp_service"],
            [operation["scope"] for operation in manifest["planned_operations"]],
        )
        self.assertEqual(
            [{"enabled": True, "id": "server-time", "name": "time_dev_docker_server"}],
            manifest["contextforge_servers"],
        )
        self.assertFalse(manifest["live_mutation_performed"])
        self.assertEqual("known_development_foil_artifacts_present", manifest["repo_artifact_readback"]["status"])
        self.assertGreater(manifest["repo_artifact_readback"]["present_count"], 0)

    def test_memory_onboarding_foil_cleanup_readback_identifies_all_required_artifact_scopes(self) -> None:
        cleanup = _load_script_module(
            ROOT / "docker/contextforge-harness/scripts/clean_onboarding_foil.py",
            "clean_onboarding_memory_foil_test",
        )
        live = {
            "gateways": [{"id": "gateway-memory", "name": "memory-canonical-gateway", "enabled": True}],
            "tools": [
                {
                    "id": "tool-memory",
                    "name": "create_entities",
                    "gatewayId": "gateway-memory",
                    "enabled": True,
                }
            ],
            "servers": [
                {
                    "id": "server-memory",
                    "name": "memory-canonical-server",
                    "associatedToolIds": ["tool-memory"],
                    "associatedPromptIds": ["prompt-memory"],
                    "associatedResourceIds": ["resource-memory"],
                    "enabled": True,
                }
            ],
            "prompts": [{"id": "prompt-memory", "name": "memory-abstract-spec", "enabled": True}],
            "resources": [
                {
                    "id": "resource-memory",
                    "name": "memory abstract spec",
                    "uri": "contextforge://service-specs/memory/abstract/v1",
                    "enabled": True,
                }
            ],
        }

        manifest = cleanup.build_manifest(
            foil_id="memory",
            base_url="http://127.0.0.1:4445",
            live=live,
            apply=False,
        )

        self.assertEqual("dirty", manifest["status"])
        self.assertEqual(
            {
                "mcp_service": 1,
                "service_bound_prompts": 1,
                "service_bound_resources": 1,
                "service_tools": 1,
                "virtual_server": 1,
            },
            manifest["counts"],
        )
        self.assertEqual("no_known_repo_local_foil_artifacts", manifest["repo_artifact_readback"]["status"])
        self.assertEqual(0, manifest["repo_artifact_readback"]["present_count"])

    def test_time_onboarding_foil_cleanup_cli_fixture_fails_closed_when_dirty(self) -> None:
        live = {
            "gateways": [{"id": "gateway-time", "name": "time-dev-docker", "enabled": True}],
            "tools": [],
            "servers": [],
            "prompts": [],
            "resources": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live_json = root / "live.json"
            output = root / "readback.json"
            live_json.write_text(json.dumps(live), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "docker/contextforge-harness/scripts/clean_onboarding_foil.py"),
                    "--foil",
                    "time",
                    "--live-json",
                    str(live_json),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            manifest = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(2, result.returncode, result.stdout)
        self.assertEqual("", result.stderr)
        self.assertEqual("dirty", manifest["status"])
        self.assertEqual(1, manifest["counts"]["mcp_service"])

    def test_time_onboarding_foil_cleanup_cli_fixture_passes_when_clean(self) -> None:
        live = {
            "gateways": [],
            "tools": [],
            "servers": [{"id": "server-context7", "name": "context7_local_server", "enabled": True}],
            "prompts": [],
            "resources": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live_json = root / "live.json"
            output = root / "readback.json"
            live_json.write_text(json.dumps(live), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "docker/contextforge-harness/scripts/clean_onboarding_foil.py"),
                    "--foil",
                    "time",
                    "--live-json",
                    str(live_json),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            manifest = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("clean", manifest["status"])
        self.assertEqual(0, sum(manifest["counts"].values()))
        self.assertEqual(
            [{"enabled": True, "id": "server-context7", "name": "context7_local_server"}],
            manifest["contextforge_servers"],
        )

    def test_onboarding_foil_preflight_passes_live_server_readback_to_capability_menu(self) -> None:
        dialogue = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_semantic_dialogue_preflight_test",
        )
        live_servers = [{"id": "server-context7", "name": "context7_local_server", "enabled": True}]

        class FakeUseCaseRunner:
            def __init__(self) -> None:
                self.calls: list[list[str]] = []
                self.payloads: list[dict[str, Any]] = []

            def run(self, command: list[str], **_: Any) -> dict[str, Any]:
                self.calls.append(command)
                if "clean_onboarding_foil.py" in " ".join(command):
                    return {
                        "returncode": 0,
                        "timeout": False,
                        "stdout": json.dumps(
                            {
                                "status": "clean",
                                "counts": {
                                    "mcp_service": 0,
                                    "service_tools": 0,
                                    "virtual_server": 0,
                                    "service_bound_prompts": 0,
                                    "service_bound_resources": 0,
                                },
                                "contextforge_servers": live_servers,
                            }
                        ),
                    }
                payload = json.loads(command[command.index("--payload-json") + 1])
                self.payloads.append(payload)
                return {
                    "returncode": 0,
                    "timeout": False,
                    "stdout": json.dumps(
                        {
                            "ok": True,
                            "available_services": [{"service_binding": "context7:canonical"}],
                            "next_turn": {"choices": [{"id": "context7:canonical"}, {"id": "none"}]},
                        }
                    ),
                }

            @staticmethod
            def parse_json_or_text(text: str) -> Any:
                return json.loads(text)

        with tempfile.TemporaryDirectory() as tmp:
            args = type(
                "Args",
                (),
                {
                    "allow_preexisting_foil_artifacts": False,
                    "client": "pi",
                },
            )()
            fake = FakeUseCaseRunner()
            result = dialogue.contextforge_foil_preflight(
                foil={
                    "id": "time",
                    "invalid_if_preexisting_contextforge_artifacts": True,
                    "forbidden_existing_contextforge_bindings": ["time:canonical"],
                    "preexisting_contextforge_artifact_scope": [
                        "mcp_service",
                        "service_tools",
                        "virtual_server",
                        "service_bound_prompts",
                        "service_bound_resources",
                        "client_activation_menu_entries",
                    ],
                },
                args=args,
                repo_root=ROOT,
                harness_root=ROOT / "docker/client-harness",
                output_root=Path(tmp),
                reset_json={"workspace": "/workspace"},
                uc1=fake,
                commands=[],
            )

        self.assertEqual("passed", result["status"])
        self.assertEqual(live_servers, fake.payloads[0]["contextforge_servers"])

    def test_onboarding_pi_human_responder_command_is_session_scoped_and_toolless(self) -> None:
        dialogue = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_semantic_pi_responder_command_test",
        )
        command = dialogue.pi_responder_command(
            {
                "provider": "litellm",
                "model": "codex/gpt-5.6-terra",
                "thinking": "high",
            },
            "human-sim-session",
            "Answer the tested assistant.",
            help_determination=15,
        )

        self.assertEqual("pi", command[0])
        self.assertEqual("litellm", command[command.index("--provider") + 1])
        self.assertEqual("codex/gpt-5.6-terra", command[command.index("--model") + 1])
        self.assertEqual("high", command[command.index("--thinking") + 1])
        self.assertEqual("human-sim-session", command[command.index("--session-id") + 1])
        self.assertEqual("/home/agent/.pi/human-sim-sessions", command[command.index("--session-dir") + 1])
        self.assertIn("--system-prompt", command)
        self.assertIn("15/20", command[command.index("--system-prompt") + 1])
        self.assertEqual("Answer the tested assistant.", command[-1])
        self.assertIn("--no-tools", command)
        self.assertIn("--no-context-files", command)
        self.assertIn("--no-extensions", command)
        self.assertIn("--no-skills", command)
        self.assertIn("--no-prompt-templates", command)

    def test_onboarding_pi_human_responder_session_id_fits_codex_cache_key_limit(self) -> None:
        dialogue = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_semantic_pi_responder_session_id_test",
        )
        session_id = dialogue.pi_responder_session_id(
            foil="time",
            client="opencode",
            run_id="20260622T081059Z-opencode-gemma-proxy-fix-2",
        )

        self.assertLessEqual(len(session_id), 64)
        self.assertEqual(session_id, dialogue.pi_responder_session_id(foil="time", client="opencode", run_id="20260622T081059Z-opencode-gemma-proxy-fix-2"))
        self.assertTrue(session_id.startswith("human-sim-time-opencode-"))

    def test_onboarding_pi_human_responder_launch_blanks_api_key_env(self) -> None:
        dialogue = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_semantic_pi_responder_env_guard_test",
        )

        self.assertIn("PI_RESPONDER_FORBIDDEN_API_KEY_ENVS", dialogue.__dict__)
        for key in [
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "PERPLEXITY_API_KEY",
            "EXA_API_KEY",
            "CONTEXT7_API_KEY",
        ]:
            self.assertIn(key, dialogue.PI_RESPONDER_FORBIDDEN_API_KEY_ENVS)

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
        self.assertIn("time-transceiver", service_names)

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
        self.assertIn("`time` follows the same compose-sidecar-locality", policy)
        self.assertIn("canonical post-development service set decision", policy)

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

    def test_opencode_semantic_config_renders_only_approved_litellm_models(self) -> None:
        render_config = _load_script_module(
            ROOT / "docker/client-harness/opencode/render-config.py",
            "contextforge_opencode_render_config_test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.json"
            target = tmp_path / "opencode.json"
            source.write_text(
                (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            env = {
                "CONTEXTFORGE_OPENCODE_CONFIG_SOURCE": str(source),
                "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(target),
                "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "litellm/codex/gpt-5.6-terra",
                "CONTEXTFORGE_OPENCODE_SMALL_MODEL": "litellm/codex/gpt-5.6-terra",
                "CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT": "high",
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "LITELLM_API_KEY": "dummy-litellm-test-token",
            }
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                render_config.render_config()

            rendered = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(["litellm"], rendered["enabled_providers"])
            self.assertEqual("litellm/codex/gpt-5.6-terra", rendered["model"])
            self.assertEqual("litellm/codex/gpt-5.6-terra", rendered["small_model"])
            self.assertEqual("high", rendered["agent"]["build"]["variant"])
            self.assertEqual({"litellm"}, set(rendered["provider"]))
            provider = rendered["provider"]["litellm"]
            self.assertEqual("@ai-sdk/openai", provider["npm"])
            self.assertEqual("http://host.docker.internal:3333/v1", provider["options"]["baseURL"])
            self.assertEqual("dummy-litellm-test-token", provider["options"]["apiKey"])
            self.assertEqual(
                {"codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"},
                set(provider["models"]),
            )

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
        self.assertIn("SANDBOX_MODEL_ROLES", runner)
        self.assertIn("selected_profile_env", runner)
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
        self.assertIn("test -f /usr/bin/pi", dockerfile)
        self.assertIn("test -x /usr/bin/pi", dockerfile)
        self.assertIn("! test /usr/bin/pi -ef /usr/local/bin/pi", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)

    def test_pi_image_wraps_bare_pi_for_interactive_harness_sessions(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/pi/Dockerfile").read_text(encoding="utf-8")
        wrapper = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        bootstrap = (ROOT / "docker/client-harness/pi/contextforge-pi-bootstrap.sh").read_text(encoding="utf-8")
        renderer = (ROOT / "docker/client-harness/pi/render-config.py").read_text(encoding="utf-8")
        baseline = (ROOT / "docker/client-harness/config/pi/start-contextforge-baseline.sh").read_text(encoding="utf-8")

        self.assertIn("COPY --chown=agent:agent pi-wrapper.sh /usr/local/bin/pi", dockerfile)
        self.assertIn("COPY --chown=agent:agent render-config.py /usr/local/lib/contextforge-pi-render-config.py", dockerfile)
        self.assertIn(": \"${CONTEXTFORGE_PI_REAL_BIN:=/usr/bin/pi}\"", wrapper)
        self.assertIn(": \"${CONTEXTFORGE_PI_DEFAULT_PROVIDER:=litellm}\"", wrapper)
        self.assertIn(": \"${CONTEXTFORGE_PI_DEFAULT_MODEL:=codex/gpt-5.6-luna}\"", wrapper)
        self.assertIn(": \"${CONTEXTFORGE_PI_DEFAULT_THINKING:=medium}\"", wrapper)
        self.assertIn('CONTEXTFORGE_PI_STANDARD_REAL_BIN="/usr/bin/pi"', wrapper)
        self.assertIn('CONTEXTFORGE_PI_ALPINE_REAL_BIN="/usr/local/bin/contextforge-pi-real"', wrapper)
        self.assertIn("must use an exact image-owned path", wrapper)
        self.assertTrue(wrapper.startswith("#!/bin/bash -p\n"))
        self.assertIn("unset BASH_ENV ENV", wrapper)
        self.assertIn('readonly PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"', wrapper)
        self.assertIn(". /usr/local/bin/contextforge-pi-bootstrap", wrapper)
        self.assertIn("default_args+=(--provider \"${CONTEXTFORGE_PI_DEFAULT_PROVIDER}\")", wrapper)
        self.assertIn("default_args+=(--model \"${CONTEXTFORGE_PI_DEFAULT_MODEL}\")", wrapper)
        self.assertIn("default_args+=(--thinking \"${selected_expected_thinking}\")", wrapper)
        self.assertIn('default_args+=(--models "${CONTEXTFORGE_PI_APPROVED_MODELS}")', wrapper)
        self.assertIn('exec /usr/local/bin/pi "$@"', baseline)
        self.assertNotIn("CONTEXTFORGE_PI_REAL_BIN", baseline)
        self.assertIn("exec \"${CONTEXTFORGE_PI_REAL_BIN}\"", wrapper)
        self.assertIn('cp /config/pi/AGENTS.md "${PI_CODING_AGENT_DIR}/AGENTS.md"', bootstrap)
        self.assertIn("python3 /usr/local/lib/contextforge-pi-render-config.py", bootstrap)
        self.assertIn('"codex/gpt-5.6-terra": "high"', renderer)
        self.assertIn('"codex/gpt-5.6-luna": "medium"', renderer)
        self.assertIn('"codex/gpt-5.6-sol": "high"', renderer)
        self.assertIn('base_url = os.environ.get("LITELLM_BASE_URL"', renderer)
        self.assertIn('provider["baseUrl"] = base_url', renderer)
        self.assertIn('provider["apiKey"] = os.environ["LITELLM_API_KEY"]', renderer)
        self.assertIn('settings["defaultThinkingLevel"]', renderer)
        self.assertIn("Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR", bootstrap)
        self.assertNotIn("/home/dgk/.pi", dockerfile + wrapper + bootstrap + renderer)

    def test_pi_alpine_preserves_real_npm_executable_before_installing_wrapper(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/pi-alpine/Dockerfile").read_text(encoding="utf-8")

        self.assertIn("CONTEXTFORGE_PI_REAL_BIN=/usr/local/bin/contextforge-pi-real", dockerfile)
        self.assertIn('installed_pi="$(command -v pi)"', dockerfile)
        self.assertIn('[ "${installed_pi}" = /usr/local/bin/pi ]', dockerfile)
        self.assertIn('mv "${installed_pi}" /usr/local/bin/contextforge-pi-real', dockerfile)
        self.assertGreaterEqual(dockerfile.count("test -f /usr/local/bin/contextforge-pi-real"), 2)
        self.assertGreaterEqual(dockerfile.count("test -x /usr/local/bin/contextforge-pi-real"), 2)
        self.assertIn("! test /usr/local/bin/contextforge-pi-real -ef /usr/local/bin/pi", dockerfile)
        self.assertIn("COPY --chown=agent:agent pi/pi-wrapper.sh /usr/local/bin/pi", dockerfile)

    def test_pi_wrapper_rejects_non_litellm_arguments_before_bootstrap(self) -> None:
        wrapper = ROOT / "docker/client-harness/pi/pi-wrapper.sh"
        base_env = {
            **os.environ,
            "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
            "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
            "CONTEXTFORGE_PI_DEFAULT_THINKING": "medium",
            "CONTEXTFORGE_PI_REAL_BIN": "/bin/true",
        }
        cases = [
            (["--provider", "openai-codex"], {}, "unsupported Pi sandbox provider"),
            (["--provider=openrouter"], {}, "unsupported Pi sandbox provider"),
            (["--provider=litellm"], {}, "requires '--provider litellm' syntax"),
            (["--model", "gpt-5.5"], {}, "unsupported Pi sandbox model"),
            (["--model=openai/gpt-5.5"], {}, "unsupported Pi sandbox model"),
            (["--model=codex/gpt-5.6-luna"], {}, "requires '--model MODEL' syntax"),
            (
                ["--model", "codex/gpt-5.6-terra", "--thinking", "medium"],
                {},
                "thinking level",
            ),
            (["--list-models", "openai"], {}, "unsupported Pi sandbox provider"),
            (["--list-models=litellm"], {}, "requires '--list-models litellm' syntax"),
            (["--thinking=medium"], {}, "requires '--thinking LEVEL' syntax"),
            (["--models", "openai/gpt-4o"], {}, "--models is fixed"),
            (["--models=openrouter/auto"], {}, "--models is fixed"),
            (["--api-key", "dummy-secret"], {}, "--api-key is forbidden"),
            (["--api-key=dummy-secret"], {}, "--api-key is forbidden"),
            (["--provider", "litellm", "--provider", "litellm"], {}, "repeated --provider"),
            (
                ["--model", "codex/gpt-5.6-luna", "--model", "codex/gpt-5.6-luna"],
                {},
                "repeated --model",
            ),
            (["--thinking", "medium", "--thinking", "medium"], {}, "repeated --thinking"),
            ([], {"CONTEXTFORGE_PI_DEFAULT_PROVIDER": "openai"}, "unsupported Pi sandbox provider"),
            ([], {"CONTEXTFORGE_PI_DEFAULT_MODEL": "gpt-5.5"}, "unsupported Pi sandbox model"),
            ([], {"CONTEXTFORGE_PI_DEFAULT_THINKING": "high"}, "thinking level"),
        ]
        for arguments, overrides, expected_error in cases:
            with self.subTest(arguments=arguments, overrides=overrides):
                completed = subprocess.run(
                    ["bash", str(wrapper), *arguments],
                    cwd=ROOT,
                    env={**base_env, **overrides},
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(2, completed.returncode)
                self.assertIn(expected_error, completed.stderr)

    def test_pi_wrapper_rejects_invalid_real_executables_without_bootstrap_side_effects(self) -> None:
        source = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = [
                ("missing", "missing", "missing or not executable"),
                ("directory", "directory", "missing or not executable"),
                ("non-executable", "non-executable", "missing or not executable"),
                ("broken-symlink", "broken-symlink", "missing or not executable"),
                ("wrapper", "wrapper", "must not resolve to the wrapper"),
                ("wrapper-symlink", "wrapper-symlink", "must not resolve to the wrapper"),
                ("wrapper-hardlink", "wrapper-hardlink", "must not resolve to the wrapper"),
            ]
            for slug, target_kind, expected_error in cases:
                with self.subTest(slug=slug):
                    case_root = root / slug
                    case_root.mkdir()
                    wrapper = case_root / "pi-wrapper"
                    real_bin = wrapper if target_kind == "wrapper" else case_root / "real-pi"
                    wrapper.write_text(
                        source.replace(
                            'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="/usr/bin/pi"',
                            f'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="{real_bin}"',
                        ),
                        encoding="utf-8",
                    )
                    wrapper.chmod(0o755)
                    if target_kind == "directory":
                        real_bin.mkdir()
                    elif target_kind == "non-executable":
                        real_bin.write_text("not executable\n", encoding="utf-8")
                    elif target_kind == "broken-symlink":
                        real_bin.symlink_to(case_root / "missing-target")
                    elif target_kind == "wrapper-symlink":
                        real_bin.symlink_to(wrapper)
                    elif target_kind == "wrapper-hardlink":
                        os.link(wrapper, real_bin)
                    agent_dir = case_root / "agent"
                    runtime_dir = case_root / "runtime"
                    approval_path = case_root / "approval.json"
                    completed = subprocess.run(
                        ["bash", str(wrapper), "--version"],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "CONTEXTFORGE_PI_REAL_BIN": str(real_bin),
                            "PI_CODING_AGENT_DIR": str(agent_dir),
                            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT": str(runtime_dir),
                            "CONTEXTFORGE_HELPER_APPROVAL_SOURCE_PATH": str(approval_path),
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(2, completed.returncode)
                    self.assertIn(expected_error, completed.stderr)
                    self.assertFalse(agent_dir.exists())
                    self.assertFalse(runtime_dir.exists())
                    self.assertFalse(approval_path.exists())

            for slug, real_bin in [
                ("standard-dot", "/usr/bin/../bin/pi"),
                ("standard-double-slash", "//usr/bin/pi"),
                ("alpine-dot", "/usr/local/bin/./contextforge-pi-real"),
                ("alpine-parent", "/usr/local/bin/../bin/contextforge-pi-real"),
            ]:
                with self.subTest(slug=slug):
                    case_root = root / slug
                    case_root.mkdir()
                    wrapper = case_root / "pi-wrapper"
                    wrapper.write_text(source, encoding="utf-8")
                    wrapper.chmod(0o755)
                    agent_dir = case_root / "agent"
                    runtime_dir = case_root / "runtime"
                    completed = subprocess.run(
                        [str(wrapper), "--version"],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "CONTEXTFORGE_PI_REAL_BIN": real_bin,
                            "PI_CODING_AGENT_DIR": str(agent_dir),
                            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT": str(runtime_dir),
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(2, completed.returncode)
                    self.assertIn("must use an exact image-owned path", completed.stderr)
                    self.assertFalse(agent_dir.exists())
                    self.assertFalse(runtime_dir.exists())

            for slug, payload in [
                ("arbitrary-executable", '#!/usr/bin/env bash\nexit 0\n'),
                ("copied-wrapper", source),
                ("modified-wrapper", source + "\n# modified copy\n"),
            ]:
                with self.subTest(slug=slug):
                    case_root = root / slug
                    case_root.mkdir()
                    wrapper = case_root / "pi-wrapper"
                    wrapper.write_text(source, encoding="utf-8")
                    wrapper.chmod(0o755)
                    real_bin = case_root / "real-pi"
                    real_bin.write_text(payload, encoding="utf-8")
                    real_bin.chmod(0o755)
                    agent_dir = case_root / "agent"
                    runtime_dir = case_root / "runtime"
                    completed = subprocess.run(
                        ["bash", str(wrapper), "--version"],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "CONTEXTFORGE_PI_REAL_BIN": str(real_bin),
                            "PI_CODING_AGENT_DIR": str(agent_dir),
                            "CONTEXTFORGE_PROJECT_INIT_RUN_ROOT": str(runtime_dir),
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(2, completed.returncode)
                    self.assertIn("must use an exact image-owned path", completed.stderr)
                    self.assertFalse(agent_dir.exists())
                    self.assertFalse(runtime_dir.exists())

    def test_pi_wrapper_ignores_shell_startup_and_path_injection(self) -> None:
        source = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "injection-marker"
            real_pi = root / "real-pi"
            real_pi.write_text(
                "#!/bin/bash\n"
                '[[ -z "${BASH_ENV:-}" && -z "${ENV:-}" ]] || exit 91\n'
                '[[ "${PATH}" == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" ]] || exit 92\n'
                'printf "real-pi-ok\\n"\n',
                encoding="utf-8",
            )
            real_pi.chmod(0o755)
            bootstrap = root / "bootstrap"
            bootstrap.write_text(":\n", encoding="utf-8")
            wrapper = root / "pi"
            wrapper.write_text(
                source.replace(
                    ". /usr/local/bin/contextforge-pi-bootstrap",
                    f'. "{bootstrap}"',
                ).replace(
                    'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="/usr/bin/pi"',
                    f'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="{real_pi}"',
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            wrapper_symlink = root / "pi-symlink"
            wrapper_symlink.symlink_to(wrapper)
            wrapper_hardlink = root / "pi-hardlink"
            os.link(wrapper, wrapper_hardlink)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_bash = fake_bin / "bash"
            fake_bash.write_text(
                f'#!/bin/sh\nprintf fake-bash > "{marker}"\nexit 93\n',
                encoding="utf-8",
            )
            fake_bash.chmod(0o755)
            bash_env = root / "bash-env"
            bash_env.write_text(
                f'printf bash-env > "{marker}"\nvalidate_provider() {{ return 0; }}\n',
                encoding="utf-8",
            )
            for invocation in [wrapper, wrapper_symlink, wrapper_hardlink]:
                with self.subTest(invocation=invocation.name):
                    marker.unlink(missing_ok=True)
                    completed = subprocess.run(
                        [str(invocation), "--version"],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
                            "BASH_ENV": str(bash_env),
                            "ENV": str(bash_env),
                            "BASH_FUNC_validate_provider%%": f"() {{ printf function > '{marker}'; }}",
                            "CONTEXTFORGE_PI_REAL_BIN": str(real_pi),
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(0, completed.returncode, completed.stderr)
                    self.assertEqual("real-pi-ok", completed.stdout.strip())
                    self.assertFalse(marker.exists())

    def test_pi_wrapper_injects_approved_model_scope_and_role_thinking(self) -> None:
        source = (ROOT / "docker/client-harness/pi/pi-wrapper.sh").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_pi = root / "real-pi"
            real_pi.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
            real_pi.chmod(0o755)
            wrapper = root / "pi"
            wrapper.write_text(
                source.replace(
                    ". /usr/local/bin/contextforge-pi-bootstrap",
                    '. "${CONTEXTFORGE_TEST_BOOTSTRAP}"',
                ).replace(
                    'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="/usr/bin/pi"',
                    f'readonly CONTEXTFORGE_PI_STANDARD_REAL_BIN="{real_pi}"',
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            bootstrap = root / "bootstrap.sh"
            bootstrap.write_text(":\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    str(wrapper),
                    "--provider",
                    "litellm",
                    "--model",
                    "codex/gpt-5.6-terra",
                    "-p",
                    "hello",
                ],
                cwd=ROOT,
                env={
                    **os.environ,
                    "CONTEXTFORGE_PI_REAL_BIN": str(real_pi),
                    "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
                    "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
                    "CONTEXTFORGE_PI_DEFAULT_THINKING": "medium",
                    "CONTEXTFORGE_TEST_BOOTSTRAP": str(bootstrap),
                },
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            [
                "--thinking",
                "high",
                "--models",
                "litellm/codex/gpt-5.6-terra,litellm/codex/gpt-5.6-luna,litellm/codex/gpt-5.6-sol",
                "--provider",
                "litellm",
                "--model",
                "codex/gpt-5.6-terra",
                "-p",
                "hello",
            ],
            completed.stdout.splitlines(),
        )

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

    def test_pi_shim_allows_only_constrained_ssh_tmux_live_probe(self) -> None:
        shim = (ROOT / "pi-extensions/contextforge-global-shim/index.ts").read_text(encoding="utf-8")

        self.assertIn('const SSH_TMUX_LIVE_TARGET_ALIAS = "contextforge-live-target"', shim)
        self.assertIn('const SSH_TMUX_LIVE_PROBE_COMMAND = "printf contextforge-ssh-tmux-ok"', shim)
        self.assertIn("function isAllowedSshTmuxLiveProbe", shim)
        self.assertIn('String(params.host || "") === SSH_TMUX_LIVE_TARGET_ALIAS', shim)
        self.assertIn('String(params.command || "").trim() === SSH_TMUX_LIVE_PROBE_COMMAND', shim)
        self.assertIn('toolKey.includes("close-session")', shim)
        self.assertIn("route.blockedByDefault && !isAllowedSshTmuxLiveProbe(route, callParams)", shim)

    def test_pi_and_opencode_use_exact_litellm_semantic_model_contract(self) -> None:
        pi_models = json.loads((ROOT / "docker/client-harness/config/pi/models.json").read_text(encoding="utf-8"))
        pi_settings = json.loads((ROOT / "docker/client-harness/config/pi/settings.json").read_text(encoding="utf-8"))
        opencode_config = json.loads((ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8"))
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        env_example = (ROOT / "docker/client-harness/env/semantic-model.env.example").read_text(encoding="utf-8")
        expected = {"codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"}

        self.assertIn('LITELLM_API_KEY: "${LITELLM_API_KEY:-}"', compose)
        self.assertIn('LITELLM_BASE_URL: "${LITELLM_BASE_URL:-http://host.docker.internal:3333/v1}"', compose)
        self.assertIn('OPENROUTER_API_KEY: ""', compose)
        self.assertIn("LITELLM_API_KEY=replace-with-litellm-secret", env_example)
        self.assertNotIn("OPENROUTER_", env_example)
        self.assertNotIn("LOCAL_LLAMA", env_example)

        self.assertEqual({"litellm"}, set(pi_models["providers"]))
        pi_provider = pi_models["providers"]["litellm"]
        self.assertEqual("$LITELLM_BASE_URL", pi_provider["baseUrl"])
        self.assertEqual("$LITELLM_API_KEY", pi_provider["apiKey"])
        self.assertEqual("openai-responses", pi_provider["api"])
        self.assertTrue(pi_provider["compat"]["supportsReasoningEffort"])
        self.assertEqual(expected, {model["id"] for model in pi_provider["models"]})
        self.assertTrue(all(model["reasoning"] and model["thinkingLevelMap"] for model in pi_provider["models"]))
        self.assertEqual("litellm", pi_settings["defaultProvider"])
        self.assertEqual("codex/gpt-5.6-luna", pi_settings["defaultModel"])
        self.assertEqual("medium", pi_settings["defaultThinkingLevel"])
        self.assertEqual({f"litellm/{model}" for model in expected}, set(pi_settings["enabledModels"]))
        self.assertEqual(
            {
                "codex/gpt-5.6-terra": 1050000,
                "codex/gpt-5.6-luna": 1050000,
                "codex/gpt-5.6-sol": 350000,
            },
            {model["id"]: model["contextWindow"] for model in pi_provider["models"]},
        )

        self.assertEqual(["litellm"], opencode_config["enabled_providers"])
        self.assertEqual("litellm/codex/gpt-5.6-luna", opencode_config["model"])
        self.assertEqual("litellm/codex/gpt-5.6-luna", opencode_config["small_model"])
        self.assertEqual({"litellm"}, set(opencode_config["provider"]))
        litellm_provider = opencode_config["provider"]["litellm"]
        self.assertEqual("@ai-sdk/openai", litellm_provider["npm"])
        self.assertEqual(expected, set(litellm_provider["models"]))
        self.assertEqual(expected, set(litellm_provider["whitelist"]))
        self.assertEqual({"high"}, set(litellm_provider["models"]["codex/gpt-5.6-terra"]["variants"]))
        self.assertEqual({"medium"}, set(litellm_provider["models"]["codex/gpt-5.6-luna"]["variants"]))
        self.assertEqual({"high"}, set(litellm_provider["models"]["codex/gpt-5.6-sol"]["variants"]))
        self.assertIn("contextforge-helper", opencode_config["mcp"])

    def test_semantic_model_profiles_are_provider_abstract_and_run_scoped(self) -> None:
        profiles_doc = json.loads((ROOT / "docker/client-harness/semantic-model-profiles.json").read_text(encoding="utf-8"))
        runner = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py").read_text(encoding="utf-8")
        models = {profile["model"]: profile for profile in profiles_doc["profiles"]}

        self.assertEqual("per_test_run", profiles_doc["selection_scope"])
        self.assertEqual("default", profiles_doc["default_selection_mode"])
        self.assertEqual(
            {"codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"},
            set(models),
        )
        self.assertEqual("human", models["codex/gpt-5.6-terra"]["semantic_role"])
        self.assertEqual("high", models["codex/gpt-5.6-terra"]["reasoning_effort"])
        self.assertEqual("blind", models["codex/gpt-5.6-luna"]["semantic_role"])
        self.assertEqual("medium", models["codex/gpt-5.6-luna"]["reasoning_effort"])
        self.assertTrue(models["codex/gpt-5.6-luna"]["default"])
        self.assertEqual("evaluator", models["codex/gpt-5.6-sol"]["semantic_role"])
        self.assertEqual("high", models["codex/gpt-5.6-sol"]["reasoning_effort"])
        for profile in profiles_doc["profiles"]:
            self.assertEqual("litellm", profile["provider_kind"])
            self.assertEqual("LITELLM_API_KEY", profile["api_key_env"])
            self.assertEqual("LITELLM_BASE_URL", profile["base_url_env"])
            self.assertGreaterEqual(profile["context_window"], 262144)

        self.assertIn("--semantic-model-profile", runner)
        self.assertIn('if selector == "random"', runner)
        self.assertIn("profile_multi_step_quorum_eligible(profile)", runner)
        self.assertIn("random.choices", runner)
        self.assertIn("MIN_SEMANTIC_CONTEXT_WINDOW = 262144", runner)
        self.assertIn("profile_context_window(profile) >= MIN_SEMANTIC_CONTEXT_WINDOW", runner)
        self.assertIn("route_preferences(profile)", runner)
        self.assertIn('env["CONTEXTFORGE_PI_DEFAULT_PROVIDER"] = "litellm"', runner)
        self.assertIn('env["CONTEXTFORGE_PI_DEFAULT_THINKING"]', runner)
        self.assertIn('env["CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT"]', runner)
        self.assertIn('if selector == "default"', runner)
        self.assertIn('"selection_scope": "per_test_run"', runner)
        self.assertIn('"minimum_context_window"', runner)
        self.assertIn('"api_key_present"', runner)
        self.assertIn("container_receives_real_semantic_model_api_key(", runner)
        self.assertIn("API_KEY_ENV_NAMES", runner)
        self.assertNotIn('launch_command.extend(["-e", key])', runner)
        self.assertNotIn('launch_command.extend(["-e", f"{key}={os.environ[key]}"])', runner)

    def test_litellm_sandbox_runners_do_not_start_non_litellm_proxy(self) -> None:
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        comprehensive_runner = (
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py"
        ).read_text(encoding="utf-8")
        onboarding_runner = (
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("env_file:\n    - ./env/semantic-model.env", compose)
        self.assertIn('OPENROUTER_API_KEY: ""', compose)
        for runner in [comprehensive_runner, onboarding_runner]:
            self.assertNotIn("start_openrouter_proxy", runner)
            self.assertNotIn("OPENROUTER_BASE_URL", runner)
            self.assertIn("container_receives_real_semantic_model_api_key", runner)
            self.assertIn("assistant_error_from_json_stream", runner)
            self.assertNotIn('for key in semantic_secret_env_keys_to_pass:\n            launch_command.extend(["-e", key])', runner)

    def test_litellm_credential_delivery_evidence_matches_container_boundary(self) -> None:
        runner = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
            "comprehensive_mcp_credential_delivery_test",
        )

        self.assertTrue(
            runner.container_receives_real_semantic_model_api_key(
                ["LITELLM_API_KEY"],
                {"LITELLM_API_KEY": "present"},
            )
        )
        self.assertFalse(
            runner.container_receives_real_semantic_model_api_key(
                ["LITELLM_API_KEY"],
                {},
            )
        )
        process_env = runner.semantic_model_compose_process_env(
            {"HARNESS_SCOPE": "isolated", "LITELLM_API_KEY": "host-value-must-not-win"},
            ["LITELLM_API_KEY"],
        )
        self.assertEqual("isolated", process_env["HARNESS_SCOPE"])
        self.assertNotIn("LITELLM_API_KEY", process_env)
        self.assertEqual("", process_env["OPENROUTER_API_KEY"])

    def test_semantic_runners_detect_structured_assistant_errors(self) -> None:
        for script_name, module_name in [
            ("run-comprehensive-mcp-service-dialogue.py", "comprehensive_mcp_error_detection"),
            ("run-onboarding-semantic-process-dialogue.py", "onboarding_semantic_error_detection"),
        ]:
            spec = importlib.util.spec_from_file_location(
                module_name,
                ROOT / "docker/client-harness/scripts" / script_name,
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(
                "Connection error.",
                module.assistant_error_from_json_stream(
                    '{"type":"message_end","message":{"stopReason":"error","errorMessage":"Connection error."}}\n'
                ),
            )
            self.assertIsNone(
                module.assistant_error_from_json_stream(
                    '{"type":"message_end","message":{"stopReason":"stop","content":[{"type":"text","text":"ok"}]}}\n'
                )
        )

    def test_onboarding_runner_parses_structured_simulated_human_stop_signal(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_human_stop_signal",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        message, should_continue, structured = module.parse_simulated_human_response(
            '{"message":"Thanks, that is sufficient.","continue_conversation":false}'
        )

        self.assertEqual("Thanks, that is sufficient.", message)
        self.assertFalse(should_continue)
        self.assertTrue(structured)

        fallback_message, fallback_continue, fallback_structured = module.parse_simulated_human_response(
            "Please show the rollback boundary."
        )
        self.assertEqual("Please show the rollback boundary.", fallback_message)
        self.assertTrue(fallback_continue)
        self.assertFalse(fallback_structured)

    def test_onboarding_runner_extracts_only_visible_pi_assistant_text(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_visible_text",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stream = "\n".join(
            [
                '{"type":"message_end","message":{"role":"custom","customType":"contextforge-project-init-first-prompt","content":"hidden route context"}}',
                '{"type":"message_end","message":{"role":"assistant","content":[{"type":"toolCall","name":"cf_project_service_onboarding_plan"}]}}',
                '{"type":"message_update","assistantMessageEvent":{"message":{"role":"assistant","content":[{"type":"text","text":"partial visible"}]}}}',
                '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"final visible"}]}}',
            ]
        )

        self.assertEqual("final visible", module.assistant_visible_text_from_json_stream(stream))

    def test_onboarding_runner_visible_text_uses_latest_update_when_no_message_end(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_visible_text_update",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stream = "\n".join(
            [
                '{"type":"message_update","assistantMessageEvent":{"message":{"role":"assistant","content":[{"type":"text","text":"part"}]}}}',
                '{"type":"message_update","assistantMessageEvent":{"message":{"role":"assistant","content":[{"type":"text","text":"part done"}]}}}',
            ]
        )

        self.assertEqual("part done", module.assistant_visible_text_from_json_stream(stream))

    def test_onboarding_runner_reports_structural_post_apply_target_client_evidence(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_post_apply_structural_evidence",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        apply_stdout = "\n".join(
            [
                '{"type":"session","id":"target-session-before-reload"}',
                '{"type":"turn_end","message":{"role":"assistant","responseId":"r1","usage":{"input":10,"output":4,"totalTokens":14},"content":[{"type":"toolCall","id":"call-apply","name":"cf_project_service_onboarding_runtime_execute","arguments":{"projectRoot":"/workspace","runtimeApplyPackageId":"rap_ok"}}]},"toolResults":[{"role":"toolResult","toolCallId":"call-apply","toolName":"cf_project_service_onboarding_runtime_execute","isError":false,"content":[{"type":"text","text":"{\\"ok\\":true,\\"status\\":\\"service_onboarding_runtime_applied\\",\\"mutation_performed\\":true}"}]}]}',
            ]
        )
        service_stdout = "\n".join(
            [
                '{"type":"session","id":"target-session-after-reload"}',
                '{"type":"turn_end","message":{"role":"assistant","responseId":"r2","usage":{"input":8,"output":3,"totalTokens":11},"content":[{"type":"toolCall","id":"call-service","name":"memory-gateway-create-entities","arguments":{"entities":[]}}]},"toolResults":[{"role":"toolResult","toolCallId":"call-service","toolName":"memory-gateway-create-entities","isError":false,"content":[{"type":"text","text":"{}"}]}]}',
            ]
        )
        turns = []
        for index, stdout in enumerate([apply_stdout, service_stdout], start=1):
            structural = module.extract_turn_structural_events(stdout)
            turns.append(
                {
                    "turn": index,
                    "prompt": f"prompt {index}",
                    "path": f"/tmp/turn-{index}.raw.txt",
                    "assistant_visible_path": f"/tmp/turn-{index}.assistant-visible.txt",
                    "target_session_id": (
                        "target-session-before-reload"
                        if index == 1
                        else "target-session-after-reload"
                    ),
                    "returncode": 0,
                    "timeout": False,
                    "assistant_visible_chars": 12,
                    **structural,
                }
            )

        proof = module.build_structural_onboarding_proof_report(turns)
        generation_report = module.build_generation_report(client="pi", session_id="target-session-after-reload", turns=turns)

        self.assertTrue(proof["runtime_apply"]["success_detected"])
        self.assertEqual(
            "candidate_events_present_requires_semantic_evaluator",
            proof["post_apply_target_client_evidence"]["proof_status"],
        )
        self.assertTrue(proof["post_apply_target_client_evidence"]["fresh_session_after_runtime_apply_detected"])
        self.assertTrue(
            proof["post_apply_target_client_evidence"]["candidate_target_client_service_tool_call_detected"]
        )
        self.assertEqual(
            "memory-gateway-create-entities",
            proof["post_apply_target_client_evidence"]["candidate_target_client_service_tool_calls"][0]["name"],
        )
        self.assertIn("does not judge free-form meaning", proof["deterministic_scope"])
        self.assertEqual(2, generation_report["totals"]["generation_step_count"])
        self.assertEqual(2, generation_report["totals"]["tool_call_count"])
        self.assertEqual(2, generation_report["totals"]["tool_result_count"])
        self.assertEqual(
            "target-session-before-reload",
            generation_report["step_generations"][0]["session_id"],
        )
        self.assertEqual(
            "target-session-after-reload",
            generation_report["step_generations"][1]["session_id"],
        )
        self.assertIn("not_semantic", generation_report["step_generations"][0]["deterministic_evaluation"])

    def test_onboarding_runner_parses_pi_tool_execution_end_after_start_event(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_tool_execution_end_parse",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stdout = "\n".join(
            [
                '{"type":"session","id":"target-session-before-reload"}',
                '{"type":"message_end","message":{"role":"assistant","content":[{"type":"toolCall","id":"call-apply","name":"cf_project_service_onboarding_runtime_execute","arguments":{"runtimeApplyPackageId":"rap_ok"}}]}}',
                '{"type":"tool_execution_start","toolCallId":"call-apply","toolName":"cf_project_service_onboarding_runtime_execute","args":{"runtimeApplyPackageId":"rap_ok"}}',
                '{"type":"tool_execution_end","toolCallId":"call-apply","toolName":"cf_project_service_onboarding_runtime_execute","isError":false,"result":{"content":[{"type":"text","text":"{\\"ok\\":true,\\"status\\":\\"service_onboarding_runtime_applied\\",\\"mutation_performed\\":true}"}],"isError":false}}',
                '{"type":"message_end","message":{"role":"toolResult","toolCallId":"call-apply","toolName":"cf_project_service_onboarding_runtime_execute","isError":false,"content":[{"type":"text","text":"{\\"ok\\":true,\\"status\\":\\"service_onboarding_runtime_applied\\",\\"mutation_performed\\":true}"}]}}',
            ]
        )

        structural = module.extract_turn_structural_events(stdout)

        self.assertEqual(1, len(structural["tool_results"]))
        self.assertEqual("service_onboarding_runtime_applied", structural["tool_results"][0]["parsed_status"])
        self.assertTrue(structural["tool_results"][0]["parsed_ok"])
        self.assertTrue(structural["tool_results"][0]["mutation_performed"])
        success = module.turn_runtime_apply_success({"turn": 3, **structural})
        self.assertIsNotNone(success)
        assert success is not None
        self.assertEqual(3, success["turn"])
        self.assertEqual("service_onboarding_runtime_applied", success["status"])
        self.assertFalse(module.is_candidate_target_client_service_tool("cf_contextforge_pi_readback"))
        self.assertFalse(module.is_candidate_target_client_service_tool("cf_project_init_list_capabilities"))
        self.assertTrue(module.is_candidate_target_client_service_tool("memory-gateway-read-graph"))

    def test_onboarding_runner_passes_fresh_session_fact_only_to_human_simulator(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_fresh_session_human_context",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prompt = module.pi_responder_prompt(
            {"source_lead": "https://example.test/mcp"},
            {
                "domain_knowledge": "ignorant",
                "goal_specificity": "outcome_oriented",
                "risk_posture": "cautious",
                "technical_fluency": "nontechnical",
                "interaction_style": "cooperative",
            },
            help_determination=15,
            turn_index=4,
            previous_user_prompt="approve",
            previous_assistant_output="Please start a new session before claiming usability.",
            runner_observation="A fresh/reloaded target-client session has been started before this next assistant turn.",
        )

        self.assertIn("Actual operator/session fact now visible to you as the human user", prompt)
        self.assertIn("fresh/reloaded target-client session", prompt)
        self.assertNotIn("memory-gateway-read-graph", prompt)

    def test_onboarding_runner_marks_missing_fresh_session_after_runtime_apply(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_missing_fresh_session",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stdout = "\n".join(
            [
                '{"type":"session","id":"same-session"}',
                '{"type":"turn_end","message":{"role":"assistant","content":[{"type":"toolCall","id":"call-apply","name":"cf_project_service_onboarding_runtime_execute","arguments":{"runtimeApplyPackageId":"rap_ok"}}]},"toolResults":[{"role":"toolResult","toolCallId":"call-apply","toolName":"cf_project_service_onboarding_runtime_execute","content":[{"type":"text","text":"{\\"ok\\":true,\\"status\\":\\"service_onboarding_runtime_applied\\",\\"mutation_performed\\":true}"}]}]}',
            ]
        )
        structural = module.extract_turn_structural_events(stdout)
        proof = module.build_structural_onboarding_proof_report(
            [
                {
                    "turn": 1,
                    "prompt": "approved apply",
                    "path": "/tmp/turn-1.raw.txt",
                    "assistant_visible_path": "/tmp/turn-1.assistant-visible.txt",
                    "returncode": 0,
                    "timeout": False,
                    "assistant_visible_chars": 0,
                    **structural,
                }
            ]
        )

        self.assertEqual(
            "missing_fresh_or_reloaded_target_client_session_structural_evidence",
            proof["post_apply_target_client_evidence"]["proof_status"],
        )
        self.assertFalse(proof["post_apply_target_client_evidence"]["candidate_target_client_service_tool_call_detected"])

    def test_onboarding_runner_exports_native_pi_transcripts_to_tmp_paths(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_native_pi_transcript_export",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            path = module.native_pi_transcript_export_path(
                role="target",
                session_id="onboarding/memory pi:bad chars",
                tmp_dir=Path(tmp),
            )

        self.assertEqual("contextforge-native-pi-target-onboarding_memory_pi_bad_chars.jsonl", path.name)
        source = (ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("copy_native_pi_session_transcript", source)
        self.assertIn("/home/agent/.pi/agent/sessions", source)
        self.assertIn("/home/agent/.pi/human-sim-sessions", source)
        self.assertIn('"evidence_exports"', source)
        self.assertIn("native-transcript-exports.json", source)

    def test_onboarding_runner_supplies_host_runtime_apply_proxy_to_client_container(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from runtime_apply_host_proxy import start_runtime_apply_host_proxy", source)
        self.assertIn("CONTEXTFORGE_RUNTIME_APPLY_PROXY_URL", source)
        self.assertIn("CONTEXTFORGE_RUNTIME_APPLY_PROXY_TOKEN", source)
        self.assertIn("CONTEXTFORGE_RUNTIME_APPLY_PROXY_BASE_URL", source)
        self.assertIn("runtime_apply_host_proxy.summary()", source)

        proxy = (ROOT / "docker/client-harness/scripts/runtime_apply_host_proxy.py").read_text(encoding="utf-8")
        self.assertIn("ContextForgeRuntimeApplyProxy", proxy)
        self.assertIn("host.docker.internal", proxy)
        self.assertIn("apply_onboarding_runtime_package.py", proxy)
        self.assertIn("ephemeral_redacted", proxy)

    def test_onboarding_runner_redacts_runtime_apply_proxy_token_from_summary(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "onboarding_semantic_redacted_summary",
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run-summary.json"
            module.write_redacted_summary(
                path,
                {
                    "command_ledger": [
                        {
                            "command_text": "docker run -e CONTEXTFORGE_RUNTIME_APPLY_PROXY_TOKEN=secret-token pi",
                            "cwd": "/tmp",
                            "returncode": 0,
                            "timeout": False,
                        }
                    ],
                    "runtime_apply_host_proxy": {"token": "secret-token"},
                },
            )
            text = path.read_text(encoding="utf-8")

        self.assertNotIn("secret-token", text)
        self.assertIn("[REDACTED_CONTEXTFORGE_SECRET]", text)

    def test_runtime_apply_host_proxy_maps_only_executor_paths_to_host_root(self) -> None:
        module = _load_script_module(
            ROOT / "docker/client-harness/scripts/runtime_apply_host_proxy.py",
            "runtime_apply_host_proxy_path_map",
        )
        package = {
            "project_root": "/workspace",
            "service_provision_plan": {
                "x_backend_home": "/workspace/server-instances/memory-canonical",
            },
            "install_artifact_contract": {
                "artifacts": {
                    "npm_stdio_service_record": {
                        "path": "/workspace/server-instances/memory-canonical/npm-stdio-service.json",
                        "content": {
                            "environment": {
                                "values": {
                                    "MEMORY_FILE_PATH": "/workspace/.contextforge/memory/memory.jsonl",
                                }
                            }
                        },
                    }
                }
            },
        }

        translated = module.translate_package_paths_for_host(package, repo_root=ROOT)

        self.assertEqual(str(ROOT), translated["project_root"])
        self.assertEqual(
            str(ROOT / "server-instances/memory-canonical"),
            translated["service_provision_plan"]["x_backend_home"],
        )
        self.assertEqual(
            str(ROOT / "server-instances/memory-canonical/npm-stdio-service.json"),
            translated["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["path"],
        )
        self.assertEqual(
            "/workspace/.contextforge/memory/memory.jsonl",
            translated["install_artifact_contract"]["artifacts"]["npm_stdio_service_record"]["content"]["environment"]["values"]["MEMORY_FILE_PATH"],
        )

    def test_luna_is_the_single_default_semantic_profile(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profiles = module.load_semantic_model_profiles(ROOT / "docker/client-harness")
        selected = module.choose_semantic_model_profile(
            ROOT / "docker/client-harness",
            "pi",
            "default",
            {"LITELLM_API_KEY": "present"},
        )
        random_candidates = [
            profile
            for profile in profiles
            if module.profile_supports_client(profile, "pi")
            and module.profile_available(profile, {"LITELLM_API_KEY": "present"})
            and module.profile_context_window(profile) >= module.MIN_SEMANTIC_CONTEXT_WINDOW
            and module.profile_weight(profile) > 0
            and module.profile_multi_step_quorum_eligible(profile)
        ]

        self.assertEqual("litellm-codex-gpt-5.6-luna", selected["id"])
        self.assertEqual("blind", selected["semantic_role"])
        self.assertEqual("medium", selected["reasoning_effort"])
        self.assertEqual(["litellm-codex-gpt-5.6-luna"], [profile["id"] for profile in random_candidates])
        for forbidden_profile in ["litellm-codex-gpt-5.6-terra", "litellm-codex-gpt-5.6-sol"]:
            with self.subTest(forbidden_profile=forbidden_profile):
                with self.assertRaisesRegex(RuntimeError, "not available for tested-assistant role"):
                    module.choose_semantic_model_profile(
                        ROOT / "docker/client-harness",
                        "pi",
                        forbidden_profile,
                        {"LITELLM_API_KEY": "present"},
                    )

    def test_env_semantic_model_selector_builds_litellm_reasoning_profile(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        profile = module.choose_semantic_model_profile(
            ROOT / "docker/client-harness",
            "pi",
            "env",
            {
                "CONTEXTFORGE_TEST_PROVIDER": "litellm",
                "CONTEXTFORGE_TEST_MODEL": "codex/gpt-5.6-luna",
                "CONTEXTFORGE_TEST_CONTEXT_WINDOW": "272000",
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "LITELLM_API_KEY": "present",
            },
        )
        env, secret_keys = module.selected_profile_env(profile, "pi", {"LITELLM_API_KEY": "present"})

        self.assertEqual("env", profile["id"])
        self.assertEqual("litellm", profile["provider_kind"])
        self.assertEqual("codex/gpt-5.6-luna", profile["model"])
        self.assertEqual(["LITELLM_API_KEY"], secret_keys)
        self.assertEqual("litellm", env["CONTEXTFORGE_PI_DEFAULT_PROVIDER"])
        self.assertEqual("codex/gpt-5.6-luna", env["CONTEXTFORGE_PI_DEFAULT_MODEL"])
        self.assertEqual("medium", env["CONTEXTFORGE_PI_DEFAULT_THINKING"])
        self.assertEqual("medium", env["CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT"])
        self.assertEqual("http://host.docker.internal:3333/v1", env["LITELLM_BASE_URL"])

    def test_semantic_quorums_repeat_only_luna_for_tested_assistant_role(self) -> None:
        service_runner = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
            "role_correct_service_runner_test",
        )
        comprehensive = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-model-quorum.py",
            "role_correct_comprehensive_quorum_test",
        )
        onboarding = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-quorum.py",
            "role_correct_onboarding_quorum_test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            harness_root = Path(tmp)
            (harness_root / "env").mkdir()
            (harness_root / "semantic-model-profiles.json").write_text(
                (ROOT / "docker/client-harness/semantic-model-profiles.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (harness_root / "env/semantic-model.env").write_text(
                "LITELLM_API_KEY=dummy-test-key\n"
                "LITELLM_BASE_URL=http://host.docker.internal:3333/v1\n",
                encoding="utf-8",
            )
            available_env = service_runner.read_env(harness_root / "env/semantic-model.env")
            comprehensive_runs = comprehensive.select_profiles(
                service_runner,
                harness_root,
                "pi",
                available_env,
                [],
                3,
            )
            onboarding_runs = onboarding.select_profiles(
                service_runner,
                harness_root,
                "opencode",
                [],
                3,
            )
            self.assertEqual(3, len(comprehensive_runs))
            self.assertEqual(3, len(onboarding_runs))
            for run_profile in [*comprehensive_runs, *onboarding_runs]:
                self.assertEqual("codex/gpt-5.6-luna", run_profile["model"])
                self.assertEqual("blind", run_profile["semantic_role"])
                self.assertEqual("medium", run_profile["reasoning_effort"])
            with self.assertRaisesRegex(RuntimeError, "blind-agent Luna"):
                comprehensive.select_profiles(
                    service_runner,
                    harness_root,
                    "pi",
                    available_env,
                    ["litellm-codex-gpt-5.6-terra"],
                    3,
                )

    def test_ssh_tmux_live_target_prompt_uses_alias_not_real_host(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            env_dir = repo_root / "server-instances" / "ssh-tmux"
            env_dir.mkdir(parents=True)
            (env_dir / ".env").write_text(
                "\n".join(
                    [
                        "CONTEXTFORGE_SSH_TMUX_TEST_HOST=10.0.0.42",
                        "CONTEXTFORGE_SSH_TMUX_TEST_ALIAS=contextforge-live-target",
                        "CONTEXTFORGE_SSH_TMUX_TEST_REMOTE_PROBE_COMMAND=printf should-not-leak",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            prompt = module.service_test_prompt(
                "ssh-tmux",
                "ssh-tmux",
                309,
                316,
                repo_root=repo_root,
            )

        self.assertIn("contextforge-live-target", prompt)
        self.assertIn("printf contextforge-ssh-tmux-ok", prompt)
        self.assertNotIn("should-not-leak", prompt)
        self.assertNotIn("10.0.0.42", prompt)

    def test_onboarding_model_backed_human_uses_terra_high(self) -> None:
        module = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-onboarding-semantic-process-dialogue.py",
            "onboarding_litellm_human_role_test",
        )
        config = module.responder_model_config(
            {
                "provider_kind": "litellm",
                "api_key_env": "LITELLM_API_KEY",
                "base_url_env": "LITELLM_BASE_URL",
            },
            {
                "LITELLM_API_KEY": "dummy-test-key",
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "CONTEXTFORGE_LITELLM_HOST_BASE_URL": "http://127.0.0.1:3333/v1",
                "CONTEXTFORGE_TERRA_MODEL": "codex/gpt-5.6-terra",
            },
            object(),
        )

        self.assertEqual("litellm", config["provider_kind"])
        self.assertEqual("codex/gpt-5.6-terra", config["model"])
        self.assertEqual("high", config["reasoning_effort"])
        self.assertEqual("http://127.0.0.1:3333/v1", config["base_url"])
        with self.assertRaisesRegex(RuntimeError, "host LiteLLM"):
            module.responder_model_config(
                {"provider_kind": "litellm"},
                {
                    "LITELLM_API_KEY": "dummy-test-key",
                    "CONTEXTFORGE_LITELLM_HOST_BASE_URL": "https://api.openai.com/v1",
                },
                object(),
            )

    def test_comprehensive_mcp_runner_supports_prompt_override_for_behavior_bundles(self) -> None:
        dialogue = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py").read_text(
            encoding="utf-8"
        )
        quorum = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-model-quorum.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("--service-test-prompt", dialogue)
        self.assertIn("args.service_test_prompt or service_test_prompt", dialogue)
        self.assertIn('"service_test_prompt_override_used": bool(args.service_test_prompt)', dialogue)
        self.assertIn("--service-test-prompt", quorum)
        self.assertIn('command.extend(["--service-test-prompt", args.service_test_prompt])', quorum)
        self.assertIn('"service_test_prompt_override_used": bool(args.service_test_prompt)', quorum)

    def test_comprehensive_mcp_quorum_uses_parallel_isolated_client_surfaces(self) -> None:
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        dialogue = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py").read_text(
            encoding="utf-8"
        )
        quorum = (ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-model-quorum.py").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "${CONTEXTFORGE_CLIENT_HARNESS_OPENCODE_HOME:-opencode-home}:/home/agent",
            "${CONTEXTFORGE_CLIENT_HARNESS_PI_HOME:-pi-home}:/home/agent",
            "${CONTEXTFORGE_CLIENT_HARNESS_WORKSPACE:-./workspace}:/workspace",
            "${CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED:-./client-scoped}:/run/contextforge-client-scoped:ro",
            "${CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES:-../../server-instances}:/repo/server-instances:ro",
        ]:
            self.assertIn(phrase, compose)
        for phrase in [
            "--isolation-root",
            "--run-suffix",
            "safe_run_suffix",
            "prepare_isolated_harness",
            "CONTEXTFORGE_CLIENT_HARNESS_WORKSPACE",
            "CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED",
            "CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES",
            "server_instances",
            "lock_file = None if isolated else uc1.acquire_harness_lock(harness_root)",
        ]:
            self.assertIn(phrase, dialogue)
        for phrase in [
            "--jobs",
            "ThreadPoolExecutor",
            "parallel_isolated",
            "--isolation-root",
            "--run-suffix",
            "prebuild",
        ]:
            self.assertIn(phrase, quorum)

    def test_sandbox_profile_selection_rejects_non_litellm_providers(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "comprehensive_mcp_service_dialogue",
            ROOT / "docker/client-harness/scripts/run-comprehensive-mcp-service-dialogue.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for provider_kind in ["openrouter", "openai_compatible", "", "litellm-direct"]:
            with self.subTest(provider_kind=provider_kind):
                with self.assertRaisesRegex(RuntimeError, "only litellm semantic profiles"):
                    module.selected_profile_env(
                        {
                            "id": "unsupported",
                            "provider_kind": provider_kind,
                            "provider_label": provider_kind,
                            "model": "unapproved/model",
                            "display_name": "Unsupported",
                            "context_window": 1048576,
                            "api_key_env": "OPENROUTER_API_KEY",
                            "base_url_env": "OPENROUTER_BASE_URL",
                        },
                        "pi",
                        {},
                    )

        canonical_profile = {
            "id": "canonical",
            "provider_kind": "litellm",
            "provider_label": "LiteLLM",
            "model": "codex/gpt-5.6-luna",
            "semantic_role": "blind",
            "display_name": "Luna",
            "context_window": 1048576,
            "reasoning_effort": "medium",
            "api_key_env": "LITELLM_API_KEY",
            "base_url_env": "LITELLM_BASE_URL",
            "default_base_url": "http://host.docker.internal:3333/v1",
            "pi_provider": "litellm",
            "pi_thinking": "medium",
            "opencode_model": "litellm/codex/gpt-5.6-luna",
            "opencode_variant": "medium",
        }
        profile_mutations = [
            ({"model": "codex/unapproved"}, "unsupported sandbox semantic model"),
            ({"semantic_role": "human"}, "semantic role mismatch"),
            ({"reasoning_effort": "high"}, "reasoning effort mismatch"),
            ({"api_key_env": "OPENAI_API_KEY"}, "must use LITELLM_API_KEY"),
            ({"base_url_env": "OPENAI_BASE_URL"}, "must use LITELLM_BASE_URL"),
            ({"default_base_url": "https://api.openai.com/v1"}, "sandbox LiteLLM endpoint"),
            ({"pi_provider": "openai"}, "Pi provider mismatch"),
            ({"pi_thinking": "high"}, "Pi thinking mismatch"),
            ({"opencode_model": "openai/gpt-5.6-luna"}, "OpenCode model mismatch"),
            ({"opencode_variant": "high"}, "OpenCode variant mismatch"),
        ]
        for mutation, expected_error in profile_mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(RuntimeError, expected_error):
                    module.selected_profile_env(
                        {**canonical_profile, **mutation},
                        "pi",
                        {"LITELLM_API_KEY": "present"},
                    )

    def test_comprehensive_mcp_semantic_tests_require_role_correct_luna_run_quorum(self) -> None:
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
            "at least three independent Luna/medium tested-assistant runs",
            "A one-run pass is useful slice evidence, not a test pass",
            "The quorum is about independent blind-agent runs over the same behavior",
            "--service-test-prompt",
            "isolated client harness roots",
        ]:
            self.assertIn(phrase, skill_line_wrapped)
        for phrase in [
            "`run_quorum`",
            "Single-run evidence is slice evidence only",
            "A test with one or two passing runs is `quorum_incomplete`, not passed",
            "The Luna run quorum does not permit deterministic prose scoring",
            "run-comprehensive-mcp-model-quorum.py",
            "does not score semantic pass/fail",
            "`--service-test-prompt`",
            "localized bundle coverage",
            "execution_mode: parallel_isolated",
            "fall back to `--jobs 1`",
        ]:
            self.assertIn(phrase, method_line_wrapped)
        for phrase in [
            "MIN_RUN_QUORUM = 3",
            "semantic_acceptance",
            "requires_sol_evaluator_per_run_and_quorum",
            "quorum_run_incomplete",
            "ready_for_sol_evaluator",
            "quorum runner does not score free-form assistant prose",
            "keeps Luna/medium fixed across runs",
        ]:
            self.assertIn(phrase, quorum_runner)

    def test_opencode_renderer_rejects_non_litellm_model_defaults(self) -> None:
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
                (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            env = {
                "CONTEXTFORGE_OPENCODE_CONFIG_SOURCE": str(source),
                "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(target),
                "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "openrouter/~google/gemini-2.5-flash-lite",
            }
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "unsupported OpenCode sandbox model"):
                    module.render_config()
            env.update(
                {
                    "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "litellm/codex/gpt-5.6-luna",
                    "LITELLM_BASE_URL": "https://api.openai.com/v1",
                }
            )
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "OpenCode sandbox LiteLLM endpoint"):
                    module.render_config()

    def test_pi_renderer_rejects_reasoning_map_and_default_thinking_drift(self) -> None:
        renderer = _load_script_module(
            ROOT / "docker/client-harness/pi/render-config.py",
            "contextforge_pi_render_config_test",
        )
        canonical_models = json.loads(
            (ROOT / "docker/client-harness/config/pi/models.json").read_text(encoding="utf-8")
        )
        canonical_settings = (ROOT / "docker/client-harness/config/pi/settings.json").read_text(
            encoding="utf-8"
        )
        mutations = [
            (lambda data: data["providers"]["litellm"]["models"][0].update({"reasoning": False}), "reasoning"),
            (
                lambda data: data["providers"]["litellm"]["models"][0]["thinkingLevelMap"].update(
                    {"high": "medium"}
                ),
                "thinking map",
            ),
            (
                lambda data: data["providers"]["litellm"]["models"][1]["thinkingLevelMap"].update(
                    {"unexpected": "high"}
                ),
                "thinking map",
            ),
        ]
        for mutate, expected_error in mutations:
            with self.subTest(expected_error=expected_error), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                models = json.loads(json.dumps(canonical_models))
                mutate(models)
                models_source = root / "models.json"
                settings_source = root / "settings.json"
                models_source.write_text(json.dumps(models), encoding="utf-8")
                settings_source.write_text(canonical_settings, encoding="utf-8")
                env = {
                    "CONTEXTFORGE_PI_MODELS_SOURCE": str(models_source),
                    "CONTEXTFORGE_PI_SETTINGS_SOURCE": str(settings_source),
                    "PI_CODING_AGENT_DIR": str(root / "target"),
                    "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
                    "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
                    "CONTEXTFORGE_PI_DEFAULT_THINKING": "medium",
                }
                with unittest.mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(ValueError, expected_error):
                        renderer.render_config()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            models_source = root / "models.json"
            settings_source = root / "settings.json"
            models_source.write_text(json.dumps(canonical_models), encoding="utf-8")
            settings_source.write_text(canonical_settings, encoding="utf-8")
            env = {
                "CONTEXTFORGE_PI_MODELS_SOURCE": str(models_source),
                "CONTEXTFORGE_PI_SETTINGS_SOURCE": str(settings_source),
                "PI_CODING_AGENT_DIR": str(root / "target"),
                "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
                "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
                "CONTEXTFORGE_PI_DEFAULT_THINKING": "high",
            }
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "thinking level"):
                    renderer.render_config()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            models_source = root / "models.json"
            settings_source = root / "settings.json"
            target = root / "target"
            models_source.write_text(json.dumps(canonical_models), encoding="utf-8")
            settings_source.write_text(canonical_settings, encoding="utf-8")
            env = {
                "CONTEXTFORGE_PI_MODELS_SOURCE": str(models_source),
                "CONTEXTFORGE_PI_SETTINGS_SOURCE": str(settings_source),
                "PI_CODING_AGENT_DIR": str(target),
                "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
                "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-terra",
                "CONTEXTFORGE_PI_DEFAULT_THINKING": "high",
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "LITELLM_API_KEY": "dummy-test-key",
            }
            with unittest.mock.patch.dict(os.environ, env, clear=True):
                renderer.render_config()
            rendered_models = json.loads((target / "models.json").read_text(encoding="utf-8"))
            rendered_settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual({"litellm"}, set(rendered_models["providers"]))
            self.assertEqual(
                "http://host.docker.internal:3333/v1",
                rendered_models["providers"]["litellm"]["baseUrl"],
            )
            self.assertEqual("dummy-test-key", rendered_models["providers"]["litellm"]["apiKey"])
            self.assertEqual("codex/gpt-5.6-terra", rendered_settings["defaultModel"])
            self.assertEqual("high", rendered_settings["defaultThinkingLevel"])
            with unittest.mock.patch.dict(
                os.environ,
                {**env, "LITELLM_BASE_URL": "https://api.openai.com/v1"},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "Pi sandbox LiteLLM endpoint"):
                    renderer.render_config()

    def test_opencode_renderer_rejects_reasoning_variant_drift(self) -> None:
        renderer = _load_script_module(
            ROOT / "docker/client-harness/opencode/render-config.py",
            "contextforge_opencode_reasoning_render_config_test",
        )
        canonical = json.loads(
            (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8")
        )
        mutations = [
            lambda data: data["provider"]["litellm"]["models"]["codex/gpt-5.6-terra"].update(
                {"reasoning": False}
            ),
            lambda data: data["provider"]["litellm"]["models"]["codex/gpt-5.6-terra"]["variants"][
                "high"
            ].update({"reasoningEffort": "medium"}),
            lambda data: data["provider"]["litellm"]["models"]["codex/gpt-5.6-luna"]["variants"][
                "medium"
            ].update({"unexpected": True}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_data = json.loads(json.dumps(canonical))
                mutate(source_data)
                source = root / "opencode.source.json"
                target = root / "opencode.json"
                source.write_text(json.dumps(source_data), encoding="utf-8")
                env = {
                    "CONTEXTFORGE_OPENCODE_CONFIG_SOURCE": str(source),
                    "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(target),
                }
                with unittest.mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(ValueError, "reasoning"):
                        renderer.render_config()

    def test_pi_renderer_rejects_extra_or_direct_configuration_surfaces(self) -> None:
        renderer = _load_script_module(
            ROOT / "docker/client-harness/pi/render-config.py",
            "contextforge_pi_strict_render_config_test",
        )
        canonical_models = json.loads(
            (ROOT / "docker/client-harness/config/pi/models.json").read_text(encoding="utf-8")
        )
        canonical_settings = json.loads(
            (ROOT / "docker/client-harness/config/pi/settings.json").read_text(encoding="utf-8")
        )
        mutations = [
            lambda models, settings: models.update({"directProvider": {"apiKey": "direct"}}),
            lambda models, settings: models["providers"]["litellm"].update({"headers": {"X-Key": "direct"}}),
            lambda models, settings: models["providers"]["litellm"].update({"apiKey": "direct-secret"}),
            lambda models, settings: models["providers"]["litellm"].update({"baseUrl": "https://api.openai.com/v1"}),
            lambda models, settings: models["providers"]["litellm"]["compat"].update({"unexpected": True}),
            lambda models, settings: models["providers"]["litellm"]["models"][0].update({"provider": "openai"}),
            lambda models, settings: settings.update({"provider": "openai"}),
            lambda models, settings: settings.update({"defaultProvider": "openai"}),
            lambda models, settings: settings["enabledModels"].append("openai/gpt-4o"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                models = json.loads(json.dumps(canonical_models))
                settings = json.loads(json.dumps(canonical_settings))
                mutate(models, settings)
                models_source = root / "models.json"
                settings_source = root / "settings.json"
                models_source.write_text(json.dumps(models), encoding="utf-8")
                settings_source.write_text(json.dumps(settings), encoding="utf-8")
                env = {
                    "CONTEXTFORGE_PI_MODELS_SOURCE": str(models_source),
                    "CONTEXTFORGE_PI_SETTINGS_SOURCE": str(settings_source),
                    "PI_CODING_AGENT_DIR": str(root / "target"),
                }
                with unittest.mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(ValueError, "canonical Pi"):
                        renderer.render_config()

    def test_opencode_renderer_rejects_extra_or_direct_configuration_surfaces(self) -> None:
        renderer = _load_script_module(
            ROOT / "docker/client-harness/opencode/render-config.py",
            "contextforge_opencode_strict_render_config_test",
        )
        canonical = json.loads(
            (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8")
        )
        mutations = [
            lambda data: data.update({"plugin": ["direct-provider-plugin"]}),
            lambda data: data["provider"].update({"openai": {"models": {"gpt-4o": {}}}}),
            lambda data: data.update({"enabled_providers": ["litellm", "openai"]}),
            lambda data: data["provider"]["litellm"]["options"].update({"headers": {"X-Key": "direct"}}),
            lambda data: data["provider"]["litellm"]["options"].update({"apiKey": "direct-secret"}),
            lambda data: data["provider"]["litellm"]["options"].update({"baseURL": "https://api.openai.com/v1"}),
            lambda data: data["provider"]["litellm"]["whitelist"].append("gpt-4o"),
            lambda data: data["provider"]["litellm"]["models"]["codex/gpt-5.6-luna"].update(
                {"provider": "openai"}
            ),
            lambda data: data["agent"].update(
                {"direct": {"model": "openai/gpt-4o", "variant": "high"}}
            ),
            lambda data: data["agent"]["build"].update({"fallback_model": "openai/gpt-4o"}),
            lambda data: data["mcp"]["contextforge-helper"]["environment"].update(
                {"OPENAI_API_KEY": "direct-secret"}
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_data = json.loads(json.dumps(canonical))
                mutate(source_data)
                source = root / "opencode.source.json"
                target = root / "opencode.json"
                source.write_text(json.dumps(source_data), encoding="utf-8")
                env = {
                    "CONTEXTFORGE_OPENCODE_CONFIG_SOURCE": str(source),
                    "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(target),
                }
                with unittest.mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(ValueError, "canonical OpenCode"):
                        renderer.render_config()

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
            self.assertIn(
                "- ${CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES:-../../server-instances}:/repo/server-instances:ro",
                match.group(0),
            )
            self.assertIn(
                "- ${CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED:-./client-scoped}:/run/contextforge-client-scoped:ro",
                match.group(0),
            )
            self.assertIn("- ${CONTEXTFORGE_CLIENT_HARNESS_WORKSPACE:-./workspace}:/workspace", match.group(0))
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
            if service in {"opencode", "pi"}:
                self.assertIn(
                    "- ${CONTEXTFORGE_CLIENT_HARNESS_CLIENT_SCOPED:-./client-scoped}:/run/contextforge-client-scoped:ro",
                    service_block,
                )
            else:
                self.assertIn("- ./client-scoped:/run/contextforge-client-scoped:ro", service_block)
            if service in {"opencode", "pi"}:
                self.assertIn(
                    "- ${CONTEXTFORGE_CLIENT_HARNESS_SERVER_INSTANCES:-../../server-instances}:/repo/server-instances:ro",
                    service_block,
                )
            else:
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

        self.assertIn('exec /usr/local/bin/pi "$@"', container_launcher)
        self.assertIn(". /usr/local/bin/contextforge-pi-bootstrap", wrapper)
        self.assertIn("CONTEXTFORGE_PI_SHIM_INSTALL_DIR:=${PI_CODING_AGENT_DIR}/extensions/contextforge-global-shim", combined)
        self.assertIn("Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR", combined)
        self.assertIn("rm -rf \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", combined)
        self.assertIn("cp -R \"$(dirname \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\")\" \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", combined)
        self.assertIn("contextforge-root.json", combined)
        self.assertNotIn("--extension \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\"", combined)
        self.assertIn('--provider "${CONTEXTFORGE_PI_DEFAULT_PROVIDER}"', wrapper)
        self.assertIn('--model "${CONTEXTFORGE_PI_DEFAULT_MODEL}"', wrapper)
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
        self.assertIn("docker compose -f compose.yml --env-file env/semantic-model.env run --rm --no-deps", host_launcher)
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
        self.assertIn("docker compose -f compose.yml --env-file env/semantic-model.env run --rm --no-deps", host_launcher)
        self.assertIn("-v \"${REPO_ROOT}:/repo:ro\"", host_launcher)
        self.assertIn("ENTRYPOINT [\"/usr/local/bin/contextforge-opencode-entrypoint\"]", dockerfile)
        self.assertIn("OPENCODE_CONFIG_DIR:=/home/agent/.config/opencode", entrypoint)
        self.assertIn("OPENCODE_DISABLE_PROJECT_CONFIG:=1", entrypoint)
        self.assertIn("export OPENCODE_DISABLE_PROJECT_CONFIG", entrypoint)
        self.assertIn("rejects OPENCODE_CONFIG_CONTENT", entrypoint)
        self.assertIn('export OPENCODE_CONFIG="${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}"', entrypoint)
        self.assertIn("OpenCode sandbox rejects direct-provider credential", entrypoint)
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
        self.assertGreaterEqual(compose.count('OPENCODE_DISABLE_PROJECT_CONFIG: "1"'), 2)
        self.assertGreaterEqual(compose.count('OPENCODE_CONFIG_CONTENT: ""'), 2)
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
        self.assertIn("const sameRecordedSession = previousSessionID && previousSessionID === String(sessionID)", plugin)
        self.assertIn("transcriptShowsProjectInitContinuation", plugin)
        self.assertIn("sameRecordedSession || transcriptShowsProjectInitContinuation(output.messages)", plugin)
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
        for model in ["codex/gpt-5.6-terra", "codex/gpt-5.6-luna", "codex/gpt-5.6-sol"]:
            self.assertIn(model, probe)
        self.assertIn("--expected-model-id \"${model}\"", probe)
        self.assertIn("pi --list-models litellm", probe)
        self.assertIn("opencode models litellm", probe)
        self.assertEqual(2, probe.count("--env-file env/semantic-model.env"))
        self.assertIn("--fail-on-stale", probe)
        self.assertIn("evidence/pi-semantic-model-identity.json", probe)
        self.assertIn("evidence/opencode-semantic-model-identity.json", probe)
        self.assertIn('exec "${ROOT}/scripts/probe-semantic-model.sh" "$@"', legacy_probe)
        self.assertIn("scripts/probe-semantic-model.sh", readme)
        self.assertIn("legacy `scripts/probe-llama.sh` name remains only as a compatibility", readme)
        self.assertIn("exact advertised model identity reports", readme)
        self.assertIn("`current`", readme)
        self.assertIn("`stale`", readme)
        self.assertIn("`unverified`", readme)

    def test_semantic_model_env_and_six_cell_smoke_are_litellm_only(self) -> None:
        generator = (ROOT / "docker/client-harness/scripts/make-semantic-model-env.sh").read_text(encoding="utf-8")
        smoke = (ROOT / "docker/client-harness/scripts/smoke-agents.sh").read_text(encoding="utf-8")

        self.assertIn('${HOME}/.config/litellm/client.env', generator)
        self.assertIn("LITELLM_API_KEY", generator)
        self.assertIn("http://host.docker.internal:3333/v1", generator)
        self.assertIn("CONTEXTFORGE_LITELLM_HOST_BASE_URL", generator)
        self.assertIn("http://127.0.0.1:3333/v1", generator)
        self.assertNotIn("OPENROUTER_", generator)
        self.assertNotIn("LOCAL_LLAMA", generator)
        self.assertEqual(3, smoke.count("run_pi_cell "))
        self.assertEqual(3, smoke.count("run_opencode_cell "))
        self.assertIn('--thinking "${thinking}"', smoke)
        self.assertIn('CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT="${variant}"', smoke)
        self.assertEqual(2, smoke.count('require_exact_response "${marker}" "${output_file}"'))
        self.assertNotIn('grep -Fxq "${marker}"', smoke)
        self.assertIn("--env-file env/semantic-model.env", smoke)

    def test_six_cell_smoke_rejects_multiline_marker_output(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-agents.sh").read_text(encoding="utf-8")

        def run_smoke(mode: str) -> subprocess.CompletedProcess[str]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                scripts = root / "scripts"
                fake_bin = root / "bin"
                scripts.mkdir()
                fake_bin.mkdir()
                smoke = scripts / "smoke-agents.sh"
                smoke.write_text(source, encoding="utf-8")
                smoke.chmod(0o755)
                generator = scripts / "make-semantic-model-env.sh"
                generator.write_text(
                    '#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p "$(dirname "$0")/../env"\n: > "$(dirname "$0")/../env/semantic-model.env"\n',
                    encoding="utf-8",
                )
                generator.chmod(0o755)
                docker = fake_bin / "docker"
                docker.write_text(
                    "#!/usr/bin/env bash\n"
                    "set -euo pipefail\n"
                    'prompt="${!#}"\n'
                    'marker="${prompt##*: }"\n'
                    'if [[ "${FAKE_DOCKER_MODE:-exact}" == noisy ]]; then\n'
                    '  printf "prefix\\n%s\\nsuffix\\n" "${marker}"\n'
                    'elif [[ "${FAKE_DOCKER_MODE:-exact}" == trailing-blank ]]; then\n'
                    '  printf "%s\\n\\n" "${marker}"\n'
                    "else\n"
                    '  printf "%s\\n" "${marker}"\n'
                    "fi\n",
                    encoding="utf-8",
                )
                docker.chmod(0o755)
                env = {
                    **os.environ,
                    "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
                    "FAKE_DOCKER_MODE": mode,
                }
                return subprocess.run(
                    [str(smoke)],
                    cwd=root,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

        self.assertEqual(0, run_smoke("exact").returncode)
        self.assertNotEqual(0, run_smoke("noisy").returncode)
        self.assertNotEqual(0, run_smoke("trailing-blank").returncode)

    def test_legacy_sandbox_smokes_use_litellm_config_without_removed_provider(self) -> None:
        for script_name in [
            "smoke-pi-contextforge-dev.sh",
            "smoke-pi-context7-dev.sh",
            "smoke-pi-alpine.sh",
            "smoke-opencode-alpine.sh",
        ]:
            with self.subTest(script_name=script_name):
                source = (ROOT / "docker/client-harness/scripts" / script_name).read_text(encoding="utf-8")
                self.assertNotIn("openrouter-semantic-test", source)
                self.assertNotIn('data["providers"]', source)
                self.assertNotIn("OPENROUTER_API_KEY", source)
                self.assertIn("--env-file env/semantic-model.env", source)

        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^  opencode-alpine:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
        self.assertIsNotNone(match)
        opencode_alpine = match.group(0)
        self.assertIn('LITELLM_API_KEY: "${LITELLM_API_KEY:-}"', opencode_alpine)
        self.assertIn('LITELLM_BASE_URL: "${LITELLM_BASE_URL:-http://host.docker.internal:3333/v1}"', opencode_alpine)
        self.assertIn(
            'CONTEXTFORGE_OPENCODE_DEFAULT_MODEL: "${CONTEXTFORGE_OPENCODE_DEFAULT_MODEL:-litellm/codex/gpt-5.6-luna}"',
            opencode_alpine,
        )

    def test_known_service_state_story_uses_luna_without_command_line_secret(self) -> None:
        module = _load_script_module(
            ROOT / "docker/client-harness/scripts/run-known-service-management-state-story.py",
            "known_service_state_story_litellm_test",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_dir = root / "env"
            env_dir.mkdir()
            env_file = env_dir / "semantic-model.env"
            values = {
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "LITELLM_API_KEY": "dummy-test-key",
                "CONTEXTFORGE_PI_DEFAULT_PROVIDER": "litellm",
                "CONTEXTFORGE_PI_DEFAULT_MODEL": "codex/gpt-5.6-luna",
                "CONTEXTFORGE_PI_DEFAULT_THINKING": "medium",
                "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "litellm/codex/gpt-5.6-luna",
                "CONTEXTFORGE_OPENCODE_SMALL_MODEL": "litellm/codex/gpt-5.6-luna",
                "CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT": "medium",
            }
            env_file.write_text(
                "".join(f"{key}={value}\n" for key, value in values.items()),
                encoding="utf-8",
            )
            launch_env, summary, selected_env_file = module.luna_launch_env(root)
            self.assertNotIn("LITELLM_API_KEY", launch_env)
            self.assertEqual("litellm", launch_env["CONTEXTFORGE_PI_DEFAULT_PROVIDER"])
            self.assertEqual("codex/gpt-5.6-luna", launch_env["CONTEXTFORGE_PI_DEFAULT_MODEL"])
            self.assertEqual("medium", launch_env["CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT"])
            self.assertEqual("blind", summary["semantic_role"])
            self.assertEqual(env_file, selected_env_file)

            env_file.write_text(
                "".join(
                    f"{key}={'high' if key == 'CONTEXTFORGE_PI_DEFAULT_THINKING' else value}\n"
                    for key, value in values.items()
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "Luna/medium sandbox contract"):
                module.luna_launch_env(root)

    def test_opencode_alpine_entrypoint_rejects_direct_or_misrouted_models(self) -> None:
        source = (ROOT / "docker/client-harness/opencode-alpine/entrypoint.sh").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/client-harness/opencode-alpine/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("contextforge-opencode-alpine-entrypoint", dockerfile)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entrypoint = root / "entrypoint.sh"
            entrypoint.write_text(
                source.replace('exec /sbin/tini -- "$@"', "printf 'validated\\n'"),
                encoding="utf-8",
            )
            config = root / "opencode.json"
            canonical = (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(
                encoding="utf-8"
            )
            config.write_text(canonical, encoding="utf-8")
            env = {
                **os.environ,
                "OPENCODE_CONFIG": str(config),
                "CONTEXTFORGE_OPENCODE_CONFIG_TARGET": str(root / "rendered-opencode.json"),
                "CONTEXTFORGE_OPENCODE_RENDERER": str(
                    ROOT / "docker/client-harness/opencode/render-config.py"
                ),
                "LITELLM_BASE_URL": "http://host.docker.internal:3333/v1",
                "LITELLM_API_KEY": "dummy-test-key",
                "CONTEXTFORGE_OPENCODE_DEFAULT_MODEL": "litellm/codex/gpt-5.6-luna",
                "CONTEXTFORGE_OPENCODE_SMALL_MODEL": "litellm/codex/gpt-5.6-luna",
                "CONTEXTFORGE_OPENCODE_DEFAULT_VARIANT": "medium",
                "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
                "OPENAI_API_KEY": "",
                "CODEX_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "OPENROUTER_API_KEY": "",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "",
                "PERPLEXITY_API_KEY": "",
                "EXA_API_KEY": "",
                "CONTEXT7_API_KEY": "",
            }
            accepted = subprocess.run(
                ["bash", str(entrypoint)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            misrouted = subprocess.run(
                ["bash", str(entrypoint)],
                env={**env, "LITELLM_BASE_URL": "https://api.openai.com/v1"},
                text=True,
                capture_output=True,
                check=False,
            )
            direct_key = subprocess.run(
                ["bash", str(entrypoint)],
                env={**env, "OPENAI_API_KEY": "direct-key"},
                text=True,
                capture_output=True,
                check=False,
            )
            malformed = json.loads(canonical)
            malformed["agent"]["direct"] = {"model": "openai/gpt-4o", "variant": "high"}
            config.write_text(json.dumps(malformed), encoding="utf-8")
            direct_agent = subprocess.run(
                ["bash", str(entrypoint)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual("validated", accepted.stdout.strip())
        self.assertEqual(2, misrouted.returncode)
        self.assertIn("sandbox LiteLLM", misrouted.stderr)
        self.assertEqual(2, direct_key.returncode)
        self.assertIn("direct-provider credential", direct_key.stderr)
        self.assertNotEqual(0, direct_agent.returncode)

    def test_opencode_entrypoints_reject_runtime_config_content_override(self) -> None:
        injected = json.dumps(
            {
                "model": "openai/gpt-4o",
                "enabled_providers": ["openai"],
                "provider": {"openai": {"options": {"apiKey": "direct-secret"}}},
                "agent": {"rogue": {"model": "openai/gpt-4o"}},
            }
        )
        for entrypoint_path in [
            ROOT / "docker/client-harness/opencode/entrypoint.sh",
            ROOT / "docker/client-harness/opencode-alpine/entrypoint.sh",
        ]:
            with self.subTest(entrypoint=entrypoint_path.parent.name):
                result = subprocess.run(
                    ["bash", str(entrypoint_path)],
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "OPENCODE_CONFIG_CONTENT": injected,
                    },
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn("rejects OPENCODE_CONFIG_CONTENT", result.stderr)

    def test_comprehensive_mcp_semantic_skill_keeps_fixed_litellm_roles(self) -> None:
        skill = (ROOT / ".codex/skills/comprehensive-mcp-testing/SKILL.md").read_text(encoding="utf-8")
        method = (ROOT / ".codex/skills/comprehensive-mcp-testing/references/method.md").read_text(
            encoding="utf-8"
        )
        skill_line_wrapped = " ".join(skill.split())
        method_line_wrapped = " ".join(method.split())

        self.assertIn("All tested-assistant semantic runs use Luna/medium through LiteLLM", skill_line_wrapped)
        self.assertIn("Terra/high is reserved for simulated humans", skill_line_wrapped)
        self.assertIn("Sol/high is reserved for semantic evaluation", skill_line_wrapped)
        self.assertIn("Do not select local, direct-provider, Terra, or Sol profiles for the tested assistant", method_line_wrapped)
        self.assertNotIn("OpenRouter", skill + method)
        self.assertNotIn("llama.cpp", skill + method)

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
