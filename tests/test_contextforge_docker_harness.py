from __future__ import annotations

import ast
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

    def test_opencode_dev_smoke_uses_ephemeral_contextforge_token(self) -> None:
        source = (ROOT / "docker/client-harness/scripts/smoke-opencode-contextforge-dev.sh").read_text(encoding="utf-8")

        self.assertIn("surface=OpenCode client Docker", source)
        self.assertIn("contextforge_surface=ContextForge dev Docker", source)
        self.assertIn("CONTEXTFORGE_HOST_BASE_URL:-http://127.0.0.1:4445", source)
        self.assertIn("CONTEXTFORGE_CONTAINER_BASE_URL:-http://host.docker.internal:4445", source)
        self.assertIn("CONTEXTFORGE_DEV_SERVER_NAME:-mentality_dev_docker_server", source)
        self.assertIn("opencode mcp add", source)
        self.assertIn("opencode mcp list", source)
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


if __name__ == "__main__":
    unittest.main()
