from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from oncall_pilot.generated_contracts import DOCUMENT_UPLOAD_POLICY
from oncall_pilot.knowledge_chunking import (
    MAX_EXCERPT_CHARACTERS,
    MAX_PREVIEW_CHUNKS,
    ChunkingConfig,
    ChunkingError,
    chunk_document_text,
    normalize_chunking_config,
    preview_chunks,
)
from oncall_pilot.knowledge_documents import (
    MARKDOWN_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    PDF_MIME_TYPE,
    DocumentInputError,
    extract_document,
)


def pdf_bytes(*, encrypted: bool = False, blank: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if not blank:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (On-call PDF content) Tj ET")
        page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("test-only-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_policy_matches_canonical_contract() -> None:
    assert DOCUMENT_UPLOAD_POLICY["maxBytes"] == MAX_UPLOAD_BYTES
    assert set(DOCUMENT_UPLOAD_POLICY["markdownMimeTypes"]) == MARKDOWN_MIME_TYPES
    assert DOCUMENT_UPLOAD_POLICY["pdfMimeType"] == PDF_MIME_TYPE
    assert DOCUMENT_UPLOAD_POLICY["extensions"] == [".md", ".pdf"]
    assert DOCUMENT_UPLOAD_POLICY["maxPreviewChunks"] == MAX_PREVIEW_CHUNKS
    assert DOCUMENT_UPLOAD_POLICY["maxExcerptCharacters"] == MAX_EXCERPT_CHARACTERS
    assert DOCUMENT_UPLOAD_POLICY["defaultMaxCharacters"] == ChunkingConfig().max_characters
    assert DOCUMENT_UPLOAD_POLICY["defaultOverlap"] == ChunkingConfig().overlap


@pytest.mark.parametrize("mime", ["text/markdown", "text/plain"])
def test_markdown_and_size_boundary(mime: str) -> None:
    content = "\ufeff标题\n正文".encode()
    name, size, actual_mime, digest, body = extract_document("notes.MD", mime, content)
    assert (name, size, actual_mime, digest, body) == (
        "notes.MD",
        len(content),
        mime,
        sha256(content).hexdigest(),
        "标题\n正文",
    )
    assert extract_document("a.md", mime, b"a" * MAX_UPLOAD_BYTES)[1] == MAX_UPLOAD_BYTES


@pytest.mark.parametrize(
    "name,mime,content",
    [
        ("a.txt", "text/plain", b"x"),
        ("a.docx", "application/pdf", b"x"),
        ("a.md.exe", "text/markdown", b"x"),
        ("../a.md", "text/markdown", b"x"),
        ("..\\a.md", "text/markdown", b"x"),
        ("a\x00.md", "text/markdown", b"x"),
        ("a" * 253 + ".md", "text/markdown", b"x"),
        ("", "text/plain", b"x"),
        ("a.md", None, b"x"),
        ("a.md", "application/pdf", b"x"),
        ("a.md", "application/octet-stream", b"x"),
        ("a.pdf", "text/plain", b"x"),
        ("a.md", "text/markdown", b""),
        ("a.md", "text/markdown", b" \r\n\t"),
        ("a.md", "text/markdown", b"\xff"),
        ("a.md", "text/markdown", b"\xef\xbb\xbf"),
        ("a.pdf", "application/pdf", b"not a PDF"),
    ],
)
def test_invalid_upload_policy(name: str, mime: str | None, content: bytes) -> None:
    with pytest.raises(DocumentInputError):
        extract_document(name, mime, content)


def test_pdf_real_text_and_rejections() -> None:
    with pytest.raises(DocumentInputError):
        extract_document("a.md", "text/markdown", b"a" * (MAX_UPLOAD_BYTES + 1))
    content = pdf_bytes()
    result = extract_document("manual.PDF", "application/pdf", content)
    assert "On-call PDF content" in result[4]
    assert result[3] == sha256(content).hexdigest()
    for invalid in [pdf_bytes(encrypted=True), pdf_bytes(blank=True), content[:30]]:
        with pytest.raises(DocumentInputError):
            extract_document("a.pdf", "application/pdf", invalid)


@pytest.mark.parametrize(
    "config",
    [
        [],
        "paragraph",
        {"strategy": ""},
        {"strategy": None},
        {"strategy": []},
        {"strategy": "unknown"},
        {"typo": 1},
        {"maxCharacters": 0},
        {"maxCharacters": -1},
        {"maxCharacters": True},
        {"maxCharacters": "1200"},
        {"maxCharacters": 1.2},
        {"maxCharacters": None},
        {"overlap": None},
        {"overlap": False},
        {"overlap": -1},
        {"overlap": 1200},
        {"overlap": "2"},
        {"overlap": 1.2},
        {"strategy": "paragraph", "maxCharacters": 10},
        {"strategy": "markdown-heading", "overlap": 0},
        {"strategy": "paragraph", "overlap": None},
    ],
)
def test_invalid_chunking_config(config: object) -> None:
    with pytest.raises(ChunkingError):
        normalize_chunking_config(config)


def test_fixed_offsets_overlap_defaults_and_preview() -> None:
    assert normalize_chunking_config({}).public() == {
        "strategy": "fixed-character",
        "maxCharacters": 1200,
        "overlap": 200,
    }
    text = "一二三四五六七八九十" * 3000
    chunks = chunk_document_text(text)
    assert chunks[0].end == 1200 and chunks[1].start == 1000
    assert chunks[0].text[-200:] == chunks[1].text[:200]
    assert all(chunk.text == text[chunk.start : chunk.end] for chunk in chunks)
    preview = preview_chunks(chunks)
    assert len(preview) == 12
    assert all(
        isinstance(p, dict) and isinstance(p["excerpt"], str) and len(p["excerpt"]) == 400
        for p in preview
    )
    assert chunk_document_text("") == []
    assert [
        c.text for c in chunk_document_text("abc", ChunkingConfig(max_characters=1, overlap=0))
    ] == ["a", "b", "c"]


def test_heading_hierarchy_preamble_and_fenced_code() -> None:
    text = "序言\n# 一\n正文\n```md\n# 不是标题\n```\n## 二\n段落\n# 三\n结束"
    chunks = chunk_document_text(text, normalize_chunking_config({"strategy": "markdown-heading"}))
    assert [c.headings for c in chunks] == [(), ("一",), ("一", "二"), ("三",)]
    assert "# 不是标题" in chunks[1].text
    assert "".join(c.text for c in chunks) == text
    assert all(c.text == text[c.start : c.end] for c in chunks)


def test_paragraph_offsets_crlf_and_empty() -> None:
    for strategy in ["fixed-character", "markdown-heading", "paragraph"]:
        selected = normalize_chunking_config({"strategy": strategy})
        long_text = "# 标题\n正文\n\n" * 1000
        assert chunk_document_text(long_text, selected, limit=12) == chunk_document_text(
            long_text, selected
        )[:12]
    config = normalize_chunking_config({"strategy": "paragraph"})
    text = " \r\n第一段\r\n连续行\r\n\r\n 第二段\n \n最后一段  "
    chunks = chunk_document_text(text, config)
    assert [c.text for c in chunks] == ["第一段\r\n连续行", "第二段", "最后一段"]
    assert all(c.text == text[c.start : c.end] for c in chunks)
    assert chunk_document_text(" \n\n", config) == []
