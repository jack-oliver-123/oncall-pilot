"""手动运行三类最小探测；不会在 import 时加载配置或请求远端。"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from oncall_pilot.llm.config import load_provider_settings
from oncall_pilot.llm.factory import create_qwen_provider
from oncall_pilot.llm.provider import ProviderError
from oncall_pilot.project_config import ProjectConfigError


async def probe(config_dir: Path) -> int:
    settings = load_provider_settings(config_dir)
    ready = True
    async with create_qwen_provider(settings) as provider:
        for capability in ("chat", "embedding", "rerank"):
            result = await provider.readiness(capability)
            print(json.dumps(asdict(result), ensure_ascii=False))
            ready = ready and result.ready
    return 0 if ready else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="手动检查模型服务可用性（产生真实请求）")
    parser.add_argument("--config-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        return asyncio.run(probe(args.config_dir))
    except (ProjectConfigError, ProviderError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
