from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContextForgeDockerHarnessTests(unittest.TestCase):
    def test_compose_defines_dev_mentality_transceiver_sidecar(self) -> None:
        compose = (ROOT / "docker/contextforge-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("mentality-transceiver:", compose)
        self.assertIn("contextforge-harness-mentality-transceiver:latest", compose)
        self.assertIn('"127.0.0.1:9201:9201"', compose)
        self.assertIn("docker/contextforge-harness/mcp-transceiver/Dockerfile", compose)

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
        self.assertIn('print(f\"probe_token_id={probe_token_id}\")', source)
        self.assertNotIn("print(probe_token", source)
        self.assertNotIn("print(access_token", source)

    def test_dockerignore_excludes_local_state_from_root_context(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        for pattern in [
            ".venv/",
            "docker/client-harness/env/local-llama.env",
            "docker/contextforge-harness/env/contextforge.env",
            "docker/contextforge-harness/evidence/",
            "config/contextforge.env",
            "run/",
            "upstream/",
        ]:
            self.assertIn(pattern, dockerignore)

    def test_dev_harness_env_allows_compose_network_upstreams(self) -> None:
        env_example = (ROOT / "docker/contextforge-harness/env/contextforge.env.example").read_text(encoding="utf-8")

        self.assertIn("SSRF_ALLOW_PRIVATE_NETWORKS=true", env_example)
        self.assertIn("REQUIRE_USER_IN_DB=false", env_example)

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
        self.assertIn("[REDACTED_CONTEXTFORGE_DEV_BEARER_TOKEN]", source)
        self.assertIn("chown -R", source)
        self.assertIn("revoke_probe_token", source)
        self.assertIn("CONTEXTFORGE_DEV_BEARER_TOKEN", source)
        self.assertNotIn("127.0.0.1:4444", source)
        self.assertNotIn("/home/dgk/.pi", source)

    def test_pi_image_provisions_container_local_contextforge_wrapper_runtime(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/pi/Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("python3-venv", dockerfile)
        self.assertIn("/opt/contextforge-wrapper-venv", dockerfile)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON", dockerfile)
        self.assertIn("/opt/contextforge-wrapper-venv/bin/python", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)

    def test_opencode_image_provisions_container_local_contextforge_helper_runtime(self) -> None:
        dockerfile = (ROOT / "docker/client-harness/opencode/Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("python3-venv", dockerfile)
        self.assertIn("/opt/contextforge-helper-venv", dockerfile)
        self.assertIn("mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}", dockerfile)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON=/opt/contextforge-helper-venv/bin/python", dockerfile)
        self.assertIn('MCP_CONTEXTFORGE_GATEWAY_VERSION: "${MCP_CONTEXTFORGE_GATEWAY_VERSION:-1.0.3}"', compose)
        self.assertIn("CONTEXTFORGE_HELPER_SCRIPT: /repo/scripts/contextforge_helper_mcp.py", compose)

    def test_pi_dev_smoke_uses_shim_against_dev_gateway(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-pi-contextforge-dev.sh").read_text(encoding="utf-8")

        self.assertIn("surface=Pi client Docker", source)
        self.assertIn("contextforge_surface=ContextForge dev Docker", source)
        self.assertIn("CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445", source)
        self.assertIn("CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445", source)
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server", source)
        self.assertIn("cf_contextforge_pi_validate", source)
        self.assertIn("pi-extensions/contextforge-global-shim/index.ts", source)
        self.assertIn("CONTEXTFORGE_SERVER_ID", source)
        self.assertIn("CONTEXTFORGE_BEARER_TOKEN", source)
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
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-context7_local_server", source)
        self.assertIn("register_context7_dev", source)
        self.assertIn("probe-context7-dev.py", source)
        self.assertIn("context7:canonical", source)
        self.assertIn("safe_probe_service=context7", source)
        self.assertIn("safe_probe_id=resolve-library-id", source)
        self.assertIn("cf_contextforge_pi_validate", source)
        self.assertIn("CONTEXTFORGE_SERVER_ID", source)
        self.assertIn("CONTEXTFORGE_BEARER_TOKEN", source)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python", source)
        self.assertIn("CONTEXTFORGE_CONFIG_ENV=/tmp/missing-contextforge.env", source)
        self.assertIn("revoke_probe_token", source)
        self.assertIn("probe_token_revoked", source)
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
        self.assertIn("local llama.cpp Qwen model path", contract)
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
        self.assertIn("OPENCODE_CONFIG: /home/agent/.config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_SOURCE: /config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_TARGET: /home/agent/.config/opencode/opencode.json", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET: /home/agent/.config/opencode/plugins/contextforge-project-init.js", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK: /repo/scripts/opencode_project_init_hook.py", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_RUN_ROOT: /tmp/contextforge-client-harness-runtime/project-init", compose)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON: /opt/contextforge-helper-venv/bin/python", compose)
        self.assertIn("CONTEXTFORGE_HELPER_SCRIPT: /repo/scripts/contextforge_helper_mcp.py", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_EXTENSION: /repo/pi-extensions/contextforge-global-shim/index.ts", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_INSTALL_DIR: /home/agent/.pi/agent/extensions/contextforge-global-shim", compose)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WRAPPER: /repo/scripts/contextforge_mcp_wrapper.py", compose)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS: /workspace", compose)

        for service in ("opencode", "pi"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertIn("- ../..:/repo:ro", match.group(0))
            self.assertIn("- ./workspace:/workspace", match.group(0))

        for service in ("opencode-ephemeral", "pi-ephemeral"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertIn("- ../..:/repo:ro", match.group(0))
            self.assertIn("tmpfs:", match.group(0))
            self.assertIn("- /workspace:uid=1000,gid=1000,mode=0755", match.group(0))
            self.assertNotIn("- ./workspace:/workspace", match.group(0))

        for service in ("codex-cli", "claude-code", "gemini-cli"):
            match = re.search(rf"(?ms)^  {service}:\n.*?(?=^  [a-z0-9-]+:|\nvolumes:)", compose)
            self.assertIsNotNone(match, service)
            self.assertNotIn("- ../..:/repo:ro", match.group(0))

    def test_pi_baseline_launcher_loads_shim_without_host_global_mutation(self) -> None:
        container_launcher = (ROOT / "docker/client-harness/config/pi/start-contextforge-baseline.sh").read_text(encoding="utf-8")
        host_launcher = (ROOT / "docker/client-harness/scripts/start-pi-contextforge-baseline.sh").read_text(encoding="utf-8")

        self.assertIn("CONTEXTFORGE_PI_SHIM_INSTALL_DIR:=${PI_CODING_AGENT_DIR}/extensions/contextforge-global-shim", container_launcher)
        self.assertIn("Refusing unsafe CONTEXTFORGE_PI_SHIM_INSTALL_DIR", container_launcher)
        self.assertIn("rm -rf \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", container_launcher)
        self.assertIn("cp -R \"$(dirname \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\")\" \"${CONTEXTFORGE_PI_SHIM_INSTALL_DIR}\"", container_launcher)
        self.assertIn("contextforge-root.json", container_launcher)
        self.assertNotIn("--extension \"${CONTEXTFORGE_PI_SHIM_EXTENSION}\"", container_launcher)
        self.assertIn("--provider local-llama-qwen", container_launcher)
        self.assertIn("--model qwen3.6-a3b", container_launcher)
        self.assertIn("CONTEXTFORGE_PI_SHIM_PYTHON:=/opt/contextforge-wrapper-venv/bin/python", container_launcher)
        self.assertIn("CONTEXTFORGE_PI_SHIM_WRAPPER:=/repo/scripts/contextforge_mcp_wrapper.py", container_launcher)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace", container_launcher)
        self.assertIn("docker compose -f compose.yml run --rm --no-deps", host_launcher)
        self.assertIn("-v \"${REPO_ROOT}:/repo:ro\"", host_launcher)
        self.assertNotIn("/home/dgk/.pi", container_launcher + host_launcher)

    def test_opencode_baseline_launcher_installs_user_home_plugin_fixture(self) -> None:
        container_launcher = (ROOT / "docker/client-harness/config/opencode/start-contextforge-baseline.sh").read_text(encoding="utf-8")
        host_launcher = (ROOT / "docker/client-harness/scripts/start-opencode-contextforge-baseline.sh").read_text(encoding="utf-8")
        plugin = (ROOT / "docker/client-harness/config/opencode/plugins/contextforge-project-init.js").read_text(encoding="utf-8")
        entrypoint = (ROOT / "docker/client-harness/opencode/entrypoint.sh").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker/client-harness/opencode/Dockerfile").read_text(encoding="utf-8")
        opencode_config = (ROOT / "docker/client-harness/config/opencode/opencode.json").read_text(encoding="utf-8")
        compose = (ROOT / "docker/client-harness/compose.yml").read_text(encoding="utf-8")

        self.assertIn("OPENCODE_CONFIG:=/home/agent/.config/opencode/opencode.json", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE:=/config/opencode/plugins/contextforge-project-init.js", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=/home/agent/.config/opencode/plugins/contextforge-project-init.js", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK_PYTHON:=${CONTEXTFORGE_HELPER_PYTHON:-/opt/contextforge-helper-venv/bin/python}", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/config/contextforge/contextforge.env", container_launcher)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445", container_launcher)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/tmp/contextforge-client-harness-runtime/project-init", container_launcher)
        self.assertIn("exec opencode \"$@\"", container_launcher)
        self.assertIn("docker compose -f compose.yml run --rm --no-deps", host_launcher)
        self.assertIn("-v \"${REPO_ROOT}:/repo:ro\"", host_launcher)
        self.assertIn("ENTRYPOINT [\"/usr/local/bin/contextforge-opencode-entrypoint\"]", dockerfile)
        self.assertIn("OPENCODE_CONFIG_DIR:=/home/agent/.config/opencode", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_CONFIG_TARGET:=${OPENCODE_CONFIG_DIR}/opencode.json", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_PLUGIN_TARGET:=${OPENCODE_CONFIG_DIR}/plugins/contextforge-project-init.js", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON:=/opt/contextforge-helper-venv/bin/python", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT:=/repo/scripts/contextforge_mcp_wrapper.py", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV:=/config/contextforge/contextforge.env", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL:=http://host.docker.internal:4445", entrypoint)
        self.assertIn("CONTEXTFORGE_PROJECT_INIT_RUN_ROOT:=/tmp/contextforge-client-harness-runtime/project-init", entrypoint)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_CONFIG_ENV: /config/contextforge/contextforge.env", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_BASE_URL: http://host.docker.internal:4445", compose)
        self.assertIn("CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE: /tmp/contextforge-wrapper-token.local.json", compose)
        self.assertIn("../contextforge-harness/env:/config/contextforge:ro", compose)
        self.assertIn("cp \"${CONTEXTFORGE_OPENCODE_CONFIG_SOURCE}\" \"${CONTEXTFORGE_OPENCODE_CONFIG_TARGET}\"", entrypoint)
        self.assertIn("cp \"${CONTEXTFORGE_OPENCODE_PLUGIN_SOURCE}\" \"${CONTEXTFORGE_OPENCODE_PLUGIN_TARGET}\"", entrypoint)
        self.assertIn('const HOOK_EVENT = "chat.message"', plugin)
        self.assertNotIn("experimental.chat.system.transform", plugin)
        self.assertIn("spawnSync", plugin)
        self.assertIn("CONTEXTFORGE_HELPER_PYTHON", plugin)
        self.assertIn("CONTEXTFORGE_OPENCODE_HOOK", plugin)
        self.assertIn("opencode_project_init_hook.py", plugin)
        self.assertIn("hookSpecificOutput", plugin)
        self.assertIn("additionalContext", plugin)
        self.assertIn("output.parts.unshift", plugin)
        self.assertIn("CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS:=/workspace", container_launcher)
        self.assertIn('"contextforge-helper"', opencode_config)
        self.assertIn('"{env:CONTEXTFORGE_HELPER_PYTHON}"', opencode_config)
        self.assertIn('"{env:CONTEXTFORGE_HELPER_SCRIPT}"', opencode_config)
        self.assertIn("contextforge-client-harness-runtime", opencode_config)
        self.assertNotIn("/workspace/.opencode/plugins", container_launcher + entrypoint + plugin)
        self.assertNotIn("/repo/run", container_launcher + entrypoint + plugin)
        self.assertNotIn("/home/dgk/.config/opencode", container_launcher + host_launcher + plugin + entrypoint)
        self.assertNotIn("opencode mcp add", container_launcher + host_launcher + plugin)
        self.assertNotIn("opencode mcp list", container_launcher + host_launcher + plugin)

    def test_client_helper_baseline_contract_requires_future_runtime_evidence(self) -> None:
        contract = (ROOT / "docker/client-harness/CONTEXTFORGE_HELPER_BASELINE.md").read_text(encoding="utf-8")
        readme = (ROOT / "docker/client-harness/README.md").read_text(encoding="utf-8")

        self.assertIn("separately approved validation", contract)
        self.assertIn("Pi ad hoc session lists or can invoke", contract)
        self.assertIn("OpenCode ad hoc session receives project-init helper/hook context", contract)
        self.assertIn("Both clients continue using the local llama.cpp Qwen model path", contract)
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
        self.assertIn("local-Qwen validation sample", readme)
        self.assertIn("thin consumers", readme)
        self.assertIn("less-mediated model behavior", readme)
        self.assertIn("multi-session persistence in `/workspace`", readme)
        self.assertIn("should not leave duplicate, stale, or orphaned", readme)
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


if __name__ == "__main__":
    unittest.main()
