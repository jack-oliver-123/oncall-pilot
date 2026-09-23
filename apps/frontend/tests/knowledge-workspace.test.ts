// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { reactive } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { documentUploadPolicy, errorCatalog } from "@oncall-pilot/api-contracts";
import KnowledgeView from "../src/views/KnowledgeView.vue";
import { applicationKey } from "../src/context";
import { createKnowledgeStore } from "../src/stores/knowledge";
import type { KnowledgeClient } from "../src/knowledge/knowledgeClient";
import { ApiClientError } from "../src/transport/apiClient";
import { createKnowledgeClient } from "../src/knowledge/knowledgeClient";
import { createAuthClient } from "../src/auth/authClient";
import { createAuthState } from "../src/auth/authState";
import { readFileSync } from "node:fs";

const user = { id: "user-1", email: "duty@example.com", createdAt: "2026-09-21T00:00:00Z" };
const document = {
  id: "doc-1",
  ownerUserId: user.id,
  knowledgeBaseId: "kb-1",
  filename: "runbook.md",
  size: 12,
  mimeType: "text/markdown",
  sha256: "a".repeat(64),
  uploadedAt: "2026-09-21T00:00:00Z",
  indexStatus: "pending" as const,
  chunkingConfig: { strategy: "paragraph" as const },
};
const task = (status: "pending" | "succeeded" | "failed" | "cancelled" = "pending") => ({
  id: "task-1",
  ownerUserId: user.id,
  knowledgeBaseId: "kb-1",
  documentId: document.id,
  status,
  failureReason: status === "failed" ? "索引服务暂时不可用" : null,
  retryOfTaskId: null,
  createdAt: document.uploadedAt,
  updatedAt: document.uploadedAt,
  startedAt: null,
  completedAt: null,
  cancelRequestedAt: null,
});
const base = { id: "kb-1", ownerUserId: user.id, createdAt: document.uploadedAt };
const job = {
  id: "job-1",
  ownerUserId: user.id,
  kind: "document_index",
  resourceType: "document_index_task",
  resourceId: "task-1",
  leaseOwner: null,
  retryOfJobId: null,
  errorMessage: null,
  status: "queued" as const,
  payload: { knowledgeBaseId: "kb-1", documentId: document.id },
  attempt: 0,
  maxAttempts: 3,
  timeoutSeconds: 60,
  availableAt: document.uploadedAt,
  createdAt: document.uploadedAt,
  updatedAt: document.uploadedAt,
  leaseExpiresAt: null,
  cancelRequestedAt: null,
  startedAt: null,
  completedAt: null,
};

function fakeAuth() {
  const identity = reactive({ user, status: "authenticated" });
  return {
    state: identity,
    registerProtectedStore: vi.fn(() => () => undefined),
  } as unknown as ReturnType<typeof createAuthState>;
}
function fakeClient(overrides: Partial<KnowledgeClient> = {}) {
  return {
    listKnowledgeBases: vi.fn(async () => [base]),
    listDocuments: vi.fn(async () => [document]),
    listBackgroundJobs: vi.fn(async () => [job]),
    getDocument: vi.fn(async () => document),
    preview: vi.fn(async () => [
      { index: 0, excerpt: "分段内容", metadata: { strategy: "paragraph" } },
    ]),
    deleteDocument: vi.fn(async () => document),
    uploadDocument: vi.fn(async () => document),
    createIndexTask: vi.fn(async () => task()),
    getIndexTask: vi.fn(async () => task()),
    retryIndexTask: vi.fn(async () => task()),
    cancelIndexTask: vi.fn(async () => job),
    retryBackgroundJob: vi.fn(async () => job),
    upload: vi.fn(async () => ({ document, task: task() })),
    ...overrides,
  } as unknown as KnowledgeClient;
}
function makeStore(client: KnowledgeClient = fakeClient()) {
  const auth = fakeAuth();
  const pinia = createPinia();
  const store = createKnowledgeStore(auth, client)(pinia);
  return { auth, store };
}

afterEach(() => vi.useRealTimers());

