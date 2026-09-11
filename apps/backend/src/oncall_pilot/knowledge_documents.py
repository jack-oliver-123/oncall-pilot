"""上传文件的权威校验和正文提取；不写入对象存储。"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import PurePath

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MARKDOWN_MIME_TYPES = frozenset({"text/markdown", "text/plain"})
PDF_MIME_TYPE = "application/pdf"


class DocumentInputError(ValueError):
    """上传文件不符合知识文档 policy。"""


def extract_document(
    filename: str,
    content_type: str | None,
    content: bytes,
) -> tuple[str, int, str, str, str]:
    """返回 (filename, size, mime, sha256, text)，输入只存在于调用方内存。"""
    name = PurePath(filename).name
    suffix = PurePath(name).suffix.casefold()
    if (
        name != filename
        or suffix not in {".md", ".pdf"}
        or len(name) > 255
        or any(ord(char) < 32 for char in name)
        or "\\" in name
        or "/" in name
    ):
        raise DocumentInputError("仅支持 .md 或 .pdf 文件")
    if len(content) == 0 or len(content) > MAX_UPLOAD_BYTES:
        raise DocumentInputError("文件大小必须大于 0 且不超过 10 MiB")
    mime = content_type or ""
    if (suffix == ".md" and mime not in MARKDOWN_MIME_TYPES) or (
        suffix == ".pdf" and mime != PDF_MIME_TYPE
    ):
        raise DocumentInputError("文件 MIME 类型与扩展名不匹配")
    digest = sha256(content).hexdigest()
    if suffix == ".md":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentInputError("Markdown 必须是 UTF-8") from exc
    else:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise DocumentInputError("加密 PDF 不可提取")
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except DocumentInputError:
            raise
        except Exception as exc:
            raise DocumentInputError("PDF 文本提取失败") from exc
    if not text.strip():
        raise DocumentInputError("文档正文不能为空")
    return name, len(content), mime, digest, text
