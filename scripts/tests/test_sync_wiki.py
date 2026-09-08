from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.sync_wiki import WikiSyncError, sync_wiki, verify_wiki

REQUIREMENT_BODY = (
    "系统 SHALL 生成 WIKI。\n\n"
    "#### Scenario: 同步\n"
    "- **WHEN** 执行同步\n"
    "- **THEN** 生成页面\n"
)


class WikiSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        (self.root / "docs").mkdir()
        (self.root / "openspec" / "changes" / "archive").mkdir(parents=True)
        (self.root / "openspec" / "specs").mkdir(parents=True)

    def create_change(
        self,
        name: str,
        *,
        archived: bool,
        skip_specs: bool = False,
        include_tasks: bool = True,
        delta_requirement: str | None = None,
    ) -> Path:
        change_root = self.root / "openspec" / "changes"
        change_dir = change_root / "archive" / name if archived else change_root / name
        change_dir.mkdir(parents=True)
        metadata = "schema: spec-driven\ncreated: 2026-08-26\n"
        if skip_specs:
            metadata += "skip_specs: true\n"
        (change_dir / ".openspec.yaml").write_text(metadata, encoding="utf-8")
        (change_dir / "proposal.md").write_text("## Why\n\n测试提案。\n", encoding="utf-8")
        (change_dir / "design.md").write_text("## Context\n\n测试设计。\n", encoding="utf-8")
        if include_tasks:
            (change_dir / "tasks.md").write_text("## 1. 测试\n\n- [x] 1.1 完成\n", encoding="utf-8")
        if delta_requirement:
            capability = "wiki-sync"
            spec_dir = change_dir / "specs" / capability
            spec_dir.mkdir(parents=True)
            (spec_dir / "spec.md").write_text(
                "## Purpose\n\n测试同步行为。\n\n"
                "## ADDED Requirements\n\n"
                f"### Requirement: {delta_requirement}\n\n{REQUIREMENT_BODY}",
                encoding="utf-8",
            )
        return change_dir

    def create_main_spec(self, requirement: str) -> None:
        spec_dir = self.root / "openspec" / "specs" / "wiki-sync"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "# wiki-sync Specification\n\n"
            "## Purpose\n\n测试。\n\n"
            "## Requirements\n\n"
            f"### Requirement: {requirement}\n\n{REQUIREMENT_BODY}",
            encoding="utf-8",
        )

    def managed_files(self) -> dict[str, str]:
        return {
            path.relative_to(self.root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted((self.root / "docs").rglob("*"))
            if path.is_file()
        }

    def test_projects_active_and_skip_specs_archive_without_symlink(self) -> None:
        self.create_change("active-change", archived=False, skip_specs=True)
        archive_name = "2026-08-26-docs-change"
        self.create_change(archive_name, archived=True, skip_specs=True)

        result = sync_wiki(self.root, "all")

        self.assertEqual((result.active_count, result.archive_count), (1, 1))
        self.assertFalse((self.root / "docs" / "openspec").exists())
        active_page = self.root / "docs" / "changes" / "active" / "active-change" / "index.md"
        archive_page = self.root / "docs" / "changes" / "archive" / archive_name / "index.md"
        self.assertIn("../../../../openspec/changes/active-change/proposal.md", active_page.read_text(encoding="utf-8"))
        self.assertIn(
            f"../../../../openspec/changes/archive/{archive_name}/proposal.md",
            archive_page.read_text(encoding="utf-8"),
        )
        index = (self.root / "docs" / "changes" / "index.md").read_text(encoding="utf-8")
        config = (self.root / "docs" / ".vitepress" / "config.mts").read_text(encoding="utf-8")
        self.assertIn("/changes/active/active-change/", index)
        self.assertIn(f"/changes/archive/{archive_name}/", index)
        self.assertIn("On-call Pilot WIKI", config)
        verify_wiki(self.root)

    def test_accepts_synchronized_delta_specs(self) -> None:
        archive_name = "2026-08-26-spec-change"
        requirement = "Generate deterministic WIKI"
        self.create_change(
            archive_name,
            archived=True,
            delta_requirement=requirement,
        )
        self.create_main_spec(requirement)

        result = sync_wiki(self.root, "archive", archive_name)

        self.assertEqual(result.archive_count, 1)
        page = self.root / "docs" / "changes" / "archive" / archive_name / "index.md"
        self.assertIn("## 规格变更", page.read_text(encoding="utf-8"))

    def test_same_day_archive_uses_created_date_before_name(self) -> None:
        requirement = "Same-day contract evolution"
        foundation = self.create_change("2026-09-08-z-foundation", archived=True, delta_requirement=requirement)
        contracts = self.create_change("2026-09-08-a-contracts", archived=True, delta_requirement=requirement)
        (foundation / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-28\n", encoding="utf-8")
        (contracts / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-09-08\n", encoding="utf-8")
        delta = contracts / "specs/wiki-sync/spec.md"
        delta.write_text(delta.read_text(encoding="utf-8").replace("ADDED", "MODIFIED").replace("生成 WIKI", "生成新版 WIKI"), encoding="utf-8")
        self.create_main_spec(requirement)
        main = self.root / "openspec/specs/wiki-sync/spec.md"
        main.write_text(main.read_text(encoding="utf-8").replace("生成 WIKI", "生成新版 WIKI"), encoding="utf-8")
        self.assertEqual(sync_wiki(self.root, "all").archive_count, 2)
        verify_wiki(self.root)
        previous = self.managed_files()
        sync_wiki(self.root, "all")
        self.assertEqual(previous, self.managed_files())

    def test_rejects_unsynchronized_delta_before_writing(self) -> None:
        archive_name = "2026-08-26-unsynced-change"
        self.create_change(
            archive_name,
            archived=True,
            delta_requirement="Missing from main spec",
        )

        with self.assertRaisesRegex(WikiSyncError, "未同步 requirement"):
            sync_wiki(self.root, "archive", archive_name)

        self.assertFalse((self.root / "docs" / "changes").exists())

    def test_rejects_missing_required_archive_artifact_before_writing(self) -> None:
        archive_name = "2026-08-26-incomplete-change"
        self.create_change(
            archive_name,
            archived=True,
            skip_specs=True,
            include_tasks=False,
        )

        with self.assertRaisesRegex(WikiSyncError, "缺少必要 artifact tasks.md"):
            sync_wiki(self.root, "archive", archive_name)

        self.assertFalse((self.root / "docs" / "changes").exists())

    def test_repeated_sync_is_idempotent(self) -> None:
        self.create_change(
            "2026-08-26-idempotent-change",
            archived=True,
            skip_specs=True,
        )

        sync_wiki(self.root, "all")
        first = self.managed_files()
        sync_wiki(self.root, "all")

        self.assertEqual(self.managed_files(), first)

    def test_verify_rejects_missing_include_target(self) -> None:
        change = self.create_change(
            "2026-08-26-missing-include",
            archived=True,
            skip_specs=True,
        )
        sync_wiki(self.root, "all")
        (change / "proposal.md").unlink()

        with self.assertRaisesRegex(WikiSyncError, "include 目标不存在"):
            verify_wiki(self.root)

    def test_verify_detects_navigation_divergence(self) -> None:
        self.create_change(
            "2026-08-26-navigation-change",
            archived=True,
            skip_specs=True,
        )
        sync_wiki(self.root, "all")
        config = self.root / "docs" / ".vitepress" / "config.mts"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "/changes/archive/2026-08-26-navigation-change/",
                "/changes/archive/wrong/",
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(WikiSyncError, "期望全文不一致"):
            verify_wiki(self.root)

    def test_verify_uses_openspec_source_not_wiki_frontmatter(self) -> None:
        archive_name = "2026-08-26-oracle-change"
        change = self.create_change(archive_name, archived=True, skip_specs=True)
        sync_wiki(self.root, "all")
        page = self.root / "docs" / "changes" / "archive" / archive_name / "index.md"
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                "createdDate: 2026-08-26",
                "createdDate: 2000-01-01",
            ),
            encoding="utf-8",
        )
        (change / ".openspec.yaml").write_text(
            "schema: spec-driven\ncreated: 2026-08-26\nskip_specs: true\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(WikiSyncError, "页面全文与 OpenSpec 期望不一致"):
            verify_wiki(self.root)

    def test_rejects_delta_spec_without_operations(self) -> None:
        archive_name = "2026-08-26-empty-ops"
        change = self.create_change(archive_name, archived=True)
        spec_dir = change / "specs" / "wiki-sync"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text("## Purpose\n\n无 operation。\n", encoding="utf-8")

        with self.assertRaisesRegex(WikiSyncError, "缺少可识别 operation"):
            sync_wiki(self.root, "archive", archive_name)
        self.assertFalse((self.root / "docs" / "changes").exists())

    def test_rejects_empty_added_section(self) -> None:
        archive_name = "2026-08-26-empty-added"
        change = self.create_change(archive_name, archived=True)
        spec_dir = change / "specs" / "wiki-sync"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "## ADDED Requirements\n\n只有标题没有 requirement。\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(WikiSyncError, "ADDED 段落没有 requirement"):
            sync_wiki(self.root, "archive", archive_name)

    def test_rejects_malformed_renamed_section(self) -> None:
        archive_name = "2026-08-26-bad-rename"
        change = self.create_change(archive_name, archived=True)
        spec_dir = change / "specs" / "wiki-sync"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "## RENAMED Requirements\n\nFROM only, missing TO pair.\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(WikiSyncError, "RENAMED 段落无法解析"):
            sync_wiki(self.root, "archive", archive_name)

    def test_rejects_invalid_sync_arguments(self) -> None:
        with self.assertRaisesRegex(WikiSyncError, "不支持的 mode"):
            sync_wiki(self.root, "nope")
        with self.assertRaisesRegex(WikiSyncError, "all 模式不能指定"):
            sync_wiki(self.root, "all", "x")
        with self.assertRaisesRegex(WikiSyncError, "路径分隔符"):
            sync_wiki(self.root, "active", "../escape")
        with self.assertRaisesRegex(WikiSyncError, "非法 Change 名称"):
            sync_wiki(self.root, "archive", ".")
        self.assertFalse((self.root / "docs" / "changes").exists())


if __name__ == "__main__":
    unittest.main()
