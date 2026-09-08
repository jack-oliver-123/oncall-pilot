from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from oncall_pilot.app import create_app
from oncall_pilot.project_config import ProjectConfigError


def write_project_config(config_dir: Path) -> None:
    config_dir.mkdir()
    (config_dir / "project.json").write_text(
        json.dumps({"frontend": {"title": "On-call Pilot"}}),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_health_reports_process_liveness_without_dependency_probes(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    write_project_config(config_dir)
    app = create_app(config_dir)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_factory_fails_before_startup_when_project_config_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProjectConfigError, match="project.json"):
        create_app(tmp_path)
