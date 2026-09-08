"""公共值约定，不持有可变状态或生成 import 时默认值。"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from oncall_pilot.project_config import JsonValue


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("持久化时间必须包含时区")
    return value.astimezone(timezone.utc)


def _validate_json(value: object) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON 数值必须有限")
        return
    if isinstance(value, list):
        for item in cast(list[object], value):
            _validate_json(item)
        return
    if isinstance(value, dict):
        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                raise ValueError("JSON object 的 key 必须是字符串")
            _validate_json(item)
        return
    raise ValueError("仅支持标准 JSON 值")


def serialize_json(value: object) -> str:
    _validate_json(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def deserialize_json(value: str) -> JsonValue:
    result = cast(JsonValue, json.loads(value))
    _validate_json(result)
    return result
