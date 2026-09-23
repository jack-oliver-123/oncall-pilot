import { defineStore } from "pinia";
import { computed, onScopeDispose, ref } from "vue";
import type {
  BackgroundJob,
  ChunkPreview,
  DocumentIndexTask,
  KnowledgeBase,
  KnowledgeDocument,
} from "@oncall-pilot/api-contracts";
import type { createAuthState } from "../auth/authState";
import {
  createKnowledgeClient,
  IndexSubmissionError,
  type KnowledgeClient,
  type UploadConfig,
} from "../knowledge/knowledgeClient";
import { ApiClientError } from "../transport/apiClient";

const ACTIVE_STATUSES = new Set<DocumentIndexTask["status"]>(["pending", "running"]);
type StoreStatus = "idle" | "loading" | "ready" | "error";

export function createKnowledgeStore(
  auth: ReturnType<typeof createAuthState>,
  client: KnowledgeClient = createKnowledgeClient(auth),
) {
  return defineStore("knowledge", () => {
    const knowledgeBases = ref<KnowledgeBase[]>([]);
    const documents = ref<KnowledgeDocument[]>([]);
    const selectedDocumentId = ref<string | null>(null);
    const selectedDetail = ref<KnowledgeDocument | null>(null);
    const previewByDocumentId = ref<Record<string, ChunkPreview[]>>({});
    const tasksByDocumentId = ref<Record<string, DocumentIndexTask>>({});
    const status = ref<StoreStatus>("idle");
    const error = ref<string | null>(null);
    const detailError = ref<string | null>(null);
    const uploadStatus = ref<"idle" | "uploading" | "indexing" | "success" | "error">("idle");
    const uploadError = ref<string | null>(null);
    const overwriteCandidate = ref<{ file: File; config: UploadConfig } | null>(null);
    const deleteCandidate = ref<KnowledgeDocument | null>(null);
    const selectedKnowledgeBaseId = computed(() => knowledgeBases.value[0]?.id ?? null);
    let generation = 0;
    let selectionGeneration = 0;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let polling = false;
    let watching = false;

    function currentRequest() {
      const requestGeneration = generation;
      const userId = auth.state.user?.id;
      return () => requestGeneration === generation && userId === auth.state.user?.id;
    }

    function errorMessage(cause: unknown, fallback: string) {
      if (cause instanceof ApiClientError) return cause.error.message;
      return cause instanceof Error && cause.message ? cause.message : fallback;
    }

    function activeTasks() {
      return Object.values(tasksByDocumentId.value).filter((task) =>
        ACTIVE_STATUSES.has(task.status),
      );
    }

    function clearPoll() {
      if (pollTimer !== undefined) clearInterval(pollTimer);
      pollTimer = undefined;
    }

    function syncPolling() {
      if (!activeTasks().length) {
        clearPoll();
        if (uploadStatus.value === "indexing") uploadStatus.value = "success";
        return;
      }
      if (watching && pollTimer === undefined) pollTimer = setInterval(() => void pollOnce(), 2000);
    }

    function stopPolling() {
      watching = false;
      clearPoll();
    }

    function reset() {
      generation += 1;
      selectionGeneration += 1;
      stopPolling();
      knowledgeBases.value = [];
      documents.value = [];
      selectedDocumentId.value = null;
      selectedDetail.value = null;
      previewByDocumentId.value = {};
      tasksByDocumentId.value = {};
      status.value = "idle";
      error.value = null;
      detailError.value = null;
      uploadStatus.value = "idle";
      uploadError.value = null;
      overwriteCandidate.value = null;
      deleteCandidate.value = null;
    }

    async function load() {
      const isCurrent = currentRequest();
      status.value = "loading";
      error.value = null;
      try {
        const bases = await client.listKnowledgeBases();
        if (!isCurrent()) return;
        const base = bases[0];
        const [rows, jobs] = base
          ? await Promise.all([client.listDocuments(base.id), client.listBackgroundJobs()])
          : ([[], []] as [KnowledgeDocument[], BackgroundJob[]]);
        if (!isCurrent()) return;
        knowledgeBases.value = bases;
        documents.value = rows;
        if (base) {
          const latestByDocument = new Map<string, BackgroundJob>();
          for (const job of jobs) {
            const payload = job.payload;
            if (
              job.resourceType !== "document_index_task" ||
              !job.resourceId ||
              typeof payload !== "object" ||
              payload === null ||
              Array.isArray(payload)
            )
              continue;
            const value = payload as Record<string, unknown>;
            const documentId = value.documentId;
            if (
              typeof documentId !== "string" ||
              value.knowledgeBaseId !== base.id ||
              !rows.some((row) => row.id === documentId)
            )
              continue;
            const previous = latestByDocument.get(documentId);
            if (!previous || job.createdAt > previous.createdAt)
              latestByDocument.set(documentId, job);
          }
          const recovered = await Promise.all(
            [...latestByDocument].map(([documentId, job]) =>
              client.getIndexTask(base.id, documentId, job.resourceId!),
            ),
          );
          if (!isCurrent()) return;
          tasksByDocumentId.value = Object.fromEntries(
            recovered.map((task) => [task.documentId, task]),
          );
        } else tasksByDocumentId.value = {};
        status.value = "ready";
        syncPolling();
      } catch (cause) {
        if (!isCurrent()) return;
        status.value = "error";
        error.value = errorMessage(cause, "无法读取知识库，请重试。");
      }
    }

    async function start() {
      watching = true;
      await load();
    }

    async function refreshDocument(documentId: string, isCurrent: () => boolean) {
      const kb = selectedKnowledgeBaseId.value;
      if (!kb) return;
      const detail = await client.getDocument(kb, documentId);
      if (!isCurrent()) return;
      const index = documents.value.findIndex((item) => item.id === documentId);
      if (index >= 0) documents.value[index] = detail;
      if (selectedDocumentId.value === documentId) selectedDetail.value = detail;
    }

    async function selectDocument(documentId: string) {
      if (selectedDocumentId.value === documentId) {
        selectedDocumentId.value = null;
        selectedDetail.value = null;
        detailError.value = null;
        return;
      }
      const kb = selectedKnowledgeBaseId.value;
      if (!kb) return;
      const isCurrent = currentRequest();
      const selection = ++selectionGeneration;
      selectedDocumentId.value = documentId;
      selectedDetail.value = null;
      detailError.value = null;
      try {
        const [detail, preview] = await Promise.all([
          client.getDocument(kb, documentId),
          client.preview(kb, documentId),
        ]);
        if (!isCurrent() || selection !== selectionGeneration) return;
        selectedDetail.value = detail;
        previewByDocumentId.value[documentId] = preview;
      } catch (cause) {
        if (isCurrent() && selection === selectionGeneration)
          detailError.value = errorMessage(cause, "无法读取文档详情，请重试。");
      }
    }

    async function pollOnce() {
      if (polling || !watching) return;
      const kb = selectedKnowledgeBaseId.value;
      const isCurrent = currentRequest();
      if (!kb || !activeTasks().length) {
        clearPoll();
        return;
      }
      polling = true;
      try {
        await Promise.all(
          activeTasks().map(async (task) => {
            const latest = await client.getIndexTask(kb, task.documentId, task.id);
            if (!isCurrent() || tasksByDocumentId.value[task.documentId]?.id !== task.id) return;
            tasksByDocumentId.value[task.documentId] = latest;
            await refreshDocument(task.documentId, isCurrent);
          }),
        );
      } catch (cause) {
        if (isCurrent()) error.value = errorMessage(cause, "暂时无法更新索引状态，将自动重试。");
      } finally {
        polling = false;
        if (isCurrent()) syncPolling();
      }
    }

    async function upload(file: File, config: UploadConfig, overwrite = false) {
      const kb = selectedKnowledgeBaseId.value;
      if (!kb) {
        uploadError.value = "当前没有可用的知识库。";
        return;
      }
      const isCurrent = currentRequest();
      uploadStatus.value = "uploading";
      uploadError.value = null;
      overwriteCandidate.value = null;
      try {
        const result = await client.upload(kb, file, config, overwrite);
        if (!isCurrent()) return;
        uploadStatus.value = "indexing";
        tasksByDocumentId.value[result.document.id] = result.task;
        await load();
        if (isCurrent()) syncPolling();
        return result.document;
      } catch (cause) {
        if (!isCurrent()) return;
        uploadStatus.value = "error";
        if (cause instanceof ApiClientError && cause.error.code === "BUSINESS_CONFLICT") {
          overwriteCandidate.value = { file, config: { ...config } };
          uploadError.value = "已有相同内容的文档，请确认后覆盖。";
        } else if (cause instanceof IndexSubmissionError) {
          uploadError.value = "文档已上传，但索引任务创建失败，请在详情中重新建立索引。";
          await load();
        } else uploadError.value = errorMessage(cause, "上传失败，请检查文件后重试。");
      }
    }

    async function confirmOverwrite() {
      const candidate = overwriteCandidate.value;
      if (candidate) await upload(candidate.file, candidate.config, true);
    }

    function requestDelete(document: KnowledgeDocument) {
      deleteCandidate.value = document;
    }

    async function confirmDelete() {
      const document = deleteCandidate.value;
      const kb = selectedKnowledgeBaseId.value;
      if (!document || !kb) return;
      const isCurrent = currentRequest();
      try {
        await client.deleteDocument(kb, document.id);
        if (!isCurrent()) return;
        deleteCandidate.value = null;
        delete tasksByDocumentId.value[document.id];
        delete previewByDocumentId.value[document.id];
        if (selectedDocumentId.value === document.id) {
          selectedDocumentId.value = null;
          selectedDetail.value = null;
          selectionGeneration += 1;
        }
        await load();
      } catch (cause) {
        if (isCurrent()) error.value = errorMessage(cause, "删除失败，请重试。");
      }
    }

    async function retry(documentId: string) {
      const kb = selectedKnowledgeBaseId.value;
      const task = tasksByDocumentId.value[documentId];
      if (!kb) return;
      const isCurrent = currentRequest();
      try {
        const next = task
          ? await client.retryIndexTask(kb, documentId, task.id)
          : await client.createIndexTask(kb, documentId);
        if (!isCurrent()) return;
        tasksByDocumentId.value[documentId] = next;
        uploadStatus.value = "indexing";
        syncPolling();
      } catch (cause) {
        if (isCurrent()) error.value = errorMessage(cause, "无法重新建立索引，请重试。");
      }
    }

    async function cancel(documentId: string) {
      const task = tasksByDocumentId.value[documentId];
      const kb = selectedKnowledgeBaseId.value;
      if (!task || !kb) return;
      const isCurrent = currentRequest();
      try {
        await client.cancelIndexTask(kb, documentId, task.id);
        if (!isCurrent()) return;
        const latest = await client.getIndexTask(kb, documentId, task.id);
        if (!isCurrent()) return;
        tasksByDocumentId.value[documentId] = latest;
        await refreshDocument(documentId, isCurrent);
        syncPolling();
      } catch (cause) {
        if (isCurrent()) error.value = errorMessage(cause, "无法取消索引任务，请重试。");
      }
    }

    const unregister = auth.registerProtectedStore(reset);
    onScopeDispose(unregister);
    onScopeDispose(() => {
      generation += 1;
      clearPoll();
    });

    return {
      knowledgeBases,
      documents,
      selectedKnowledgeBaseId,
      selectedDocumentId,
      selectedDetail,
      previewByDocumentId,
      tasksByDocumentId,
      status,
      error,
      detailError,
      uploadStatus,
      uploadError,
      overwriteCandidate,
      deleteCandidate,
      start,
      stopPolling,
      load,
      selectDocument,
      upload,
      confirmOverwrite,
      requestDelete,
      confirmDelete,
      retry,
      cancel,
      reset,
      pollOnce,
    };
  });
}
