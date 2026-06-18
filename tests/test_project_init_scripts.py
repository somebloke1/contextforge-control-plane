from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manage_serena_project_instance as serena_manager
import codex_project_init_hook as init_hook
import gemini_project_init_hook
import opencode_project_init_hook
import pi_project_init_helper_cli
import control_plane_contextforge_binding as binding
import control_plane_project_state as project_state
import control_plane_registry_discipline as registry_discipline
import inspect_codex_runtime_readback as codex_runtime_readback
import inspect_project_init_readiness as readiness
import plan_codex_global_config_migration as codex_global_plan
import plan_dirty_checkout_rebind as dirty_rebind
import project_init_common as common
import register_project_init_prompt as prompt_registration
import register_serena_cf_controlplane_service as serena_registration
import register_github_service as github_registration
import register_web_search_service as web_search_registration


CONSENT_REFS = ["run/consent-receipts/receipt-project-local-config.json"]


def write_fake_python(root: Path) -> Path:
    python_path = root / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    python_path.chmod(0o755)
    return python_path


def service_descriptor(name: str = "context7") -> dict[str, object]:
    return {
        "service_family": name,
        "canonical_service": name,
        "service_binding": f"{name}:canonical",
        "codex_alias": common.normalize_codex_alias(name),
        "instantiation_class": "shared_canonical",
        "backend_instance": f"server-instances/{name}",
        "virtual_server": f"{common.normalize_codex_alias(name)}_server",
        "contextforge_readback_status": "matched",
        "gateway": f"{name}-gateway",
        "validation_policy": common.safe_validation_policy(name),
        "non_actions": ["do not create a per-project backend"],
    }


class RegistryMutationGuardCoverageTests(unittest.TestCase):
    def test_registration_api_wrappers_reject_unsupported_paths_before_gateway(self) -> None:
        cases = [
            (
                prompt_registration,
                lambda: prompt_registration.api_request("PATCH", "/gateways/gateway-1", "token"),
            ),
            (
                serena_registration,
                lambda: serena_registration.api_request("PATCH", "/gateways/gateway-1", token="token"),
            ),
            (
                github_registration,
                lambda: github_registration.api_request("PATCH", "/gateways/gateway-1", token="token"),
            ),
            (
                web_search_registration,
                lambda: web_search_registration.api_request("PATCH", "/gateways/gateway-1", token="token"),
            ),
            (
                serena_manager,
                lambda: serena_manager.api_request("PATCH", "/gateways/gateway-1", "token"),
            ),
        ]

        for module, call in cases:
            with self.subTest(module=module.__name__):
                with mock.patch.object(module.gateway, "_request", side_effect=AssertionError("unguarded gateway call")):
                    with self.assertRaises(registry_discipline.RegistryMutationDisciplineError):
                        call()

    def test_newly_guarded_registry_scripts_call_gateway_only_through_api_wrapper(self) -> None:
        for path in [
            REPO_ROOT / "scripts" / "register_project_init_prompt.py",
            REPO_ROOT / "scripts" / "register_serena_cf_controlplane_service.py",
            REPO_ROOT / "scripts" / "register_github_service.py",
            REPO_ROOT / "scripts" / "register_web_search_service.py",
            REPO_ROOT / "scripts" / "manage_serena_project_instance.py",
        ]:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("registry_discipline.assert_public_contextforge_api_path", source)
                self.assertEqual(1, source.count("gateway._request("))


