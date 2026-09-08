# 数据迁移

此目录只包含 Alembic async 运行环境。foundation Change 不创建业务模型或 migration revision。

运行 Alembic 时必须显式传入本地配置目录：

```powershell
uv run alembic -x config-dir=../../config current
```
