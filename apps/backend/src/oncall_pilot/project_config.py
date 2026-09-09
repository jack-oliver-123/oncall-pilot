"""加载并合并 On-call Pilot 本地 JSON 配置。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeAlias, cast

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ProjectConfigError(ValueError):
    """表示本地项目配置无法安全加载。"""


def _read_json_object(path: Path, *, required: bool) -> JsonObject:
    error: str | None = None
    raw: object = None
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        if not required:
            return {}
        error = "必需配置文件不存在"
    except (json.JSONDecodeError, UnicodeError):
        error = "配置文件不是有效 UTF-8 JSON"
    except OSError:
        error = "无法读取配置文件"

    if error is not None:
        # 在 except 之外抛出，不保留可能携带凭据的底层异常链。
        raise ProjectConfigError(f"{path.name}: {error}")

    if not isinstance(raw, dict):
        raise ProjectConfigError(f"{path.name}: 配置文件根节点必须是 JSON object")

    return cast(JsonObject, raw)


def _deep_merge(project: JsonObject, user: JsonObject) -> JsonObject:
    merged = dict(project)
    for key, user_value in user.items():
        project_value = merged.get(key)
        if isinstance(project_value, dict) and isinstance(user_value, dict):
            merged[key] = _deep_merge(project_value, user_value)
        else:
            merged[key] = user_value
    return merged


def load_project_config(config_dir: Path) -> JsonObject:
    """读取 project.json，并用 user.project.json 递归覆盖。"""

    resolved_dir = config_dir.resolve()
    project = _read_json_object(resolved_dir / "project.json", required=True)
    user = _read_json_object(resolved_dir / "user.project.json", required=False)
    merged = _deep_merge(project, user)
    if "llm" in merged:
        from oncall_pilot.llm.config import validate_llm_config

        validate_llm_config(dict(merged))
    return merged
