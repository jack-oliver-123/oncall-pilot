"""无 I/O 的文档切分与预览能力。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import chain
from typing import Literal, cast

from pydantic import JsonValue

Strategy = Literal["fixed-character", "markdown-heading", "paragraph"]
DEFAULT_MAX_CHARACTERS = 1200
DEFAULT_OVERLAP = 200
MAX_PREVIEW_CHUNKS = 12
MAX_EXCERPT_CHARACTERS = 400


class ChunkingError(ValueError):
    """切分策略或参数不合法。"""


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    strategy: Strategy = "fixed-character"
    max_characters: int | None = DEFAULT_MAX_CHARACTERS
    overlap: int | None = DEFAULT_OVERLAP

    def public(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {"strategy": self.strategy}
        if self.strategy == "fixed-character":
            result.update(maxCharacters=self.max_characters, overlap=self.overlap)
        return result


def normalize_chunking_config(value: object = None) -> ChunkingConfig:
    if value is None:
        return ChunkingConfig()
    if not isinstance(value, dict):
        raise ChunkingError("切分配置必须为对象")
    config = cast(dict[str, object], value)
    selected = config.get("strategy", "fixed-character")
    if selected not in ("fixed-character", "markdown-heading", "paragraph"):
        raise ChunkingError("切分策略无效")
    if set(config) - {"strategy", "maxCharacters", "overlap"}:
        raise ChunkingError("切分配置包含未知字段")
    if selected != "fixed-character":
        if set(config) - {"strategy"}:
            raise ChunkingError("仅 fixed-character 支持 maxCharacters 和 overlap")
        return ChunkingConfig(cast(Strategy, selected), None, None)
    maximum = config.get("maxCharacters", DEFAULT_MAX_CHARACTERS)
    overlap = config.get("overlap", DEFAULT_OVERLAP)
    if type(maximum) is not int or maximum <= 0:
        raise ChunkingError("maxCharacters 必须为正整数")
    if type(overlap) is not int or overlap < 0 or overlap >= maximum:
        raise ChunkingError("overlap 必须为非负整数且小于 maxCharacters")
    return ChunkingConfig("fixed-character", maximum, overlap)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    index: int
    text: str
    start: int
    end: int
    strategy: Strategy
    headings: tuple[str, ...] = ()
    document_id: str | None = None
    knowledge_base_id: str | None = None
    owner_user_id: str | None = None

    def metadata(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "start": self.start,
            "end": self.end,
            "strategy": self.strategy,
            "headings": list(self.headings),
        }
        if self.document_id is not None:
            result.update(
                documentId=self.document_id,
                knowledgeBaseId=self.knowledge_base_id,
                ownerUserId=self.owner_user_id,
                tenantId=self.owner_user_id,
            )
        return result


def chunk_document_text(
    text: str, config: ChunkingConfig | None = None, *, limit: int | None = None
) -> list[DocumentChunk]:
    """preview 与未来 indexing 共用的唯一入口；范围使用原正文字符偏移。"""
    selected = normalize_chunking_config(None if config is None else config.public())
    if limit is not None and limit <= 0:
        raise ChunkingError("limit 必须为正整数")
    chunks: list[DocumentChunk] = []

    def append(start: int, end: int, headings: tuple[str, ...] = ()) -> None:
        if start < end:
            chunks.append(
                DocumentChunk(len(chunks), text[start:end], start, end, selected.strategy, headings)
            )

    if selected.strategy == "fixed-character":
        assert selected.max_characters is not None and selected.overlap is not None
        for start in range(0, len(text), selected.max_characters - selected.overlap):
            end = min(start + selected.max_characters, len(text))
            append(start, end)
            if end == len(text) or (limit is not None and len(chunks) >= limit):
                break
    elif selected.strategy == "paragraph":
        start = 0
        for boundary in chain(re.finditer(r"\r?\n[ \t\r]*\n", text), [None]):
            end = len(text) if boundary is None else boundary.start()
            value = text[start:end]
            left = start + len(value) - len(value.lstrip())
            right = start + len(value.rstrip())
            append(left, right)
            if limit is not None and len(chunks) >= limit:
                break
            start = len(text) if boundary is None else boundary.end()
    else:
        # 围栏代码块中的 # 不是标题；标题层级随每个片段保留。
        offset = start = 0
        headings: list[tuple[int, str]] = []
        fence: str | None = None
        for line in text.splitlines(keepends=True):
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if marker:
                token = marker.group(1)
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
            heading = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$", line) if fence is None else None
            if heading:
                append(start, offset, tuple(label for _, label in headings))
                if limit is not None and len(chunks) >= limit:
                    return chunks
                level = len(heading.group(1))
                headings = [(depth, label) for depth, label in headings if depth < level]
                headings.append((level, re.sub(r"[ \t]+#+$", "", heading.group(2))))
                start = offset
            offset += len(line)
        append(start, len(text), tuple(label for _, label in headings))
    return chunks


def preview_chunks(chunks: list[DocumentChunk]) -> list[JsonValue]:
    return [
        {
            "index": chunk.index,
            "excerpt": chunk.text[:MAX_EXCERPT_CHARACTERS],
            "metadata": chunk.metadata(),
        }
        for chunk in chunks[:MAX_PREVIEW_CHUNKS]
    ]
