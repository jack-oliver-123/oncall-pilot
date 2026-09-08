"""新 Repository 可复用的参数失败合同；调用方另断言未发生数据库 I/O。"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from oncall_pilot.memory.scope import InvalidOwnerScope


async def assert_owner_parameter_contract(
    operation: Callable[..., Awaitable[Any]], **arguments: Any
) -> None:
    parameter = inspect.signature(operation).parameters["owner_user_id"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        await operation(**arguments)
    invalid_values: list[Any] = [None, "", " ", "\t", " padded", 0, False, [], {}]
    for invalid in invalid_values:
        with pytest.raises(InvalidOwnerScope):
            await operation(**arguments, owner_user_id=invalid)
