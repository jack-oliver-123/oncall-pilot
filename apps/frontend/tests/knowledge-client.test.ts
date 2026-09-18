import { describe, expect, it, vi } from "vitest";
import {
  createKnowledgeClient,
  IndexSubmissionError,
  indexStatusLabels,
} from "../src/knowledge/knowledgeClient";
import { createAuthState } from "../src/auth/authState";
import { createAuthClient } from "../src/auth/authClient";

function setup(fail: boolean) {
  const calls: string[] = [];
  const doc = {
    id: "d",
    ownerUserId: "u",
    knowledgeBaseId: "k",
    filename: "a.md",
    size: 1,
    mimeType: "text/markdown",
    sha256: "a".repeat(64),
    uploadedAt: "2026-09-15T00:00:00Z",
    indexStatus: "pending",
    chunkingConfig: { strategy: "paragraph" },
  };
  const task = {
    id: "t",
    ownerUserId: "u",
    knowledgeBaseId: "k",
    documentId: "d",
    status: "pending",
    failureReason: null,
    retryOfTaskId: null,
    createdAt: doc.uploadedAt,
    updatedAt: doc.uploadedAt,
    startedAt: null,
    completedAt: null,
    cancelRequestedAt: null,
  };
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname;
    calls.push(path);
    if (fail && path.endsWith("index-tasks")) throw new Error("network");
    const data = path.endsWith("index-tasks") ? task : doc;
    return new Response(JSON.stringify({ ok: true, data, meta: { requestId: "test" } }), {
      headers: { "Content-Type": "application/json" },
    });
  });
  const auth = createAuthState({
    client: createAuthClient({
      baseUrl: "https://example.test",
      fetch,
      getRequestId: () => "test",
    }),
    storage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  });
  return { client: createKnowledgeClient(auth), calls };
}

describe("上传后显式索引", () => {
  it("先上传成功，再显式创建首次任务", async () => {
    const { client, calls } = setup(false);
    const result = await client.upload("k", new File(["x"], "a.md", { type: "text/markdown" }));
    expect(calls).toEqual([
      "/knowledge-bases/k/documents",
      "/knowledge-bases/k/documents/d/index-tasks",
    ]);
    expect(result.task.status).toBe("pending");
    expect(Object.keys(indexStatusLabels)).toHaveLength(5);
  });
  it("第二步失败保留已上传文档", async () => {
    const { client, calls } = setup(true);
    await expect(client.upload("k", new File(["x"], "a.md"))).rejects.toMatchObject({
      document: { id: "d" },
    });
    expect(calls).toHaveLength(2);
    expect(IndexSubmissionError).toBeDefined();
  });
});
