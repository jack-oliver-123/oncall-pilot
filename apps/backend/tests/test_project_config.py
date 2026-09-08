from __future__ import annotations

import json
from pathlib import Path

import pytest

from oncall_pilot.project_config import ProjectConfigError, load_project_config


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_user_config_recursively_overrides_project_config(tmp_path: Path) -> None:
    write_json(
        tmp_path / "project.json",
        {
            "frontend": {
                "title": "On-call Pilot",
                "apiBaseUrl": "http://127.0.0.1:8000",
            },
            "flags": {"enabled": True},
        },
    )
    write_json(
        tmp_path / "user.project.json",
        {"frontend": {"title": "我的值班工作台"}},
    )

    assert load_project_config(tmp_path) == {
        "frontend": {
            "title": "我的值班工作台",
            "apiBaseUrl": "http://127.0.0.1:8000",
        },
        "flags": {"enabled": True},
    }


def test_arrays_scalars_and_null_replace_project_values(tmp_path: Path) -> None:
    write_json(
        tmp_path / "project.json",
        {"items": [1, 2], "mode": "project", "nested": {"value": 1}},
    )
    write_json(
        tmp_path / "user.project.json",
        {"items": [3], "mode": 2, "nested": None},
    )

    assert load_project_config(tmp_path) == {
        "items": [3],
        "mode": 2,
        "nested": None,
    }


def test_missing_user_config_is_an_empty_override(tmp_path: Path) -> None:
    project = {"frontend": {"title": "On-call Pilot"}}
    write_json(tmp_path / "project.json", project)

    assert load_project_config(tmp_path) == project


def test_explicit_config_directory_is_independent_of_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    other_dir = tmp_path / "other"
    config_dir.mkdir()
    other_dir.mkdir()
    write_json(config_dir / "project.json", {"source": "explicit"})
    write_json(other_dir / "project.json", {"source": "cwd"})
    monkeypatch.chdir(other_dir)

    assert load_project_config(config_dir) == {"source": "explicit"}


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("project.json", "not-json"),
        ("project.json", "[]"),
        ("user.project.json", "not-json"),
        ("user.project.json", "[]"),
    ],
)
def test_invalid_config_identifies_the_file(
    tmp_path: Path, filename: str, content: str
) -> None:
    write_json(tmp_path / "project.json", {})
    (tmp_path / filename).write_text(content, encoding="utf-8")

    with pytest.raises(ProjectConfigError, match=filename):
        load_project_config(tmp_path)


def test_missing_project_config_identifies_the_required_file(tmp_path: Path) -> None:
    with pytest.raises(ProjectConfigError, match="project.json"):
        load_project_config(tmp_path)
