from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RepositoryFoundationTests(unittest.TestCase):
    def test_repository_uses_final_top_level_layout(self) -> None:
        expected = {
            "apps/backend",
            "apps/frontend",
            "packages/api-contracts",
            "config",
            "infra",
            "scripts",
            "openspec",
            "docs",
        }

        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_dir())

        for legacy_root in (ROOT / "backend", ROOT / "frontend"):
            with self.subTest(path=legacy_root):
                self.assertEqual(list(legacy_root.rglob("*")), [])

    def test_root_manifest_exposes_required_workspaces_and_scripts(self) -> None:
        manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "oncall-pilot")
        self.assertEqual(manifest["packageManager"], "npm@10.9.7")
        self.assertEqual(
            set(manifest["workspaces"]),
            {"apps/frontend", "packages/api-contracts"},
        )
        required_scripts = {
            "backend:dev",
            "backend:lint",
            "backend:typecheck",
            "backend:test",
            "frontend:dev",
            "frontend:lint",
            "frontend:format:check",
            "frontend:typecheck",
            "frontend:test",
            "frontend:build",
            "contracts:typecheck",
            "contracts:test",
            "wiki:test",
            "openspec:validate",
            "docs:build",
            "check",
        }
        self.assertLessEqual(required_scripts, set(manifest["scripts"]))

    def test_internal_workspace_dependency_is_one_way(self) -> None:
        frontend = json.loads(
            (ROOT / "apps/frontend/package.json").read_text(encoding="utf-8")
        )
        contracts = json.loads(
            (ROOT / "packages/api-contracts/package.json").read_text(encoding="utf-8")
        )

        self.assertEqual(frontend["name"], "@oncall-pilot/frontend")
        self.assertEqual(frontend["dependencies"]["@oncall-pilot/api-contracts"], "~0.1.0")
        self.assertEqual(contracts["name"], "@oncall-pilot/api-contracts")
        self.assertNotIn("dependencies", contracts)

    def test_product_sources_do_not_use_legacy_or_cross_app_imports(self) -> None:
        source_roots = [ROOT / "apps/backend/src", ROOT / "apps/frontend/src"]
        forbidden = ("super_ai", "src.oncall_pilot", "apps/backend", "apps/frontend")

        for source_root in source_roots:
            if not source_root.exists():
                continue
            for path in source_root.rglob("*"):
                if not path.is_file() or path.suffix not in {".py", ".ts", ".vue"}:
                    continue
                content = path.read_text(encoding="utf-8")
                for value in forbidden:
                    with self.subTest(path=path, value=value):
                        self.assertNotIn(value, content)

    def test_local_and_generated_files_are_ignored(self) -> None:
        ignored_paths = (
            "config/project.json",
            "config/user.project.json",
            ".env",
            ".env.local",
            ".idea/workspace.xml",
            ".venv/pyvenv.cfg",
            "node_modules/example/index.js",
            "apps/frontend/dist/index.js",
            "coverage/lcov.info",
            ".pytest_cache/state",
            ".ruff_cache/state",
            "docs/.vitepress/cache/state",
            "docs/.vitepress/dist/index.html",
            "apps/backend/var/oncall-pilot.db",
            "local.sqlite3",
            "oncall-pilot.log",
        )

        for relative_path in ignored_paths:
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "--quiet", relative_path],
                cwd=ROOT,
                check=False,
            )
            with self.subTest(path=relative_path):
                self.assertEqual(result.returncode, 0)

    def test_tracked_config_templates_are_safe_and_include_model_boundaries(self) -> None:
        project = json.loads(
            (ROOT / "config/project.template.json").read_text(encoding="utf-8")
        )
        user = json.loads(
            (ROOT / "config/user.project.template.json").read_text(encoding="utf-8")
        )

        self.assertEqual(project["frontend"]["title"], "On-call Pilot")
        self.assertEqual(project["frontend"]["apiBaseUrl"], "http://127.0.0.1:8000")
        self.assertEqual(project["frontend"]["analytics"]["publicKey"], "")
        self.assertEqual(
            project["database"]["url"],
            "sqlite+aiosqlite:///apps/backend/var/oncall-pilot.db",
        )
        self.assertTrue({"llm", "modelCapabilities", "mcp", "aiopsDemo"}.issubset(project))
        self.assertEqual(user["llm"]["chat"]["apiKey"], "")

        def assert_credentials_are_empty(value: object) -> None:
            if not isinstance(value, dict):
                return
            for key, child in value.items():
                if any(token in key.casefold() for token in ("key", "secret", "password")):
                    self.assertEqual(child, "")
                assert_credentials_are_empty(child)

        assert_credentials_are_empty(project)
        assert_credentials_are_empty(user)

    def test_agents_is_the_single_project_guide(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

        required_rules = (
            "简体中文",
            "apps/backend",
            "apps/frontend",
            "from oncall_pilot",
            "config/project.json",
            "tenant",
            "真实 MCP",
            "一个滚动容器",
            "feat/",
            "fix/",
            "Conventional Commits",
            "E2E 截图",
        )
        for rule in required_rules:
            with self.subTest(rule=rule):
                self.assertIn(rule, agents)

        self.assertIn("AGENTS.md", claude)
        self.assertNotIn("## 语言与文档", claude)
        self.assertLess(len(claude.splitlines()), 10)

    def test_workspace_readmes_are_chinese_and_describe_only_the_foundation(self) -> None:
        required_documents = {
            "README.md": ("On-call Pilot", "npm run check"),
            "apps/backend/README.md": ("oncall_pilot", "uv run pytest"),
            "apps/frontend/README.md": ("npm run frontend:dev", "桌面 Web"),
            "packages/api-contracts/README.md": ("HealthResponse", "contracts:typecheck"),
            "infra/README.md": ("主机", "Compose"),
        }

        for relative_path, markers in required_documents.items():
            content = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIsNotNone(re.search(r"[\u4e00-\u9fff]", content))
                for marker in markers:
                    self.assertIn(marker, content)
                for false_claim in (
                    "已实现认证",
                    "已实现聊天",
                    "已实现知识库",
                    "已实现 AIOps",
                    "已实现 MCP",
                ):
                    self.assertNotIn(false_claim, content)

    def test_ci_covers_frozen_linux_and_windows_gates(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

        required_markers = (
            "ubuntu-latest",
            "windows-latest",
            'python-version: "3.10"',
            'python-version: "3.12"',
            'node-version: "22"',
            "actions/checkout@v7",
            "actions/setup-node@v7",
            "actions/setup-python@v7",
            "astral-sh/setup-uv@v10.0.1",
            "npm ci",
            "uv lock --check",
            "uv sync --frozen",
            "config/project.template.json",
            "config/project.json",
            "npm run check",
            "git diff --check",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
