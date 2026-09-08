"""无框架依赖的归属上下文；由可信认证边界显式创建和传递。"""

from dataclasses import dataclass


class InvalidOwnerScope(ValueError):
    """调用方遗漏或伪造 scope；错误不携带输入值。"""


def require_scope_id(value: object) -> str:
    """空值、错误类型及首尾空白在任何 I/O 前失败，不静默规范化。"""
    if not isinstance(value, str) or not value or value != value.strip():
        raise InvalidOwnerScope("归属标识必须是非空且无首尾空白的字符串。")
    if any(ord(char) < 32 for char in value):
        raise InvalidOwnerScope("归属标识不能包含控制字符。")
    return value


@dataclass(frozen=True, slots=True)
class OwnerScope:
    owner_user_id: str

    def __post_init__(self) -> None:
        require_scope_id(self.owner_user_id)

    @property
    def tenant_id(self) -> str:
        """本地用户即 tenant；不提供可独立覆盖的 tenant 字段。"""
        return self.owner_user_id

    def require_owner(self, record_owner_user_id: str) -> None:
        if require_scope_id(record_owner_user_id) != self.owner_user_id:
            raise InvalidOwnerScope("记录归属与当前 scope 不一致。")


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """已认证的最小身份；不携带密码或会话凭据。"""

    user_id: str

    def __post_init__(self) -> None:
        require_scope_id(self.user_id)

    @property
    def owner_scope(self) -> OwnerScope:
        return OwnerScope(self.user_id)

    @property
    def tenant_id(self) -> str:
        return self.user_id
