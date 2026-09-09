"""显式手动探测模型；无 import 副作用，不输出配置或响应正文。"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.contracts import ModelKind, ProviderError
from oncall_pilot.llm.qwen import open_qwen_provider
from oncall_pilot.project_config import ProjectConfigError


async def run_smoke(config_dir: Path) -> int:
    try:
        config = load_llm_config(config_dir)
        async with open_qwen_provider(config) as provider:
            ready = True
            kinds: tuple[ModelKind, ...] = ("chat", "embedding", "rerank")
            for kind in kinds:
                result = await provider.readiness(kind)
                print(json.dumps({"kind": kind, **asdict(result)}, ensure_ascii=False))
                ready = ready and result.ready
        return 0 if ready else 1
    except (ProjectConfigError, ProviderError) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="手动检查 Qwen 三类模型的连通性")
    parser.add_argument("--config-dir", required=True, type=Path, help="本地 JSON 配置目录")
    args = parser.parse_args()
    return asyncio.run(run_smoke(args.config_dir))


if __name__ == "__main__":
    raise SystemExit(main())
