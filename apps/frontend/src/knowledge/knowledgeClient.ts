import {
  documentUploadPolicy,
  type BackgroundJob,
  type ChunkingConfig,
  type ChunkPreview,
  type DocumentIndexTask,
  type KnowledgeDocument,
} from "@oncall-pilot/api-contracts";
import type { createAuthState } from "../auth/authState";

export const indexStatusLabels: Record<KnowledgeDocument["indexStatus"], string> = {
  pending: "等待处理",
  running: "正在索引",
  succeeded: "索引完成",
  failed: "索引失败",
  cancelled: "已取消",
};
export type UploadConfig = ChunkingConfig;
export class UploadPolicyError extends Error {}
export class IndexSubmissionError extends Error {
  constructor(
    public readonly document: KnowledgeDocument,
    public readonly reason: unknown,
  ) {
    super("文档已上传，但索引任务创建失败");
  }
}
export type KnowledgeClient = ReturnType<typeof createKnowledgeClient>;

export function validateUpload(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!documentUploadPolicy.extensions.includes(extension as ".md" | ".pdf"))
    return "只支持上传 .md 或 .pdf 文件。";
  if (file.size > documentUploadPolicy.maxBytes) return "文件不能超过 10 MiB。";
  if (extension === ".pdf" && file.type && file.type !== documentUploadPolicy.pdfMimeType)
    return "PDF 文件的类型不正确，请重新选择。";
  if (
    extension === ".md" &&
    file.type &&
    !documentUploadPolicy.markdownMimeTypes.includes(
      file.type as (typeof documentUploadPolicy.markdownMimeTypes)[number],
    )
  )
    return "Markdown 文件的类型不正确，请重新选择。";
  return null;
}
export function serializeChunkingConfig(config: UploadConfig): string {
  return config.strategy === "fixed-character"
    ? JSON.stringify({
        strategy: config.strategy,
        maxCharacters: config.maxCharacters,
        overlap: config.overlap,
      })
    : JSON.stringify({ strategy: config.strategy });
}

export function createKnowledgeClient(auth: ReturnType<typeof createAuthState>) {
  const scope = (kb: string, document: string, task?: string) => ({
    kb,
    document,
    ...(task ? { task } : {}),
  });
  const createIndexTask = (kb: string, document: string): Promise<DocumentIndexTask> =>
    auth.request("createDocumentIndexTask", {}, scope(kb, document));
  const uploadDocument = async (
    kb: string,
    file: File,
    config: UploadConfig,
    overwrite = false,
  ): Promise<KnowledgeDocument> => {
    const policyError = validateUpload(file);
    if (policyError) throw new UploadPolicyError(policyError);
    const form = new FormData();
    form.append("file", file);
    form.append("overwrite", String(overwrite));
    form.append("chunkingConfig", serializeChunkingConfig(config));
    return auth.request("uploadKnowledgeDocument", { body: form }, { kb });
  };
  return {
    listBackgroundJobs: () => auth.request("listBackgroundJobs"),
    retryBackgroundJob: (id: string) => auth.request("retryBackgroundJob", {}, { id }),
    listKnowledgeBases: () => auth.request("listKnowledgeBases"),
    listDocuments: (kb: string) => auth.request("listKnowledgeDocuments", {}, { kb }),
    getDocument: (kb: string, document: string) =>
      auth.request("getKnowledgeDocument", {}, { kb, document }),
    preview: (kb: string, document: string): Promise<ChunkPreview[]> =>
      auth.request("previewKnowledgeDocumentChunks", {}, { kb, document }),
    deleteDocument: (kb: string, document: string) =>
      auth.request("deleteKnowledgeDocument", {}, { kb, document }),
    uploadDocument,
    createIndexTask,
    getIndexTask: (kb: string, document: string, task: string): Promise<DocumentIndexTask> =>
      auth.request("getDocumentIndexTask", {}, scope(kb, document, task)),
    retryIndexTask: (kb: string, document: string, task: string): Promise<DocumentIndexTask> =>
      auth.request("retryDocumentIndexTask", {}, scope(kb, document, task)),
    async cancelIndexTask(_kb: string, _document: string, task: string): Promise<BackgroundJob> {
      const job = (await auth.request("listBackgroundJobs")).find(
        (item) => item.resourceType === "document_index_task" && item.resourceId === task,
      );
      if (!job) throw new Error("找不到对应的后台任务");
      return auth.request("cancelBackgroundJob", {}, { id: job.id });
    },
    async upload(
      kb: string,
      file: File,
      config: UploadConfig = {
        strategy: "fixed-character",
        maxCharacters: documentUploadPolicy.defaultMaxCharacters,
        overlap: documentUploadPolicy.defaultOverlap,
      },
      overwrite = false,
    ) {
      const document = await uploadDocument(kb, file, config, overwrite);
      try {
        return { document, task: await createIndexTask(kb, document.id) };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") throw error;
        throw new IndexSubmissionError(document, error);
      }
    },
  };
}