describe("knowledge client 与 store", () => {
  it("上传 multipart 发送 bearer、request id、envelope 和策略边界", async () => {
    const requests: { input: RequestInfo | URL; init?: RequestInit }[] = [];
    const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push(init ? { input, init } : { input });
      const path = new URL(String(input)).pathname;
      const data = path.endsWith("/documents") ? document : task();
      return new Response(JSON.stringify({ ok: true, data, meta: { requestId: "request-1" } }), {
        headers: { "Content-Type": "application/json" },
      });
    });
    const auth = createAuthState({
      client: createAuthClient({
        baseUrl: "https://example.test",
        fetch,
        getRequestId: () => "request-1",
      }),
      storage: { getItem: () => "token-1", setItem: () => undefined, removeItem: () => undefined },
    });
    const client = createKnowledgeClient(auth);
    await client.upload("kb-1", new File(["hello"], "runbook.md", { type: "text/markdown" }), {
      strategy: "fixed-character",
      maxCharacters: 100,
      overlap: 10,
    });
    const form = requests[0]!.init!.body as FormData;
    const headers = new Headers(requests[0]!.init!.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-1");
    expect(headers.get("X-Request-ID")).toBe("request-1");
    expect(Object.fromEntries(form.entries())).toMatchObject({
      overwrite: "false",
      chunkingConfig: JSON.stringify({
        strategy: "fixed-character",
        maxCharacters: 100,
        overlap: 10,
      }),
    });
    expect(form.get("file")).toBeInstanceOf(Blob);
    expect(
      await import("../src/knowledge/knowledgeClient").then(({ serializeChunkingConfig }) =>
        serializeChunkingConfig({ strategy: "markdown-heading" }),
      ),
    ).toBe('{"strategy":"markdown-heading"}');
  });

  it("冲突要求明确覆盖，删除后重新读取服务器列表，刷新可恢复任务", async () => {
    const conflict = new ApiClientError(errorCatalog.BUSINESS_CONFLICT, "r");
    const client = fakeClient({ upload: vi.fn().mockRejectedValue(conflict) });
    const { store } = makeStore(client);
    await store.start();
    expect(store.tasksByDocumentId[document.id]?.id).toBe("task-1");
    await store.upload(new File(["x"], "runbook.md", { type: "text/markdown" }), {
      strategy: "paragraph",
    });
    expect(store.overwriteCandidate?.file.name).toBe("runbook.md");
    expect(store.uploadError).toContain("覆盖");
    store.requestDelete(document);
    await store.confirmDelete();
    expect(client.deleteDocument).toHaveBeenCalledWith("kb-1", "doc-1");
    expect(client.listDocuments).toHaveBeenCalledTimes(2);
  });

  it("约 2 秒轮询活动任务并在终态停止，reset 清理 owner 数据", async () => {
    vi.useFakeTimers();
    const latest = task("succeeded");
    const getIndexTask = vi.fn().mockResolvedValueOnce(task()).mockResolvedValue(latest);
    const client = fakeClient({ getIndexTask });
    const { store } = makeStore(client);
    await store.start();
    expect(client.getIndexTask).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(2000);
    await flushPromises();
    expect(client.getIndexTask).toHaveBeenCalledTimes(2);
    expect(store.tasksByDocumentId[document.id]!.status).toBe("succeeded");
    store.reset();
    expect(store.documents).toEqual([]);
    expect(store.tasksByDocumentId).toEqual({});
    expect(store.overwriteCandidate).toBeNull();
  });

  it("旧用户请求返回时不能回写新身份", async () => {
    let resolve!: (value: (typeof base)[]) => void;
    const client = fakeClient({
      listKnowledgeBases: vi.fn<KnowledgeClient["listKnowledgeBases"]>(
        () =>
          new Promise((done) => {
            resolve = done;
          }),
      ),
    });
    const { store } = makeStore(client);
    const loading = store.load();
    store.reset();
    resolve([base]);
    await loading;
    expect(store.knowledgeBases).toEqual([]);
    expect(store.documents).toEqual([]);
  });
});

describe("knowledge workspace view", () => {
  it("展示上传策略、行内详情、chunk preview 和删除确认", async () => {
    const client = fakeClient();
    const { store } = makeStore(client);
    const feedback = { show: vi.fn() };
    const wrapper = mount(KnowledgeView, {
      global: { provide: { [applicationKey as symbol]: { knowledge: store, feedback } } },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("上传文档");
    expect(wrapper.find('input[type="number"]').exists()).toBe(true);
    await wrapper.get("select").setValue("paragraph");
    expect(wrapper.find('input[type="number"]').exists()).toBe(false);
    await wrapper.get('button[aria-label="展开详情"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("分段内容");
    expect(wrapper.find(".preview-scroll").exists()).toBe(true);
    await wrapper.get('button[aria-label="删除文档"]').trigger("click");
    expect(wrapper.get('[role="alertdialog"]').text()).toContain("确认删除");
    wrapper.unmount();
  });

  it("policy 和布局约束具有中文提示、边界滚动和 reduced motion", () => {
    const css = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
    expect(css).toContain(".document-list");
    expect(css).toContain("max-height: min(58dvh, 680px)");
    expect(css).toContain("overflow-y: auto");
    expect(css).toContain("overflow-x: auto");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(documentUploadPolicy.extensions).toEqual([".md", ".pdf"]);
  });
});
import { resolve } from "node:path";
