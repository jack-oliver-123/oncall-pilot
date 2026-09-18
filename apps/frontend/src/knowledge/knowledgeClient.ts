import type { DocumentIndexStatus, KnowledgeDocument } from "@oncall-pilot/api-contracts";
import type { createAuthState } from "../auth/authState";

export const indexStatusLabels: Record<DocumentIndexStatus, string> = {
  pending: "等待处理",
  running: "正在索引",
  succeeded: "索引完成",
  failed: "索引失败",
  cancelled: "已取消",
};

export class IndexSubmissionError extends Error {
  constructor(
    public readonly document: KnowledgeDocument,
    public readonly reason: unknown,
  ) {
    super("文档已上传，但索引任务创建失败");
  }
}

export function createKnowledgeClient(auth: ReturnType<typeof createAuthState>) {
  const scope = (kb: string, document: string, task?: string) => ({
    kb,
    document,
    ...(task ? { task } : {}),
  });
  const create = (kb: string, document: string) =>
    auth.request("createDocumentIndexTask", {}, scope(kb, document));
  return {
    create,
    get: (kb: string, document: string, task: string) =>
      auth.request("getDocumentIndexTask", {}, scope(kb, document, task)),
    retry: (kb: string, document: string, task: string) =>
      auth.request("retryDocumentIndexTask", {}, scope(kb, document, task)),
    cancel: (kb: string, document: string, task: string) =>
      auth.request("cancelDocumentIndexTask", {}, scope(kb, document, task)),
    async upload(kb: string, file: File) {
      const form = new FormData();
      form.append("file", file);
      const document = await auth.request("uploadKnowledgeDocument", { body: form }, { kb });
      try {
        const task = await create(kb, document.id);
        return { document, task };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") throw error;
        throw new IndexSubmissionError(document, error);
      }
    },
  };
}
