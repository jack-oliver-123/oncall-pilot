import { describe, expect, it } from "vitest";
import document from "../openapi/foundation.openapi.json";
import { documentUploadPolicy, operations, parseContract } from "../src/index";

const dto = {
  id: "doc", ownerUserId: "owner", knowledgeBaseId: "kb", filename: "中文.md",
  size: 10, mimeType: "text/markdown", sha256: "a".repeat(64),
  uploadedAt: "2026-09-11T00:00:00Z", indexStatus: "pending",
  chunkingConfig: { strategy: "fixed-character", maxCharacters: 1200, overlap: 200 },
};

describe("知识文档合同", () => {
  it("登记 owner-scoped 操作、上传 policy 与 multipart 字段", () => {
    expect(operations.listKnowledgeBases.path).toBe("/knowledge-bases");
    expect(operations.uploadKnowledgeDocument.method).toBe("POST");
    expect(operations.deleteKnowledgeDocument.method).toBe("DELETE");
    expect(operations.previewKnowledgeDocumentChunks.path).toBe(
      "/knowledge-bases/{kb}/documents/{document}/chunk-preview",
    );
    expect(documentUploadPolicy).toMatchObject({
      maxBytes: 10485760, extensions: [".md", ".pdf"],
      defaultMaxCharacters: 1200, defaultOverlap: 200,
      maxPreviewChunks: 12, maxExcerptCharacters: 400,
    });
    const upload = document.paths["/knowledge-bases/{kb}/documents"].post;
    expect(Object.keys(upload.requestBody.content["multipart/form-data"].schema.properties))
      .toEqual(["file", "overwrite", "chunkingConfig"]);
    expect(upload.security).toEqual([{ BearerAuth: [] }]);
    expect(upload.responses["401"].$ref).toContain("Unauthenticated");
    expect(upload.responses["403"].$ref).toContain("Forbidden");
    expect(upload.responses["409"].content["application/json"].schema.$ref).toContain("ApiFailure");
  });

  it("返回实际配置与完整元数据，拒绝正文及不合法值", () => {
    expect(parseContract("KnowledgeDocument", dto)).toEqual(dto);
    for (const strategy of ["markdown-heading", "paragraph"]) {
      expect(parseContract("KnowledgeDocument", { ...dto, chunkingConfig: { strategy } })
        .chunkingConfig.strategy).toBe(strategy);
    }
    for (const invalid of [
      { ...dto, body: "secret" }, { ...dto, size: 0 }, { ...dto, size: 10485761 },
      { ...dto, filename: "a".repeat(256) }, { ...dto, sha256: "bad" },
      { ...dto, chunkingConfig: { strategy: "paragraph", overlap: 0 } },
      { ...dto, chunkingConfig: { strategy: "fixed-character", maxCharacters: 0, overlap: 0 } },
      { ...dto, chunkingConfig: { strategy: "fixed-character", maxCharacters: 1, overlap: -1 } },
    ]) expect(() => parseContract("KnowledgeDocument", invalid)).toThrow();
  });

  it("预览在跨语言 runtime 中按字符与数量受限", () => {
    const chunk = { index: 0, excerpt: "中".repeat(400), metadata: { strategy: "paragraph" } };
    const response = { ok: true, data: Array(12).fill(chunk), meta: { requestId: "test" } };
    expect(parseContract("ChunkPreviewResponse", response)).toEqual(response);
    expect(() => parseContract("ChunkPreview", { ...chunk, excerpt: "中".repeat(401) })).toThrow();
    expect(() => parseContract("ChunkPreviewResponse", { ...response, data: Array(13).fill(chunk) })).toThrow();
    expect(parseContract("ChunkPreview", { ...chunk, excerpt: "\u{1F600}".repeat(400) }).excerpt)
      .toHaveLength(800);
  });
});