class ProjectInitCommonTests(unittest.TestCase):
    def test_denied_roots_are_rejected(self) -> None:
        for root in ("/", str(Path.home()), "/home/dgk/workspace"):
            with self.subTest(root=root):
                with self.assertRaises(ValueError):
                    common.validate_project_root(root, require_workspace=True)

    def test_cmu_math_foundations_root_is_safe(self) -> None:
        root = common.CMU_MATH_FOUNDATIONS_ROOT
        self.assertTrue(common.safe_workspace_project_root(root))
        self.assertEqual(root, common.validate_project_root(root, require_workspace=True))
        self.assertEqual(root / "dev", common.validate_project_root(root / "dev", require_workspace=True))

    def test_additional_safe_project_roots_are_explicit_env_only(self) -> None:
        root = Path("/workspace")
        with self.assertRaises(ValueError):
            common.validate_project_root(root, require_workspace=True)
        with mock.patch.dict(common.os.environ, {common.ADDITIONAL_SAFE_ROOTS_ENV: str(root)}):
            self.assertTrue(common.safe_workspace_project_root(root))
            self.assertEqual(root, common.validate_project_root(root, require_workspace=True))

    def test_additional_safe_project_roots_do_not_override_denied_roots(self) -> None:
        with mock.patch.dict(common.os.environ, {common.ADDITIONAL_SAFE_ROOTS_ENV: str(Path.home())}):
            with self.assertRaises(ValueError):
                common.validate_project_root(Path.home(), require_workspace=True)

    def test_symlink_escape_is_not_a_safe_workspace_project(self) -> None:
        link = common.WORKSPACE_ROOT / "cf-controlplane-test-symlink-escape"
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to("/tmp")
            detected = common.detect_project_root(link)
            self.assertIsNone(detected)
            with self.assertRaises(ValueError):
                common.validate_project_root(link, require_workspace=True)
        finally:
            if link.exists() or link.is_symlink():
                link.unlink()

    def test_project_env_writes_only_whitelisted_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("EXISTING=value\nCONTEXTFORGE_SERENA_DECISION=unasked\n", encoding="utf-8")
            common.write_project_env(root, {common.ENV_SERENA_DECISION: "accepted"})
            self.assertEqual(
                "EXISTING=value\nCONTEXTFORGE_SERENA_DECISION=accepted\n",
                (root / ".env").read_text(encoding="utf-8"),
            )
            with self.assertRaises(ValueError):
                common.write_project_env(root, {"SECRET_TOKEN": "nope"})

    def test_identity_is_deterministic_for_uid_and_root(self) -> None:
        root = Path("/home/dgk/workspace/legacy-controlplane-archive").resolve()
        self.assertEqual(common.project_root_hash(root, uid=1000), common.project_root_hash(root, uid=1000))
        self.assertNotEqual(common.project_root_hash(root, uid=1000), common.project_root_hash(root, uid=1001))

    def test_empty_nested_workspace_dir_is_its_own_project_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            parent = Path(tmp).resolve()
            (parent / ".env").write_text(
                "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS=complete\n",
                encoding="utf-8",
            )
            child = parent / "empty-child"
            child.mkdir()
            self.assertEqual(child, common.detect_project_root(child))

    def test_non_empty_child_under_marker_root_still_uses_parent(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            parent = Path(tmp).resolve()
            (parent / ".env").write_text(
                "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS=complete\n",
                encoding="utf-8",
            )
            child = parent / "non-empty-child"
            child.mkdir()
            (child / "notes.txt").write_text("not a separate empty project\n", encoding="utf-8")
            self.assertEqual(parent, common.detect_project_root(child))


class ProjectInitReadinessInspectorTests(unittest.TestCase):
    def test_report_distinguishes_primary_root_mismatch_from_legacy_live_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            primary = base / "clean-dev-root"
            legacy = base / "legacy-controlplane-archive"
            primary.mkdir()
            legacy.mkdir()

            legacy_state = project_state.default_state(legacy, status="initialized")
            written_legacy = project_state.write_state_atomic(legacy, legacy_state)
            primary_state_path = project_state.project_state_path(primary)
            primary_state_path.parent.mkdir(mode=0o700, parents=True)
            primary_state_path.write_text(json.dumps(written_legacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            before = primary_state_path.read_text(encoding="utf-8")

            process_snapshot = [
                {
                    "pid": 12345,
                    "script": str(legacy / "scripts" / "contextforge_helper_mcp.py"),
                    "source_root": str(legacy),
                    "command": f"{legacy}/.venv/bin/python {legacy}/scripts/contextforge_helper_mcp.py",
                }
            ]
            report = readiness.build_report(
                project_root=primary,
                compare_roots=[legacy],
                client_types=("codex", "pi"),
                process_snapshot=process_snapshot,
            )

            self.assertEqual(before, primary_state_path.read_text(encoding="utf-8"))
            self.assertEqual("blocked", report["status"])
            self.assertIn("primary_project_state_root_mismatch", report["blockers"])
            self.assertIn("helper_process_source_mismatch", report["blockers"])
            self.assertIn("comparison_root_has_valid_project_state", report["warnings"])
            self.assertEqual("invalid_blocked", report["roots"][0]["readiness_status"])
            self.assertEqual("valid", report["roots"][1]["readiness_status"])
            self.assertFalse(report["roots"][0]["state"]["root_match"]["root_matches"])
            self.assertEqual(str(legacy), report["helper_processes"][0]["source_root"])
            self.assertIn("read-only inspection; no project files are written", report["non_actions"])

    def test_disabled_comparison_root_does_not_warn_as_live_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            primary = base / "clean-dev-root"
            archive = base / "legacy-controlplane-archive"
            primary.mkdir()
            archive.mkdir()
            write_fake_python(primary)
            project_state.write_state_atomic(primary, project_state.default_state(primary, status="initialized"))
            project_state.write_state_atomic(archive, project_state.default_state(archive, status="disabled"))

            report = readiness.build_report(
                project_root=primary,
                compare_roots=[archive],
                client_types=("codex",),
                include_processes=False,
            )

            self.assertEqual("ready", report["status"])
            self.assertNotIn("comparison_root_has_valid_project_state", report["warnings"])
            self.assertEqual("valid", report["roots"][1]["readiness_status"])
            self.assertEqual("disabled", report["roots"][1]["state"]["raw_status"])

    def test_report_blocks_mixed_helper_process_sources(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            primary = base / "clean-dev-root"
            legacy = base / "legacy-controlplane-archive"
            primary.mkdir()
            legacy.mkdir()
            project_state.write_state_atomic(primary, project_state.default_state(primary, status="initialized"))
            process_snapshot = [
                {
                    "pid": 12345,
                    "cwd": str(primary),
                    "script": str(primary / "scripts" / "contextforge_helper_mcp.py"),
                    "source_root": str(primary),
                    "command": f"{primary}/.venv/bin/python {primary}/scripts/contextforge_helper_mcp.py",
                },
                {
                    "pid": 12346,
                    "cwd": str(legacy),
                    "script": str(legacy / "scripts" / "contextforge_helper_mcp.py"),
                    "source_root": str(legacy),
                    "command": f"{legacy}/.venv/bin/python {legacy}/scripts/contextforge_helper_mcp.py",
                },
            ]

            report = readiness.build_report(
                project_root=primary,
                client_types=("codex",),
                process_snapshot=process_snapshot,
            )

        self.assertEqual("blocked", report["status"])
        self.assertIn("helper_process_source_mismatch", report["blockers"])

    def test_relative_helper_process_command_uses_cwd_for_source_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "scripts").mkdir()
            script, source_root = readiness._extract_process_script(
                "python scripts/contextforge_mcp_wrapper.py",
                cwd=str(root),
            )

        self.assertEqual(str(root / "scripts" / "contextforge_mcp_wrapper.py"), script)
        self.assertEqual(str(root), source_root)

    def test_unattributed_helper_process_source_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            project_state.write_state_atomic(root, project_state.default_state(root, status="initialized"))
            report = readiness.build_report(
                project_root=root,
                client_types=("codex",),
                process_snapshot=[
                    {
                        "pid": 12345,
                        "cwd": None,
                        "script": "scripts/contextforge_mcp_wrapper.py",
                        "source_root": None,
                        "command": "python scripts/contextforge_mcp_wrapper.py",
                    }
                ],
            )

        self.assertEqual("blocked", report["status"])
        self.assertIn("helper_process_source_unknown", report["blockers"])

    def test_cli_emits_clean_json_without_process_probe(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            write_fake_python(root)
            project_state.write_state_atomic(root, project_state.default_state(root, status="initialized"))

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "inspect_project_init_readiness.py"),
                    "--project-root",
                    str(root),
                    "--client-type",
                    "codex",
                    "--no-processes",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertTrue(result.stdout.startswith("{"), result.stdout[:200])
        parsed = json.loads(result.stdout)
        self.assertEqual(readiness.REPORT_SCHEMA_URI, parsed["schema_uri"])
        self.assertEqual("ready", parsed["status"])
        self.assertEqual([], parsed["helper_processes"])
        self.assertEqual(["codex"], list(parsed["roots"][0]["inspections"]))
        self.assertTrue(parsed["activation_artifacts"]["python_environment"]["is_executable"])

    def test_activation_artifacts_report_legacy_config_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve() / "cf-controlplane"
            root.mkdir()
            legacy = project_state.WORKSPACE_ROOT / "legacy-controlplane-slices" / "repo-local-skills-and-governance" / "missing-fixture-root"
            write_fake_python(root)
            project_state.write_state_atomic(root, project_state.default_state(root, status="initialized"))
            config = root / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                f"""
[mcp_servers.contextforge-helper]
command = "{legacy}/.venv/bin/python"
args = ["{legacy}/scripts/contextforge_helper_mcp.py"]
""".lstrip(),
                encoding="utf-8",
            )
            identity = common.project_identity(root)
            legacy_serena = root / "server-instances" / identity.instance_slug
            legacy_serena.mkdir(parents=True)
            (legacy_serena / "instance.json").write_text(
                json.dumps({"canonical_project_root": str(legacy), "name": identity.instance_slug}),
                encoding="utf-8",
            )
            before = {
                path: path.read_text(encoding="utf-8")
                for path in root.rglob("*")
                if path.is_file()
            }

            report = readiness.build_report(
                project_root=root,
                client_types=("codex",),
                include_processes=False,
            )

            after = {
                path: path.read_text(encoding="utf-8")
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertEqual(before, after)
        self.assertEqual("blocked", report["status"])
        self.assertIn("codex_config_legacy_root_references", report["blockers"])
        self.assertIn("codex_config_missing_mcp_path", report["blockers"])
        self.assertIn("serena_project_instance_root_mismatch", report["warnings"])
        artifacts = report["activation_artifacts"]
        self.assertTrue(artifacts["python_environment"]["is_executable"])
        self.assertEqual(1, artifacts["codex_config"]["mcp_server_count"])
        self.assertTrue(artifacts["codex_config"]["mcp_servers"][0]["legacy_bound"])
        self.assertEqual("serena", artifacts["serena_project_instance"]["expected"]["service_binding"].split(":", 1)[0])

    def test_project_name_mismatch_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            write_fake_python(root)
            state = project_state.default_state(root, status="initialized")
            state["project"]["name"] = "cf-controlplane"
            project_state.write_state_atomic(root, state)

            report = readiness.build_report(
                project_root=root,
                client_types=("codex",),
                include_processes=False,
            )

        self.assertEqual("blocked", report["status"])
        self.assertIn("project_state_name_mismatch", report["blockers"])

    def test_serena_compatibility_registration_refuses_live_mutation_by_default(self) -> None:
        with (
            mock.patch.object(serena_registration.gateway, "_read_env") as read_env,
            mock.patch.object(serena_registration.gateway, "_token") as token,
            mock.patch.object(serena_registration, "ensure_gateway") as ensure_gateway,
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            result = serena_registration.main([])

        self.assertEqual(2, result)
        self.assertIn("Refusing to mutate live ContextForge Serena registration", stderr.getvalue())
        read_env.assert_not_called()
        token.assert_not_called()
        ensure_gateway.assert_not_called()

    def test_serena_registration_reconciles_legacy_gateway_by_url(self) -> None:
        requests: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_items(path: str, token: str) -> list[dict[str, object]]:
            self.assertEqual("token", token)
            self.assertEqual("/gateways?include_inactive=true&limit=1000", path)
            return [
                {
                    "id": "gateway-old",
                    "name": "stale-serena-gateway",
                    "slug": "stale-serena-gateway",
                    "url": serena_registration.GATEWAY_URL,
                }
            ]

        def fake_request(method: str, path: str, *, token: str, body: dict[str, object] | None = None) -> dict[str, object]:
            self.assertEqual("token", token)
            requests.append((method, path, body))
            return {"id": "gateway-old", **(body or {})}

        with (
            mock.patch.object(serena_registration, "api_items", side_effect=fake_items),
            mock.patch.object(serena_registration, "api_request", side_effect=fake_request),
        ):
            row = serena_registration.ensure_gateway("token")

        self.assertEqual("gateway-old", row["id"])
        self.assertEqual([("PUT", "/gateways/gateway-old")], [(method, path) for method, path, _body in requests])
        body = requests[0][2] or {}
        self.assertEqual(serena_registration.GATEWAY_NAME, body["name"])
        self.assertEqual(serena_registration.GATEWAY_URL, body["url"])
        self.assertTrue(body["enabled"])
        self.assertNotIn("stale-serena-gateway", body["tags"])

    def test_serena_registration_replaces_legacy_server_metadata_and_resources(self) -> None:
        requests: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_items(path: str, token: str) -> list[dict[str, object]]:
            self.assertEqual("token", token)
            if path == "/servers?include_inactive=true&limit=1000":
                return [
                    {
                        "id": "server-old",
                        "name": "stale_serena_server",
                        "description": "Virtual server exposing Serena for the ContextForge operator repository.",
                        "associatedResources": ["old-resource"],
                        "associatedPrompts": ["old-prompt"],
                        "associatedA2aAgents": ["a2a-old"],
                        "tags": [{"id": "serena", "label": "serena"}],
                    }
                ]
            if path == "/resources?include_inactive=true&limit=1000":
                return [
                    {
                        "id": "old-resource",
                        "uri": "contextforge://retired/serena-project-instance-guidance/v14",
                        "tags": ["serena"],
                    },
                    {
                        "id": "new-resource",
                        "uri": "contextforge://cf-controlplane/serena-project-instance-guidance/v15",
                        "tags": ["contextforge", "serena"],
                    },
                ]
            if path == "/prompts?include_inactive=true&limit=1000":
                return [
                    {"id": "new-prompt", "customName": "serena_project_instance_guidance"},
                    {"id": "other-prompt", "customName": "serena_other_guidance"},
                ]
            raise AssertionError(f"unexpected path: {path}")

        def fake_request(method: str, path: str, *, token: str, body: dict[str, object] | None = None) -> dict[str, object]:
            self.assertEqual("token", token)
            requests.append((method, path, body))
            return {"id": "server-old", **(body or {})}

        with (
            mock.patch.object(serena_registration, "api_items", side_effect=fake_items),
            mock.patch.object(serena_registration, "api_request", side_effect=fake_request),
        ):
            row = serena_registration.ensure_server("token", ["tool-a", "tool-b"])

        self.assertEqual("server-old", row["id"])
        self.assertEqual([("PUT", "/servers/server-old")], [(method, path) for method, path, _body in requests])
        body = requests[0][2] or {}
        self.assertEqual(serena_registration.SERVER_NAME, body["name"])
        self.assertEqual(["tool-a", "tool-b"], body["associatedTools"])
        self.assertEqual(["new-resource"], body["associatedResources"])
        self.assertEqual(["new-prompt"], body["associatedPrompts"])
        self.assertEqual(["contextforge", "serena", "cf-controlplane"], body["tags"])


class DirtyCheckoutRebindPlannerTests(unittest.TestCase):
    def _write_minimal_surfaces(self, target: Path, legacy: Path) -> None:
        (target / ".codex" / "skills" / "contextforge-project-init").mkdir(parents=True)
        (target / ".project").mkdir(parents=True)
        (target / ".serena").mkdir(parents=True)
        (target / "server-instances" / "serena-cf-controlplane-d46fe58a2a20").mkdir(parents=True)
        (target / "server-instances" / "mentality").mkdir(parents=True)
        (target / "scripts").mkdir(parents=True)

        (target / ".codex" / "config.toml").write_text(
            f"""
[mcp_servers.serena]
command = "{legacy}/.venv/bin/python"
args = ["{legacy}/scripts/contextforge_mcp_wrapper.py", "serena_cf_controlplane_d46fe58a2a20_server"]
cwd = "{legacy}"
""".lstrip(),
            encoding="utf-8",
        )
        legacy_state = project_state.default_state(legacy, status="initialized")
        written_legacy = project_state.write_state_atomic(legacy, legacy_state)
        (target / ".project" / "context_forge_state.json").write_text(
            json.dumps(written_legacy, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (target / "server-instances" / "serena-cf-controlplane-d46fe58a2a20" / "instance.json").write_text(
            json.dumps(
                {
                    "name": "serena-cf-controlplane-d46fe58a2a20",
                    "canonical_project_root": str(legacy),
                    "codex_config_path": str(legacy / ".codex" / "config.toml"),
                    "scope": {"workspace_root": str(legacy)},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "server-instances" / "serena-cf-controlplane-d46fe58a2a20" / "run-server.sh").write_text(
            f'#!/usr/bin/env bash\nexec serena-mcp-server --project "{legacy}"\n',
            encoding="utf-8",
        )
        (target / "server-instances" / "serena-cf-controlplane-d46fe58a2a20" / "lsp.env").write_text(
            f'PATH="{legacy}/server-instances/serena-cf-controlplane-d46fe58a2a20/lsp-tools/bin:$PATH"\n',
            encoding="utf-8",
        )
        (target / "server-instances" / "mentality" / "instance.json").write_text(
            json.dumps({"backend": {"working_directory": str(legacy)}}, indent=2) + "\n",
            encoding="utf-8",
        )
        (target / ".serena" / "project.yml").write_text('project_name: "cf-controlplane"\n', encoding="utf-8")
        (target / ".codex" / "skills" / "contextforge-project-init" / "SKILL.md").write_text(
            f"Use project_root={legacy}\n",
            encoding="utf-8",
        )
        (target / "scripts" / "register_project_init_prompt.py").write_text(
            f'PROJECT_ROOT = "{legacy}"\n',
            encoding="utf-8",
        )
        (target / "scripts" / "register_serena_cf_controlplane_service.py").write_text(
            f'DESCRIPTION = "Serena scoped to {legacy}"\n',
            encoding="utf-8",
        )
        (target / "scripts" / "install_user_systemd.py").write_text(
            'UNIT = "contextforge-serena-cf-controlplane-d46fe58a2a20.service"\n',
            encoding="utf-8",
        )

    def test_preflight_reports_path_bound_surfaces_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "clean-root"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            self._write_minimal_surfaces(target, legacy)
            before = {
                path: path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            }

            report = dirty_rebind.build_report(
                target_root=target,
                legacy_root=legacy,
                client_types=("codex",),
                include_processes=False,
            )

            after = {
                path: path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            }
        self.assertEqual(before, after)
        self.assertEqual(dirty_rebind.REPORT_SCHEMA_URI, report["schema_uri"])
        self.assertEqual("blocked", report["status"])
        self.assertTrue(report["approval_required"])
        self.assertIn("approval_required_before_rebind", report["blockers"])
        self.assertIn("codex_project_config:surface_legacy_root_reference", report["blockers"])
        self.assertIn("project_state:project_state_root_mismatch", report["blockers"])
        self.assertIn("primary_project_state_root_mismatch", report["blockers"])
        surfaces = {surface["surface_id"]: surface for surface in report["surfaces"]}
        self.assertTrue(surfaces["codex_project_config"]["rebind_required"])
        self.assertTrue(surfaces["project_state"]["rebind_required"])
        self.assertEqual(str(target), surfaces["project_state"]["expected_root"])
        self.assertIn("read-only preflight; no project files are written", report["non_actions"])

    def test_preflight_marks_missing_optional_registration_script_as_warning(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "clean-root"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            self._write_minimal_surfaces(target, legacy)
            (target / "scripts" / "register_serena_cf_controlplane_service.py").unlink()

            report = dirty_rebind.build_report(
                target_root=target,
                legacy_root=legacy,
                client_types=("codex",),
                include_processes=False,
            )

        surfaces = {surface["surface_id"]: surface for surface in report["surfaces"]}
        self.assertEqual("attention_required", surfaces["serena_registration_script"]["status"])
        self.assertIn("optional_surface_missing", surfaces["serena_registration_script"]["warnings"])

    def test_preflight_approval_acknowledgement_removes_approval_blocker(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "clean-root"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            self._write_minimal_surfaces(target, legacy)
            project_state.write_state_atomic(
                target,
                project_state.default_state(target, status="initialized"),
                allow_invalid_existing=True,
            )
            for path in target.rglob("*"):
                if path.is_file():
                    path.write_text(path.read_text(encoding="utf-8").replace(str(legacy), str(target)), encoding="utf-8")

            report = dirty_rebind.build_report(
                target_root=target,
                legacy_root=legacy,
                client_types=("codex",),
                include_processes=False,
                approval_acknowledged=True,
                approval_ref="test-approval",
            )

        self.assertFalse(report["approval_required"])
        self.assertTrue(report["approval"]["acknowledged"])
        self.assertEqual("test-approval", report["approval"]["ref"])
        self.assertNotIn("approval_required_before_rebind", report["blockers"])

    def test_preflight_cli_emits_clean_json_without_process_probe(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "clean-root"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            self._write_minimal_surfaces(target, legacy)

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "plan_dirty_checkout_rebind.py"),
                    "--target-root",
                    str(target),
                    "--legacy-root",
                    str(legacy),
                    "--client-type",
                    "codex",
                    "--no-processes",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertTrue(result.stdout.startswith("{"), result.stdout[:200])
        parsed = json.loads(result.stdout)
        self.assertEqual(dirty_rebind.REPORT_SCHEMA_URI, parsed["schema_uri"])
        self.assertEqual("blocked", parsed["status"])
        self.assertEqual([], parsed["helper_processes"])


class CodexGlobalConfigMigrationPlannerTests(unittest.TestCase):
    def _write_global_config(self, path: Path, legacy: Path) -> None:
        path.write_text(
            f"""
[mcp_servers.contextforge-helper]
command = "{legacy}/.venv/bin/python"
args = ["{legacy}/scripts/contextforge_helper_mcp.py"]

[projects."{legacy}"]
trust_level = "trusted"

[hooks]

[[hooks.SessionStart]]
matcher = "startup"

[[hooks.SessionStart.hooks]]
type = "command"
command = "{legacy}/.venv/bin/python {legacy}/scripts/codex_project_init_hook.py"
timeout = 10

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "{legacy}/.venv/bin/python {legacy}/scripts/codex_project_init_hook.py"
timeout = 10

[hooks.state."{legacy}/.codex/config.toml:pre_compact:0:0"]
trusted_hash = "sha256:precompact"

[hooks.state."{legacy}/.codex/config.toml:session_start:0:0"]
trusted_hash = "sha256:sessionstart"
""".lstrip(),
            encoding="utf-8",
        )

    def test_global_config_plan_classifies_stale_legacy_entries_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")

            report = codex_global_plan.build_report(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
            )

            after = config.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(codex_global_plan.REPORT_SCHEMA_URI, report["schema_uri"])
        self.assertEqual("blocked", report["status"])
        self.assertTrue(report["approval_required"])
        self.assertIn("approval_required_before_user_global_codex_config_or_trust_mutation", report["blockers"])
        self.assertIn("clean_root_project_trust_missing", report["warnings"])
        self.assertIn("clean_root_project_local_hook_state_missing", report["warnings"])
        entries = {entry["entry_id"]: entry for entry in report["entries"]}
        self.assertEqual("replace_with_clean_root", entries["global_mcp_contextforge_helper"]["bucket"])
        self.assertEqual(str(target / ".venv/bin/python"), entries["global_mcp_contextforge_helper"]["target_value"]["command"])
        self.assertEqual("replace_with_clean_root", entries["legacy_project_trust"]["bucket"])
        self.assertEqual(str(target), entries["legacy_project_trust"]["target_value"]["project"])
        self.assertEqual(
            "preserve_or_prune_decision_required",
            entries["legacy_project_local_hook_state"]["bucket"],
        )
        self.assertIn("read-only plan; no user-global config or trust file is written", report["non_actions"])
        self.assertIn(f"codex -C {target} mcp list --json", report["readback_commands"])
        stale_hardcoded_readback = (
            "codex -C "
            + "/home/dgk/workspace/"
            + "legacy-controlplane-slices/repo-local-skills-and-governance mcp list --json"
        )
        self.assertNotIn(
            stale_hardcoded_readback,
            report["readback_commands"],
        )

    def test_global_config_plan_reports_clean_root_presence_after_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            with config.open("a", encoding="utf-8") as handle:
                handle.write(
                    f'\n[projects."{target}"]\ntrust_level = "trusted"\n'
                    f'\n[hooks.state."{target}/.codex/config.toml:pre_compact:0:0"]\n'
                    'trusted_hash = "sha256:cleanprecompact"\n'
                )

            report = codex_global_plan.build_report(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
            )

        self.assertEqual("ready", report["status"])
        self.assertFalse(report["approval_required"])
        self.assertEqual("test approval", report["approval"]["ref"])
        self.assertTrue(report["clean_root_presence"]["project_trust_present"])
        self.assertEqual(1, report["clean_root_presence"]["project_local_hook_state_count"])
        self.assertNotIn("clean_root_project_trust_missing", report["warnings"])
        self.assertNotIn("clean_root_project_local_hook_state_missing", report["warnings"])

    def test_global_config_plan_reports_hook_retarget_side_effect_preflight(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)

            report = codex_global_plan.build_report(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
            )

        preflight = report["hook_retarget_preflight"]
        self.assertEqual(["SessionStart", "UserPromptSubmit"], [item["event"] for item in preflight["affected_hook_commands"]])
        self.assertIn(f"{legacy}/.codex/config.toml:session_start:0:0", preflight["legacy_hook_state_records"])
        self.assertEqual([], preflight["clean_root_hook_state_records"])
        prompt_resource = preflight["first_run_side_effect_model"]["prompt_resource_readback"]
        self.assertEqual("unknown_prompt_resource_readback_required", prompt_resource["status"])
        self.assertTrue(prompt_resource["approval_required_before_hook_execution"])
        self.assertIn("no hook is executed", preflight["non_actions"])

    def test_prompt_resource_side_effect_classifier_distinguishes_fresh_from_upsert(self) -> None:
        fresh = codex_global_plan.classify_prompt_resource_side_effect(
            prompt_record={"id": "prompt-id", "name": common.PROJECT_INIT_PROMPT_NAME, "tags": [common.PROMPT_VERSION]},
            resource_record={
                "id": "resource-id",
                "name": common.PROJECT_INIT_RESOURCE_NAME,
                "uri": common.PROJECT_INIT_RESOURCE_URI,
                "tags": [common.PROMPT_VERSION],
            },
            prompt_version=common.PROMPT_VERSION,
            resource_uri=common.PROJECT_INIT_RESOURCE_URI,
        )
        missing_prompt = codex_global_plan.classify_prompt_resource_side_effect(
            prompt_record=None,
            resource_record={
                "id": "resource-id",
                "name": common.PROJECT_INIT_RESOURCE_NAME,
                "uri": common.PROJECT_INIT_RESOURCE_URI,
                "tags": [common.PROMPT_VERSION],
            },
            prompt_version=common.PROMPT_VERSION,
            resource_uri=common.PROJECT_INIT_RESOURCE_URI,
        )
        stale_resource = codex_global_plan.classify_prompt_resource_side_effect(
            prompt_record={"id": "prompt-id", "name": common.PROJECT_INIT_PROMPT_NAME, "tags": [common.PROMPT_VERSION]},
            resource_record={
                "id": "resource-id",
                "name": common.PROJECT_INIT_RESOURCE_NAME,
                "uri": common.PROJECT_INIT_RESOURCE_URI,
                "tags": ["old"],
            },
            prompt_version=common.PROMPT_VERSION,
            resource_uri=common.PROJECT_INIT_RESOURCE_URI,
        )
        missing_ids = codex_global_plan.classify_prompt_resource_side_effect(
            prompt_record={"name": common.PROJECT_INIT_PROMPT_NAME, "tags": [common.PROMPT_VERSION]},
            resource_record={
                "name": common.PROJECT_INIT_RESOURCE_NAME,
                "uri": common.PROJECT_INIT_RESOURCE_URI,
                "tags": [common.PROMPT_VERSION],
            },
            prompt_version=common.PROMPT_VERSION,
            resource_uri=common.PROJECT_INIT_RESOURCE_URI,
        )

        self.assertEqual("read_only_render_path", fresh["status"])
        self.assertFalse(fresh["would_call_upgrade_project_init_prompt"])
        self.assertEqual("would_upsert_prompt_resource", missing_prompt["status"])
        self.assertIn("project_init_prompt_missing", missing_prompt["reasons"])
        self.assertEqual("would_upsert_prompt_resource", stale_resource["status"])
        self.assertIn("project_init_resource_stale", stale_resource["reasons"])
        self.assertEqual("would_upsert_prompt_resource", missing_ids["status"])
        self.assertIn("project_init_prompt_missing_id", missing_ids["reasons"])
        self.assertIn("project_init_resource_missing_id", missing_ids["reasons"])

    def test_global_config_apply_requires_approval_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")

            with self.assertRaises(PermissionError):
                codex_global_plan.apply_migration(
                    config_path=config,
                    target_root=target,
                    legacy_root=legacy,
                    approval_acknowledged=False,
                )

            self.assertEqual(before, config.read_text(encoding="utf-8"))
            self.assertEqual([], list(base.glob(f"codex-config.toml{codex_global_plan.BACKUP_SUFFIX}-*")))

    def test_global_config_apply_is_staged_idempotent_and_preserves_provenance(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            backup = base / "pre-change.toml"
            self._write_global_config(config, legacy)

            first = codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
                backup_path=backup,
            )
            migrated = config.read_text(encoding="utf-8")
            backup_created = backup.exists()
            second = codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
                backup_path=base / "second-backup.toml",
            )

        self.assertTrue(first["changed"])
        self.assertEqual("pending_restart", first["status"])
        self.assertEqual(str(backup), first["backup_path"])
        self.assertTrue(backup_created)
        self.assertFalse(second["changed"])
        self.assertEqual("already_converged", second["status"])
        self.assertIn(f'command = "{target}/.venv/bin/python"', migrated)
        self.assertIn(f'args = ["{target}/scripts/contextforge_helper_mcp.py"]', migrated)
        self.assertIn(f'[projects."{target}"]', migrated)
        self.assertIn(f'[projects."{legacy}"]', migrated)
        self.assertIn(f'[hooks.state."{legacy}/.codex/config.toml:pre_compact:0:0"]', migrated)
        self.assertEqual(2, migrated.count(f"{target}/scripts/codex_project_init_hook.py"))

    def test_global_config_apply_de_duplicates_partial_hook_migration(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            with config.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n[[hooks.SessionStart.hooks]]\n"
                    'type = "command"\n'
                    f'command = "{target}/.venv/bin/python {target}/scripts/codex_project_init_hook.py"\n'
                    "timeout = 10\n"
                )

            codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
            )
            migrated = config.read_text(encoding="utf-8")

        self.assertEqual(2, migrated.count(f"{target}/scripts/codex_project_init_hook.py"))
        self.assertNotIn(f"{legacy}/scripts/codex_project_init_hook.py", migrated)

    def test_global_config_apply_scopes_helper_rewrite_to_owned_mcp_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            with config.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n[mcp_servers.unrelated]\n"
                    f'command = "{legacy}/.venv/bin/python"\n'
                    'args = ["-m", "unrelated"]\n'
                )

            codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
            )
            migrated = config.read_text(encoding="utf-8")

        self.assertIn("[mcp_servers.unrelated]", migrated)
        self.assertIn(f'command = "{legacy}/.venv/bin/python"', migrated)
        self.assertIn(f'args = ["-m", "unrelated"]', migrated)

    def test_global_config_apply_refuses_to_overwrite_explicit_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            backup = base / "pre-change.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")
            backup.write_text("existing backup", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                codex_global_plan.apply_migration(
                    config_path=config,
                    target_root=target,
                    legacy_root=legacy,
                    approval_acknowledged=True,
                    approval_ref="test approval",
                    backup_path=backup,
                )

            self.assertEqual(before, config.read_text(encoding="utf-8"))
            self.assertEqual("existing backup", backup.read_text(encoding="utf-8"))

    def test_global_config_apply_refuses_config_path_as_backup_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")

            with self.assertRaises(ValueError):
                codex_global_plan.apply_migration(
                    config_path=config,
                    target_root=target,
                    legacy_root=legacy,
                    approval_acknowledged=True,
                    approval_ref="test approval",
                    backup_path=config,
                )

            self.assertEqual(before, config.read_text(encoding="utf-8"))

    def test_global_config_apply_requires_separate_approval_for_destructive_options(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")

            with self.assertRaises(PermissionError):
                codex_global_plan.apply_migration(
                    config_path=config,
                    target_root=target,
                    legacy_root=legacy,
                    approval_acknowledged=True,
                    approval_ref="base approval only",
                    remove_legacy_trust=True,
                )
            with self.assertRaises(PermissionError):
                codex_global_plan.apply_migration(
                    config_path=config,
                    target_root=target,
                    legacy_root=legacy,
                    approval_acknowledged=True,
                    approval_ref="base approval only",
                    prune_legacy_hook_state=True,
                )

            self.assertEqual(before, config.read_text(encoding="utf-8"))

    def test_global_config_apply_can_use_separately_approved_destructive_options(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)

            result = codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="base plus cleanup approval",
                remove_legacy_trust=True,
                remove_legacy_trust_approved=True,
                prune_legacy_hook_state=True,
                prune_legacy_hook_state_approved=True,
            )
            migrated = config.read_text(encoding="utf-8")

        self.assertEqual("pending_restart", result["status"])
        self.assertEqual("removed_by_separate_approval", result["policies"]["legacy_project_trust"])
        self.assertEqual("pruned_by_separate_approval", result["policies"]["legacy_hook_state"])
        self.assertNotIn(f'[projects."{legacy}"]', migrated)
        self.assertNotIn(f'[hooks.state."{legacy}/.codex/config.toml:pre_compact:0:0"]', migrated)

    def test_global_config_rollback_restores_backup_with_new_safety_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            backup = base / "pre-change.toml"
            self._write_global_config(config, legacy)
            original = config.read_text(encoding="utf-8")
            codex_global_plan.apply_migration(
                config_path=config,
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test approval",
                backup_path=backup,
            )

            rollback = codex_global_plan.rollback_from_backup(
                config_path=config,
                backup_path=backup,
                approval_acknowledged=True,
                approval_ref="rollback approval",
            )
            restored = config.read_text(encoding="utf-8")
            rollback_backup_exists = Path(rollback["pre_rollback_backup_path"]).exists()

        self.assertEqual("rolled_back_pending_restart", rollback["status"])
        self.assertEqual(original, restored)
        self.assertTrue(rollback_backup_exists)

    def test_global_config_rollback_refuses_live_config_as_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            legacy = base / "legacy-controlplane-archive"
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)
            before = config.read_text(encoding="utf-8")

            with self.assertRaises(ValueError):
                codex_global_plan.rollback_from_backup(
                    config_path=config,
                    backup_path=config,
                    approval_acknowledged=True,
                    approval_ref="rollback approval",
                )

            self.assertEqual(before, config.read_text(encoding="utf-8"))
            self.assertEqual([], list(base.glob(f"codex-config.toml{codex_global_plan.BACKUP_SUFFIX}-*")))

    def test_global_config_plan_cli_emits_clean_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "repo-local-skills-and-governance"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, legacy)

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "plan_codex_global_config_migration.py"),
                    "--config-path",
                    str(config),
                    "--target-root",
                    str(target),
                    "--legacy-root",
                    str(legacy),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(codex_global_plan.REPORT_SCHEMA_URI, parsed["schema_uri"])
        self.assertEqual("blocked", parsed["status"])


class CodexRuntimeReadbackInspectorTests(unittest.TestCase):
    def _write_global_config(self, path: Path, target: Path, legacy: Path) -> None:
        path.write_text(
            f"""
[mcp_servers.contextforge-helper]
command = "{target}/.venv/bin/python"
args = ["{target}/scripts/contextforge_helper_mcp.py"]

[projects."{target}"]
trust_level = "trusted"

[hooks]

[[hooks.SessionStart]]
matcher = "startup"

[[hooks.SessionStart.hooks]]
type = "command"
command = "{target}/.venv/bin/python {target}/scripts/codex_project_init_hook.py"
timeout = 10

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "{target}/.venv/bin/python {target}/scripts/codex_project_init_hook.py"
timeout = 10

[hooks.state."{target}/.codex/config.toml:session_start:0:0"]
trusted_hash = "sha256:target"

[projects."{legacy}"]
trust_level = "trusted"
""".lstrip(),
            encoding="utf-8",
        )

    def test_runtime_readback_blocks_legacy_mcp_and_process_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "cf-controlplane"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, target, legacy)
            readbacks = {
                "project_explicit_root": {
                    "status": "ok",
                    "summary": {
                        "legacy_root_reference_counts": {str(legacy): 1},
                        "non_target_servers": ["context7"],
                    },
                }
            }
            processes = [
                {
                    "pid": 123,
                    "ppid": 1,
                    "script": str(legacy / "scripts" / "contextforge_mcp_wrapper.py"),
                    "source_root": str(legacy),
                    "command": f"{legacy}/.venv/bin/python {legacy}/scripts/contextforge_mcp_wrapper.py context7",
                }
            ]

            report = codex_runtime_readback.build_report(
                project_root=target,
                config_path=config,
                legacy_roots=(legacy,),
                codex_mcp_readbacks=readbacks,
                process_snapshot=processes,
            )

        self.assertEqual(codex_runtime_readback.REPORT_SCHEMA_URI, report["schema_uri"])
        self.assertEqual("blocked", report["status"])
        self.assertIn("project_explicit_root_codex_mcp_readback_legacy_root_reference", report["blockers"])
        self.assertIn("codex_runtime_legacy_helper_processes_present", report["blockers"])
        self.assertIn("Codex Desktop project open/reload/new-session action", " ".join(report["human_boundaries"]))
        self.assertIn("no process termination or restart", report["non_actions"])

    def test_runtime_readback_accepts_target_mcp_and_process_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "cf-controlplane"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, target, legacy)
            readbacks = {
                "project_explicit_root": {
                    "status": "ok",
                    "summary": {
                        "legacy_root_reference_counts": {str(legacy): 0},
                        "non_target_servers": [],
                    },
                }
            }
            processes = [
                {
                    "pid": 123,
                    "ppid": 1,
                    "script": str(target / "scripts" / "contextforge_helper_mcp.py"),
                    "source_root": str(target),
                    "command": f"{target}/.venv/bin/python {target}/scripts/contextforge_helper_mcp.py",
                }
            ]

            report = codex_runtime_readback.build_report(
                project_root=target,
                config_path=config,
                legacy_roots=(legacy,),
                codex_mcp_readbacks=readbacks,
                process_snapshot=processes,
            )

        self.assertEqual("readback_clean", report["status"])
        self.assertEqual([], report["blockers"])
        self.assertEqual([], report["warnings"])

    def test_runtime_readback_cli_emits_clean_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "cf-controlplane"
            legacy = base / "legacy-controlplane-archive"
            target.mkdir()
            legacy.mkdir()
            config = base / "codex-config.toml"
            self._write_global_config(config, target, legacy)

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "inspect_codex_runtime_readback.py"),
                    "--project-root",
                    str(target),
                    "--config-path",
                    str(config),
                    "--legacy-root",
                    str(legacy),
                    "--no-codex-mcp",
                    "--no-processes",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=REPO_ROOT,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(codex_runtime_readback.REPORT_SCHEMA_URI, parsed["schema_uri"])
        self.assertIn("read-only inspection; no global Codex config write", parsed["non_actions"])


class SerenaManagerTests(unittest.TestCase):
    def test_operator_reserved_port_is_not_per_project_allocatable(self) -> None:
        self.assertNotIn(9108, serena_manager.PORT_RANGE)
        self.assertIn(9108, serena_manager.OPERATOR_RESERVED_PORTS)

        with (
            mock.patch.object(serena_manager, "used_manifest_ports", return_value=set()),
            mock.patch.object(serena_manager, "socket_port_open", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "operator singleton"):
                serena_manager.reserve_port(preferred=9108)

    def test_operator_reserved_port_is_skipped_if_range_changes(self) -> None:
        with (
            mock.patch.object(serena_manager, "PORT_RANGE", range(9108, 9111)),
            mock.patch.object(serena_manager, "used_manifest_ports", return_value=set()),
            mock.patch.object(serena_manager, "socket_port_open", return_value=False),
        ):
            self.assertEqual(9109, serena_manager.reserve_port())

    def test_gemini_project_init_hook_uses_gemini_lifecycle_events(self) -> None:
        self.assertEqual({"SessionStart", "BeforeAgent"}, set(gemini_project_init_hook.GEMINI_HOOK_EVENTS))
        self.assertEqual({"experimental.chat.system.transform", "session.created"}, set(opencode_project_init_hook.OPENCODE_HOOK_EVENTS))
        self.assertEqual({"SessionStart", "UserPromptSubmit"}, set(init_hook.CODEX_HOOK_EVENTS))

    def test_opencode_project_init_hook_routes_to_opencode_client_context(self) -> None:
        calls: list[dict[str, object]] = []
        original = opencode_project_init_hook.codex_project_init_hook.main_for_events
        try:
            def fake_main_for_events(events: object, *, suppress_output: bool = False, target_client: str = "codex") -> int:
                calls.append(
                    {
                        "events": set(events),  # type: ignore[arg-type]
                        "suppress_output": suppress_output,
                        "target_client": target_client,
                    }
                )
                return 0

            opencode_project_init_hook.codex_project_init_hook.main_for_events = fake_main_for_events  # type: ignore[assignment]
            self.assertEqual(0, opencode_project_init_hook.main())
        finally:
            opencode_project_init_hook.codex_project_init_hook.main_for_events = original  # type: ignore[assignment]

        self.assertEqual(1, len(calls))
        self.assertEqual({"experimental.chat.system.transform", "session.created"}, calls[0]["events"])
        self.assertTrue(calls[0]["suppress_output"])
        self.assertEqual("opencode", calls[0]["target_client"])

    def test_gemini_project_init_hook_import_suppresses_gateway_stderr(self) -> None:
        cases = [
            ("gemini_project_init_hook", "GEMINI_HOOK_EVENTS", "BeforeAgent,SessionStart"),
            ("opencode_project_init_hook", "OPENCODE_HOOK_EVENTS", "experimental.chat.system.transform,session.created"),
        ]
        for module_name, attr_name, expected in cases:
            with self.subTest(module=module_name):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import sys; "
                            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
                            f"import {module_name}; "
                            f"print(','.join(sorted({module_name}.{attr_name})))"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                self.assertEqual(expected, result.stdout.strip())

    def test_merge_codex_config_refuses_unmanaged_serena(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            config = root / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")
            identity = common.project_identity(root)
            with self.assertRaises(RuntimeError):
                serena_manager.merge_codex_config(identity)

    def test_merge_codex_config_manages_owned_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            serena_manager.merge_codex_config(identity)
            config = (root / ".codex/config.toml").read_text(encoding="utf-8")
            self.assertIn(f'contextforge-project-init-owner = "{identity.server_name}"', config)
            self.assertIn(str(serena_manager.WRAPPER_PATH), config)
            self.assertIn(identity.server_name, config)

    def test_create_respects_write_codex_config_flag(self) -> None:
        for write_codex_config in (False, True):
            with self.subTest(write_codex_config=write_codex_config):
                with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as runtime:
                    root = Path(tmp).resolve()
                    runtime_root = Path(runtime)
                    repo_root = runtime_root / "repo"
                    repo_root.mkdir()
                    run_root = runtime_root / "run"
                    systemd_root = runtime_root / "systemd"
                    args = Namespace(
                        project_root=str(root),
                        require_workspace=True,
                        language=None,
                        replace_existing_serena_config=False,
                        verify=False,
                        app_server=False,
                        write_codex_config=write_codex_config,
                    )
                    with (
                        mock.patch.object(serena_manager, "REPO_ROOT", repo_root),
                        mock.patch.object(serena_manager, "RUN_ROOT", run_root),
                        mock.patch.object(serena_manager, "LOCK_PATH", run_root / "serena.lock"),
                        mock.patch.object(serena_manager, "SYSTEMD_USER_DIR", systemd_root),
                        mock.patch.object(serena_manager, "reserve_port", return_value=9119),
                        mock.patch.object(serena_manager, "verify_systemd_service"),
                        mock.patch.object(serena_manager, "wait_for_port"),
                        mock.patch.object(
                            serena_manager.gateway,
                            "_read_env",
                            return_value={
                                "PLATFORM_ADMIN_EMAIL": "admin@contextforge.dev",
                                "PLATFORM_ADMIN_PASSWORD": "password",
                            },
                        ),
                        mock.patch.object(serena_manager.gateway, "_token", return_value="token"),
                        mock.patch.object(
                            serena_manager,
                            "register_gateway_and_server",
                            return_value={"gateway_id": "gateway-1", "server_id": "server-1"},
                        ),
                        mock.patch.object(serena_manager, "merge_codex_config") as merge_codex_config,
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        result = serena_manager.create(args)

                    self.assertEqual(0, result)
                    self.assertEqual(write_codex_config, merge_codex_config.called)

    def test_legacy_manifest_project_root_is_detected(self) -> None:
        data = {
            "scope": {"workspace_root": "/home/dgk/workspace/legacy-controlplane-archive"},
            "backend": {"args": ["--project", "/wrong"]},
        }
        self.assertEqual(
            "/home/dgk/workspace/legacy-controlplane-archive",
            serena_manager.manifest_project_root(data),
        )

    def test_app_server_status_shapes_are_parsed(self) -> None:
        server = {"name": "serena", "tools": {"a": {"name": "serena-project-get-current-config"}}}
        for response in (
            {"result": {"data": [server]}},
            {"result": {"servers": [server]}},
            {"result": [server]},
        ):
            self.assertEqual([server], serena_manager.app_server_servers(response))

    def test_app_server_tool_names_accept_dict_and_list(self) -> None:
        self.assertEqual(
            ["serena-project-get-current-config"],
            serena_manager.app_server_tool_names({"tools": {"x": {"name": "serena-project-get-current-config"}}}),
        )
        self.assertEqual(
            ["serena-project-get-current-config"],
            serena_manager.app_server_tool_names({"tools": [{"name": "serena-project-get-current-config"}]}),
        )

    def test_activate_exposure_uses_tool_names_not_config_text(self) -> None:
        server = {
            "name": "serena",
            "tools": {
                "config": {
                    "name": "serena-project-get-current-config",
                    "description": "Serena may report activate_project inside config text.",
                }
            },
        }
        names = serena_manager.app_server_tool_names(server)
        self.assertFalse(any("activate" in name for name in names))

    def test_empty_project_without_language_needs_choice(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / ".serena").mkdir()
            (root / ".serena/project.yml").write_text("languages: []\n", encoding="utf-8")
            state = serena_manager.language_state(root)
            self.assertEqual("needs_language", state["language_status"])
            self.assertTrue(state["needs_user_language_choice"])
            self.assertEqual(
                ["python", "typescript", "javascript", "rust", "go", "bash", "java", "csharp", "cpp"],
                state["recommended_language_examples"],
            )
            self.assertIn("--language LANGUAGE --verify --app-server", state["recommended_command"])
            self.assertEqual("ask_user_for_serena_language_before_create", state["next_action"])

    def test_status_require_workspace_rejects_denied_root(self) -> None:
        with self.assertRaises(ValueError):
            serena_manager.status(Namespace(project_root="/home/dgk", require_workspace=True, language=None))

    def test_empty_uninitialized_status_is_non_mutating_preflight(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = serena_manager.status(Namespace(project_root=str(root), require_workspace=True, language=None))
            after = sorted(path.relative_to(root) for path in root.rglob("*"))
            result = json.loads(stdout.getvalue())
            self.assertEqual(0, code)
            self.assertEqual(before, after)
            self.assertFalse(result["env_present"])
            self.assertTrue(result["needs_user_language_choice"])
            self.assertEqual("needs_language", result["language_status"])
            self.assertIn("--require-workspace", result["recommended_command"])

    def test_related_instances_reports_ancestor_without_selecting_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as workspace_tmp, tempfile.TemporaryDirectory() as repo_tmp:
            original_repo_root = serena_manager.REPO_ROOT
            try:
                serena_manager.REPO_ROOT = Path(repo_tmp)
                instances = serena_manager.REPO_ROOT / "server-instances/serena-parent"
                instances.mkdir(parents=True)
                parent = Path(workspace_tmp).resolve()
                child = parent / "child"
                child.mkdir()
                (instances / "instance.json").write_text(
                    json.dumps(
                        {
                            "canonical_project_root": str(parent),
                            "instance_slug": "serena-parent",
                            "server_name": "serena_parent_server",
                            "unit": "contextforge-serena-parent.service",
                            "port": 9119,
                        }
                    ),
                    encoding="utf-8",
                )
                related = serena_manager.related_serena_instances(child)
                self.assertEqual(1, len(related))
                self.assertEqual("ancestor", related[0]["relation"])
                self.assertEqual(str(parent), related[0]["project_root"])
                self.assertEqual("serena_parent_server", related[0]["server_name"])
            finally:
                serena_manager.REPO_ROOT = original_repo_root

    def test_port_listener_classification_accepts_canonical_manifest_owner(self) -> None:
        project_root = Path("/home/dgk/workspace/cf-controlplane")
        instance_dir = project_root / "server-instances" / "serena-cf-controlplane-d46fe58a2a20"
        detail = {
            "returncode": 0,
            "listeners": [
                {
                    "pid": "123",
                    "cwd": str(project_root),
                    "cmdline": [
                        "serena",
                        "start-mcp-server",
                        "--project",
                        str(project_root),
                        "--port",
                        "9108",
                    ],
                    "env": {"SERENA_HOME": str(instance_dir / "run" / "serena-home")},
                }
            ],
        }

        result = serena_manager.classify_port_listener(detail, project_root, instance_dir)

        self.assertEqual("canonical_manifest_owner", result["classification"])
        self.assertEqual(["123"], result["matching_pids"])

    def test_port_listener_classification_flags_foreign_or_stale_owner(self) -> None:
        project_root = Path("/home/dgk/workspace/cf-controlplane")
        instance_dir = project_root / "server-instances" / "serena-cf-controlplane-d46fe58a2a20"
        other_root = Path("/home/dgk/workspace/retired-project")
        detail = {
            "returncode": 0,
            "listeners": [
                {
                    "pid": "456",
                    "cwd": str(other_root),
                    "cmdline": [
                        "serena",
                        "start-mcp-server",
                        "--project",
                        str(other_root),
                        "--port",
                        "9108",
                    ],
                    "env": {
                        "SERENA_HOME": str(other_root / "server-instances" / "serena-retired" / "run" / "serena-home")
                    },
                }
            ],
        }

        result = serena_manager.classify_port_listener(detail, project_root, instance_dir)

        self.assertEqual("foreign_or_stale_owner", result["classification"])
        self.assertEqual([], result["matching_pids"])
        self.assertEqual(["456"], result["listener_pids"])

    def test_language_inference_prefers_code_over_markdown(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "README.md").write_text("# docs\n", encoding="utf-8")
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            self.assertEqual("python", serena_manager.infer_language(root))

    def test_language_override_writes_project_local_yml(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            changed = serena_manager.write_language_override(root, "python")
            self.assertTrue(changed)
            self.assertEqual(["python"], serena_manager.configured_languages(root))
            self.assertIn("languages:\n  - python\n", (root / ".serena/project.local.yml").read_text(encoding="utf-8"))

    def test_lsp_probe_uses_file_path_for_empty_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            path, created = serena_manager.find_probe_target(root, "python")
            self.assertTrue(created)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertNotEqual(".", str(path.relative_to(root)))
            self.assertTrue(path.name.endswith(".py"))
            path.unlink()

    def test_optional_lsp_method_missing_is_advisory(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "find_implementations",
            {"error": {"code": -32601, "message": "method not found"}},
            baseline=False,
        )
        self.assertTrue(classified["ok"])
        self.assertEqual("unsupported_by_lsp_backend", classified["classification"])
        self.assertEqual("optional_capability_gap", classified["severity"])

    def test_baseline_lsp_method_missing_is_blocking(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "get_symbols_overview",
            {"error": {"code": -32601, "message": "method not found"}},
            baseline=True,
        )
        self.assertFalse(classified["ok"])
        self.assertEqual("baseline_blocking", classified["severity"])

    def test_baseline_lsp_tool_error_text_is_blocking(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "get_symbols_overview",
            {"result": {"content": [{"text": "Error executing tool: Exception - language server manager is not initialized"}]}},
            baseline=True,
        )
        self.assertFalse(classified["ok"])
        self.assertEqual("probe_error", classified["classification"])
        self.assertEqual("baseline_blocking", classified["severity"])

    def test_automatic_lsp_probes_are_read_only(self) -> None:
        suffixes = serena_manager.automatic_lsp_probe_tool_suffixes(include_optional=True)
        self.assertIn("find-implementations", suffixes)
        self.assertFalse(set(suffixes) & set(serena_manager.EDIT_LSP_TOOL_SUFFIXES))

    def test_python_find_implementations_gap_is_optional(self) -> None:
        gap = serena_manager.unsupported_optional_gap("find_implementations", "find-implementations")
        self.assertEqual("optional_capability_gap", gap["severity"])
        self.assertEqual("unsupported_by_lsp_backend", gap["classification"])

    def test_javascript_backend_options_normalize_to_typescript(self) -> None:
        self.assertEqual("typescript", serena_manager.validate_language("javascript"))
        options = serena_manager.lsp_backend_options("javascript")
        self.assertLessEqual(len(options), 3)
        self.assertEqual("typescript", options[0]["backend_id"])
        self.assertEqual("javascript", options[0]["requested_language"])
        self.assertEqual("typescript", options[0]["normalized_language"])

    def test_backend_catalog_returns_user_facing_choices(self) -> None:
        options = serena_manager.lsp_backend_options("python")
        self.assertLessEqual(len(options), 3)
        self.assertTrue(all(option["label"] for option in options))
        self.assertTrue(all(option["recommended_scope"] == "instance" for option in options))
        self.assertFalse(any(option["install_implemented"] for option in options))

    def test_status_output_includes_lsp_advisory_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = serena_manager.status(Namespace(project_root=str(root), require_workspace=True, language=None))
            result = json.loads(stdout.getvalue())
            self.assertEqual(0, code)
            for key in (
                "lsp_capability_status",
                "lsp_gap_severity",
                "optional_capability_gaps",
                "lsp_backend_options",
                "lsp_next_action",
                "lsp_instance_scope",
            ):
                self.assertIn(key, result)

    def test_verify_without_manifest_includes_lsp_advisory_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            result = serena_manager.build_verify_result(
                Namespace(project_root=str(root), require_workspace=True, language=None, app_server=False)
            )
            self.assertFalse(result["ok"])
            self.assertIn("lsp_capability_status", result)
            self.assertIn("lsp_backend_options", result)

    def test_instance_lsp_scaffold_is_local_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance = Path(tmp) / "serena-test"
            scaffold = serena_manager.ensure_lsp_scaffold(instance, "python")
            self.assertTrue((instance / "lsp-tools/bin").is_dir())
            self.assertTrue((instance / "lsp-tools/cache").is_dir())
            self.assertTrue((instance / "lsp-tools/logs").is_dir())
            self.assertTrue((instance / "lsp-tools/solidlsp").is_dir())
            self.assertTrue((instance / "lsp.env").is_file())
            self.assertEqual(str(instance / "lsp-tools"), scaffold["lsp_tools_dir"])
            manifest = json.loads((instance / "lsp-tools/manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["install_command_execution_enabled"])

    def test_lsp_scaffold_rejects_symlink_and_world_writable_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symlink_instance = root / "symlink-instance"
            symlink_instance.symlink_to("/tmp")
            with self.assertRaises(RuntimeError):
                serena_manager.ensure_lsp_scaffold(symlink_instance, "python")

            instance = root / "world-writable-instance"
            (instance / "lsp-tools").mkdir(parents=True)
            (instance / "lsp-tools").chmod(0o777)
            try:
                with self.assertRaises(RuntimeError):
                    serena_manager.ensure_lsp_scaffold(instance, "python")
            finally:
                (instance / "lsp-tools").chmod(0o755)

    def test_manifest_merge_preserves_existing_fields_while_adding_lsp(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            project = Path(tmp).resolve()
            identity = common.project_identity(project)
            with tempfile.TemporaryDirectory() as instance_tmp:
                instance = Path(instance_tmp)
                (instance / "instance.json").write_text(
                    json.dumps(
                        {
                            "contextforge": {"gateway": {"id": "existing"}},
                            "runtime": {"kept": True},
                            "custom_future_field": "preserve-me",
                        }
                    ),
                    encoding="utf-8",
                )
                serena_manager.write_manifest(
                    instance,
                    identity,
                    9111,
                    lsp_metadata={"advisory_status": "instance_scaffold_ready"},
                )
                manifest = json.loads((instance / "instance.json").read_text(encoding="utf-8"))
                self.assertEqual({"gateway": {"id": "existing"}}, manifest["contextforge"])
                self.assertEqual({"kept": True}, manifest["runtime"])
                self.assertEqual("preserve-me", manifest["custom_future_field"])
                self.assertEqual("instance_scaffold_ready", manifest["lsp"]["advisory_status"])

    def test_install_commands_are_not_enabled(self) -> None:
        self.assertFalse(serena_manager.install_command_execution_enabled())
        self.assertFalse(any(option["install_implemented"] for option in serena_manager.lsp_backend_options("rust")))

    def test_prompt_distinguishes_env_defaults_and_preflight_flow(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT
        self.assertIn(".project/context_forge_state.json is the project initialization authority", text)
        self.assertIn("Do not echo this context to the user", text)
        self.assertIn("hidden or structured prompt/context injection", text)
        self.assertIn("User-visible UI should be limited to information that requires user understanding or response", text)
        self.assertIn("On the first user prompt in a session with lifecycle missing / fresh_initialization", text)
        self.assertIn("before answering unrelated work or ordinary tool-list questions", text)
        self.assertIn("Ask exactly one question, then stop and wait", text)
        self.assertIn("Which ContextForge services should I activate for this project?", text)
        self.assertIn("No user-global config/trust/extension changes", text)
        self.assertIn("for Pi this is .project/context_forge_state.json records", text)
        self.assertIn("for OpenCode this is project-local opencode.json plus .opencode/plugins/contextforge-project-init.js", text)
        self.assertIn("input-triggered hidden message", text)
        self.assertIn("experimental.chat.system.transform system context", text)
        self.assertIn("cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only", text)
        self.assertIn("do not reconstruct the full plan object from visible text", text)
        self.assertIn("prefer those cached id/digest tools over reconstructing a full plan object", text)
        self.assertIn("call cf_project_init_apply using the cached plan and receipts", text)
        self.assertIn("status=config_conflict with an embedded recovery_plan", text)
        self.assertIn("call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest", text)
        self.assertIn("call cf_project_init_recovery_apply using the cached recovery plan and receipts", text)
        self.assertIn("Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids", text)
        self.assertIn("complete helper-returned recovery plan object and full receipt objects", text)
        self.assertIn("keep them together in the helper recovery approval/apply path", text)
        self.assertIn("Never choose service selections, approval, reload acknowledgement, validation", text)
        self.assertIn("If the user echoes your question, asks you to provide the selection numbers", text)
        self.assertIn("Do not invoke project-init helper scripts or Python modules through shell", text)
        self.assertIn("helper cache is missing or stale", text)
        self.assertIn("do not silently replace the challenge id", text)
        self.assertIn("first call cf_project_init_record_client_reload", text)
        self.assertIn("honor that choice after recording the reload acknowledgement instead of asking again", text)
        self.assertIn("after the reload or new session, resume project init", text)
        self.assertIn("Codex launches configured MCP servers and exposes their tools when a session starts", text)
        self.assertIn("/mcp is a status view, not an in-place MCP tool reload", text)
        self.assertIn("start a new Codex session from the project root before target-client-visible validation", text)
        self.assertIn("start a new OpenCode session from the project root before target-client-visible validation", text)
        self.assertIn("the Pi agent must issue /reload before validation", text)
        self.assertIn("Choose 1 to validate now", text)
        self.assertIn("Do not call unlisted or unavailable validation tool names", text)
        self.assertIn("validation tool call is missing, not found, unavailable, or returns an error", text)
        self.assertIn("Skipped-service follow-up", text)
        self.assertIn("Do not substitute built-in web search, direct shell commands, direct SSH/tmux", text)
        self.assertIn("service remains skipped/not verified", text)
        self.assertIn("numbered option list", text)
        self.assertIn("status --project-root", text)
        self.assertIn("Serena is one project-scoped option in this menu, not the whole flow", text)
        self.assertIn("target-client-visible and non-destructive", text)

    def test_prompt_registration_help_and_dry_run_do_not_call_gateway(self) -> None:
        original_read_env = prompt_registration.gateway._read_env
        try:
            def fail_read_env(_path: object) -> dict[str, str]:
                raise AssertionError("gateway env should not be read for help or dry-run")

            prompt_registration.gateway._read_env = fail_read_env  # type: ignore[assignment]
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as help_exit:
                    prompt_registration.main(["--help"])
            self.assertEqual(0, help_exit.exception.code)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(0, prompt_registration.main(["--dry-run"]))
            self.assertIn("would_register project_init_prompt", stdout.getvalue())
        finally:
            prompt_registration.gateway._read_env = original_read_env  # type: ignore[assignment]

    def test_prompt_render_verification_supplies_target_client(self) -> None:
        calls: list[dict[str, object] | None] = []

        def fake_api_request(
            method: str,
            path: str,
            token: str,
            payload: dict[str, object] | None = None,
        ) -> dict[str, object]:
            self.assertEqual("POST", method)
            self.assertEqual("/prompts/prompt-id", path)
            self.assertEqual("token", token)
            calls.append(payload)
            text = prompt_registration.PROJECT_INIT_TEXT
            for key, value in (payload or {}).items():
                text = text.replace("{{ " + key + " }}", str(value))
            return {"messages": [{"content": {"text": text}}]}

        with mock.patch.object(prompt_registration, "api_request", side_effect=fake_api_request):
            prompt_registration.verify_prompt_render("token", {"id": "prompt-id"})

        self.assertEqual(1, len(calls))
        self.assertEqual("codex", (calls[0] or {})["target_client"])
        self.assertEqual("/home/dgk/workspace/cf-controlplane", (calls[0] or {})["project_root"])

    def test_serena_guidance_association_replaces_retired_resources(self) -> None:
        requests: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_items(method: str, path: str, token: str, payload: dict[str, object] | None = None) -> list[dict[str, object]]:
            self.assertEqual("GET", method)
            self.assertEqual("token", token)
            if path == "/servers?include_inactive=true&limit=1000":
                return [
                    {
                        "id": "server-id",
                        "name": "serena_cf_controlplane_d46fe58a2a20_server",
                        "associatedToolIds": ["tool-id"],
                        "associatedResourceIds": ["resource-current", "resource-retired"],
                        "associatedPromptIds": ["prompt-current"],
                        "tags": [{"id": "serena", "label": "serena"}],
                    }
                ]
            if path == "/resources?include_inactive=true&limit=1000":
                retired_uri = prompt_registration.retired_registry_uri_prefix() + "/serena-project-instance-guidance/v14"
                return [
                    {"id": "resource-current", "name": "serena_project_instance_guidance_resource_v15", "uri": common.SERENA_GUIDANCE_RESOURCE_URI},
                    {"id": "resource-retired", "name": "serena_project_instance_guidance_resource_v14", "uri": retired_uri},
                ]
            raise AssertionError(f"unexpected path: {path}")

        def fake_request(
            method: str,
            path: str,
            token: str,
            payload: dict[str, object] | None = None,
        ) -> dict[str, object]:
            self.assertEqual("PUT", method)
            self.assertEqual("token", token)
            requests.append((method, path, payload))
            return {"id": "server-id"}

        with (
            mock.patch.object(prompt_registration, "api_items", side_effect=fake_items),
            mock.patch.object(prompt_registration, "api_request", side_effect=fake_request),
        ):
            associated = prompt_registration.associate_serena_guidance(
                "token",
                {"id": "prompt-current"},
                {"id": "resource-current"},
            )

        self.assertEqual(["serena_cf_controlplane_d46fe58a2a20_server"], associated)
        body = requests[0][2] or {}
        self.assertEqual(["resource-current"], body["associatedResources"])
        self.assertEqual(["prompt-current"], body["associatedPrompts"])

    def test_project_init_artifact_uris_track_semantic_prompt_version(self) -> None:
        self.assertTrue(common.PROJECT_INIT_RESOURCE_URI.endswith(f"/{common.PROMPT_VERSION}"))
        self.assertTrue(common.SERENA_GUIDANCE_RESOURCE_URI.endswith(f"/{common.PROMPT_VERSION}"))
        self.assertIn(common.PROMPT_VERSION, common.PROJECT_INIT_RESOURCE_NAME)
        self.assertIn(common.PROMPT_VERSION, common.SERENA_GUIDANCE_RESOURCE_NAME)
        self.assertNotRegex(common.PROJECT_INIT_RESOURCE_URI, r"/v1(?:/|$)")

    def test_hook_rejects_stale_registered_serena_only_prompt(self) -> None:
        stale = (
            "ContextForge project initialization, version v1. "
            "Ask the user whether to enable a project-local Serena backend. "
            "First-run initialization asks only for Serena enablement."
        )
        self.assertFalse(init_hook.prompt_text_is_fresh(stale))

        identity = common.project_identity("/home/dgk/workspace/test-new-proj-03")
        rendered = init_hook.render_local_prompt(init_hook.prompt_args(identity, {}))

        self.assertTrue(init_hook.prompt_text_is_fresh(rendered))
        self.assertIn("Ask exactly one question, then stop and wait", rendered)
        self.assertIn("/home/dgk/workspace/test-new-proj-03", rendered)
        self.assertIn(f"ContextForge project initialization, version {common.PROMPT_VERSION}", rendered)

    def test_fresh_project_startup_guidance_is_client_specific_and_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            pi_result = pi_project_init_helper_cli.dispatch(
                "render_project_init_prompt",
                {"project_root": str(root), "client_type": "pi"},
            )
            opencode_rendered = init_hook.render_local_prompt(
                init_hook.prompt_args(common.project_identity(root), {}, target_client="opencode")
            )
            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

        self.assertEqual(before, after)
        self.assertTrue(pi_result["ok"])
        self.assertEqual("pi", pi_result["client_type"])
        pi_text = str(pi_result["prompt_text"])
        for text, client in ((pi_text, "pi"), (opencode_rendered, "opencode")):
            with self.subTest(client=client):
                self.assertIn(f"Target client: {client}", text)
                self.assertIn("State: uninitialized", text)
                self.assertIn("Lifecycle: missing / fresh_initialization", text)
                self.assertIn("On the first user prompt in a session with lifecycle missing / fresh_initialization", text)
                self.assertIn("before answering unrelated work or ordinary tool-list questions", text)
                self.assertIn('asking exactly: "Which ContextForge services should I activate for this project?"', text)
                self.assertIn("explain in practical terms", text)
                self.assertIn("planned project-local writes and non-actions", text)
                self.assertIn("require scoped approval before apply", text)
                self.assertIn("avoid writing project state, client config, trust state, registry entries, service state, secrets, or backend state", text)
                self.assertIn("Which ContextForge services should I activate for this project?", text)

    def test_fresh_project_hook_uses_local_prompt_without_gateway_catalog_mutation(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as run_tmp:
            root = Path(tmp).resolve()
            run_root = Path(run_tmp)
            payload = {
                "hook_event_name": "experimental.chat.system.transform",
                "session_id": "opencode-fresh-project",
                "cwd": str(root),
            }
            stdin = io.StringIO(json.dumps(payload))
            stdout = io.StringIO()
            with (
                mock.patch.object(init_hook, "RUN_ROOT", run_root),
                mock.patch.object(init_hook, "STATE_PATH", run_root / "project-init-hook-state.local.json"),
                mock.patch.object(init_hook, "LOCK_PATH", run_root / "project-init-hook-state.local.lock"),
                mock.patch.object(init_hook, "LOG_PATH", run_root / "project-init-hook.local.log"),
                mock.patch.object(init_hook.gateway, "_read_env", side_effect=AssertionError("gateway env must not be read")),
                mock.patch.object(init_hook, "upgrade_project_init_prompt", side_effect=AssertionError("fresh guidance must not upsert prompt catalog")),
                mock.patch.object(sys, "stdin", stdin),
                contextlib.redirect_stdout(stdout),
            ):
                code = init_hook.main_for_events(
                    {"experimental.chat.system.transform"},
                    suppress_output=True,
                    target_client="opencode",
                )

            self.assertEqual(0, code)
            emitted = json.loads(stdout.getvalue())
            self.assertTrue(emitted["suppressOutput"])
            context = emitted["hookSpecificOutput"]["additionalContext"]
            self.assertIn("On the first user prompt in a session with lifecycle missing / fresh_initialization", context)
            self.assertIn("before answering unrelated work or ordinary tool-list questions", context)
            self.assertIn('asking exactly: "Which ContextForge services should I activate for this project?"', context)
            self.assertIn("Target client: opencode", context)
            self.assertIn("State: uninitialized", context)
            self.assertIn("Lifecycle: missing / fresh_initialization", context)
            self.assertIn("require scoped approval before apply", context)
            self.assertIn("avoid writing project state, client config, trust state, registry entries, service state, secrets, or backend state", context)
            self.assertFalse(project_state.project_state_path(root).exists())
            self.assertFalse((root / "opencode.json").exists())
            self.assertFalse((root / ".opencode").exists())

    def test_hook_decision_uses_project_init_lifecycle_inspector(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(init_hook.should_inject(root, {}))

            initialized = project_state.default_state(root, status="initialized")
            project_state.write_state_atomic(root, initialized)
            self.assertFalse(init_hook.should_inject(root, {}))

            disabled = project_state.load_state(root)
            assert disabled is not None
            disabled["status"] = "disabled"
            project_state.write_state_atomic(root, disabled)
            self.assertFalse(init_hook.should_inject(root, {}))

            pending = project_state.load_state(root)
            assert pending is not None
            pending["status"] = "in_progress"
            pending["project_init"]["x_hook_prompt_state"] = "active"
            project_state.write_state_atomic(root, pending)
            self.assertTrue(init_hook.should_inject(root, {}))

            completed_unverified = project_state.load_state(root)
            assert completed_unverified is not None
            completed_unverified["project_init"]["x_hook_prompt_state"] = "completed_unverified"
            project_state.write_state_atomic(root, completed_unverified)
            self.assertFalse(init_hook.should_inject(root, {}))

    def test_hook_suppression_is_target_client_aware(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            self.assertFalse(init_hook.should_inject(root, {}, target_client="codex"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="gemini"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="opencode"))

            gemini_plan = binding.plan_project_init_gemini_config_write(root, [service])
            gemini_state = project_state.apply_project_init_activation_to_state(
                state,
                [service],
                target_client="gemini",
                client_config_plan=gemini_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="validate_now", target_client="gemini"),
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, gemini_state)
            self.assertFalse(init_hook.should_inject(root, {}, target_client="gemini"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="opencode"))

    def test_hook_decision_repairs_invalid_current_shape_without_fresh_init_classification(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="[mcp_servers.context7]\ncommand = \"npx\"\n")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
            raw = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            raw.pop("project_init")
            project_state.project_state_path(root).parent.mkdir(parents=True)
            project_state.project_state_path(root).write_text(json.dumps(raw), encoding="utf-8")

            inspection = init_hook.project_state_inspection(root)
            args = init_hook.prompt_args(common.project_identity(root), {})
            should_inject = init_hook.should_inject(root, {})

        self.assertTrue(should_inject)
        self.assertEqual("invalid_repairable", inspection["lifecycle_status"])
        self.assertEqual("repair_project_init_state", inspection["recommended_action"])
        self.assertEqual("invalid_repairable", args["project_state_lifecycle_status"])
        self.assertEqual("repair_project_init_state", args["project_state_recommended_action"])

    def test_hook_prompt_metadata_requires_current_semantic_version_tag(self) -> None:
        self.assertTrue(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v6",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertTrue(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v6",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": [{"name": common.PROMPT_VERSION}],
                }
            )
        )
        self.assertFalse(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v1",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": ["contextforge", "project-init", "v1"],
                }
            )
        )
        self.assertFalse(init_hook.prompt_record_is_fresh({"name": common.PROJECT_INIT_PROMPT_NAME, "tags": [common.PROMPT_VERSION]}))

    def test_hook_resource_metadata_requires_current_semantic_version_uri_and_tag(self) -> None:
        self.assertTrue(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v6",
                    "uri": common.PROJECT_INIT_RESOURCE_URI,
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertFalse(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v1",
                    "uri": "contextforge://cf-controlplane/project-init/v1",
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertFalse(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v6",
                    "uri": common.PROJECT_INIT_RESOURCE_URI,
                    "tags": ["contextforge", "project-init", "v1"],
                }
            )
        )

    def test_hook_self_upgrade_upserts_project_init_prompt_and_resource(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []
        original_resource = prompt_registration.upsert_resource
        original_prompt = prompt_registration.upsert_prompt
        try:
            def fake_resource(token: str, **kwargs: object) -> dict[str, object]:
                calls.append(("resource", kwargs))
                self.assertEqual("token", token)
                return {"id": "resource-v6"}

            def fake_prompt(token: str, **kwargs: object) -> dict[str, object]:
                calls.append(("prompt", kwargs))
                self.assertEqual("token", token)
                return {"id": "prompt-v6"}

            prompt_registration.upsert_resource = fake_resource  # type: ignore[assignment]
            prompt_registration.upsert_prompt = fake_prompt  # type: ignore[assignment]

            prompt_id = init_hook.upgrade_project_init_prompt("token")
        finally:
            prompt_registration.upsert_resource = original_resource  # type: ignore[assignment]
            prompt_registration.upsert_prompt = original_prompt  # type: ignore[assignment]

        self.assertEqual("prompt-v6", prompt_id)
        self.assertEqual(["resource", "prompt"], [name for name, _kwargs in calls])
        self.assertEqual(common.PROJECT_INIT_RESOURCE_NAME, calls[0][1]["name"])
        self.assertEqual(common.PROJECT_INIT_RESOURCE_URI, calls[0][1]["uri"])
        self.assertEqual(common.PROJECT_INIT_PROMPT_NAME, calls[1][1]["name"])
        self.assertIn(common.PROMPT_VERSION, calls[0][1]["tags"])
        self.assertIn(common.PROMPT_VERSION, calls[1][1]["tags"])
        self.assertIn("version {{ prompt_version }}", str(calls[1][1]["template"]))

    def test_hook_renders_upgraded_prompt_when_registered_prompt_is_stale(self) -> None:
        identity = common.project_identity("/home/dgk/workspace/test-new-proj-03")
        original_request = init_hook.gateway._request
        original_upgrade = init_hook.upgrade_project_init_prompt
        upgrade_calls: list[str] = []
        try:
            def fake_request(method: str, path: str, *, token: str, body: dict[str, str] | None = None) -> dict[str, object]:
                self.assertEqual("POST", method)
                if path == "/prompts/stale":
                    return {"messages": [{"content": {"text": "ContextForge project initialization, version v1. Serena only."}}]}
                if path == "/prompts/upgraded":
                    return {"messages": [{"content": {"text": init_hook.render_local_prompt(body or {})}}]}
                raise AssertionError(f"unexpected path: {path}")

            def fake_upgrade(token: str) -> str:
                upgrade_calls.append(token)
                return "upgraded"

            init_hook.gateway._request = fake_request  # type: ignore[assignment]
            init_hook.upgrade_project_init_prompt = fake_upgrade  # type: ignore[assignment]

            rendered = init_hook.render_prompt("token", "stale", identity, {})
        finally:
            init_hook.gateway._request = original_request  # type: ignore[assignment]
            init_hook.upgrade_project_init_prompt = original_upgrade  # type: ignore[assignment]

        self.assertEqual(["token"], upgrade_calls)
        self.assertTrue(init_hook.prompt_text_is_fresh(rendered))
        self.assertIn(f"ContextForge project initialization, version {common.PROMPT_VERSION}", rendered)


if __name__ == "__main__":
    unittest.main()
