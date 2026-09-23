<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { FilePlus2, RefreshCw, Trash2, RotateCcw, Square, ChevronDown } from "lucide-vue-next";
import { documentUploadPolicy, type KnowledgeDocument } from "@oncall-pilot/api-contracts";
import { useApplication } from "../context";
import { indexStatusLabels, validateUpload, type UploadConfig } from "../knowledge/knowledgeClient";
import AppEmptyState from "../components/AppEmptyState.vue";
import AppErrorState from "../components/AppErrorState.vue";
import AppLoadingState from "../components/AppLoadingState.vue";
import AsyncStatusBadge from "../components/AsyncStatusBadge.vue";

const { knowledge, feedback } = useApplication();
const fileInput = ref<HTMLInputElement>();
const strategy = ref<UploadConfig["strategy"]>("fixed-character");
const maxCharacters = ref(documentUploadPolicy.defaultMaxCharacters);
const overlap = ref(documentUploadPolicy.defaultOverlap);
const localFileError = ref<string | null>(null);
const uploading = computed(() => knowledge.uploadStatus === "uploading");
const selectedConfig = computed<UploadConfig>(() =>
  strategy.value === "fixed-character"
    ? { strategy: strategy.value, maxCharacters: maxCharacters.value, overlap: overlap.value }
    : { strategy: strategy.value },
);
const activeTaskCount = computed(
  () =>
    Object.values(knowledge.tasksByDocumentId).filter((task) =>
      ["pending", "running"].includes(task.status),
    ).length,
);
const uploadStateText = computed(
  () =>
    ({
      idle: "等待选择文件",
      uploading: "正在上传",
      indexing: "已上传，正在索引",
      error: "上传失败",
      success: "索引任务已完成",
    })[knowledge.uploadStatus],
);

onMounted(() => void knowledge.start());
onUnmounted(() => knowledge.stopPolling());
function chooseFile() {
  fileInput.value?.click();
}
function policyMessage(file: File) {
  return validateUpload(file);
}
async function submit() {
  const file = fileInput.value?.files?.[0];
  localFileError.value = file ? policyMessage(file) : "请选择一个 .md 或 .pdf 文件。";
  if (!file || localFileError.value) return;
  if (
    strategy.value === "fixed-character" &&
    (maxCharacters.value <= 0 || overlap.value < 0 || overlap.value >= maxCharacters.value)
  ) {
    localFileError.value = "长度必须为正数，overlap 必须小于长度。";
    return;
  }
  await knowledge.upload(file, selectedConfig.value);
  if (!knowledge.uploadError) {
    feedback.show("success", "文档已上传，索引任务已创建。");
    if (fileInput.value) fileInput.value.value = "";
  }
}
async function confirmOverwrite() {
  await knowledge.confirmOverwrite();
  if (!knowledge.uploadError) feedback.show("success", "文档已覆盖，索引任务已创建。");
}
function statusText(document: KnowledgeDocument) {
  return indexStatusLabels[
    knowledge.tasksByDocumentId[document.id]?.status ?? document.indexStatus
  ];
}
function taskFor(document: KnowledgeDocument) {
  return knowledge.tasksByDocumentId[document.id];
}
function previewFor(document: KnowledgeDocument) {
  return knowledge.previewByDocumentId[document.id] ?? [];
}
async function retry(document: KnowledgeDocument) {
  await knowledge.retry(document.id);
}
async function cancel(document: KnowledgeDocument) {
  await knowledge.cancel(document.id);
}
</script>
<template>
  <section class="knowledge-workspace" aria-labelledby="knowledge-heading">
    <div class="knowledge-intro">
      <div>
        <p class="eyebrow">资料管理</p>
        <h2 id="knowledge-heading">知识库工作区</h2>
        <p>上传值班资料，选择切分方式，并跟踪索引结果。</p>
      </div>
      <div class="knowledge-summary" aria-label="知识库摘要">
        <strong>{{ knowledge.documents.length }}</strong
        ><span>份文档</span>
        <span v-if="activeTaskCount" class="active-count">{{ activeTaskCount }} 项正在处理</span>
      </div>
    </div>

    <form class="knowledge-upload" aria-labelledby="upload-heading" @submit.prevent="submit">
      <div class="section-heading">
        <div>
          <h3 id="upload-heading">上传文档</h3>
          <p>仅支持 Markdown 和 PDF，单文件不超过 10 MiB。</p>
        </div>
        <FilePlus2 :size="22" aria-hidden="true" />
      </div>
      <div class="upload-controls">
        <div class="file-picker">
          <input
            ref="fileInput"
            type="file"
            accept=".md,.pdf,text/markdown,application/pdf"
            aria-label="选择 Markdown 或 PDF 文档"
            @change="
              localFileError = fileInput?.files?.[0] ? policyMessage(fileInput.files[0]) : null
            "
          /><button type="button" class="secondary-button" @click="chooseFile">选择文件</button
          ><span>{{ fileInput?.files?.[0]?.name ?? "尚未选择文件" }}</span>
        </div>
        <label
          >切分策略<select v-model="strategy">
            <option value="fixed-character">固定字符</option>
            <option value="markdown-heading">Markdown 标题</option>
            <option value="paragraph">段落</option>
          </select></label
        >
        <label v-if="strategy === 'fixed-character'"
          >长度<input v-model.number="maxCharacters" type="number" min="1" /><span
            class="field-hint"
            >默认 {{ documentUploadPolicy.defaultMaxCharacters }} 字</span
          ></label
        >
        <label v-if="strategy === 'fixed-character'"
          >overlap<input v-model.number="overlap" type="number" min="0" /><span class="field-hint"
            >默认 {{ documentUploadPolicy.defaultOverlap }} 字</span
          ></label
        >
        <button class="primary-button" type="submit" :disabled="uploading">
          <RefreshCw v-if="uploading" class="spin" :size="16" aria-hidden="true" />{{
            uploading ? "上传中" : "开始上传"
          }}
        </button>
      </div>
      <p class="policy-hint">
        Markdown 文件需要 UTF-8 编码；服务器会再次校验文件类型、实际大小和切分参数。
      </p>
      <p v-if="localFileError || knowledge.uploadError" class="inline-error" role="alert">
        {{ localFileError || knowledge.uploadError }}
      </p>
      <div
        v-if="knowledge.overwriteCandidate"
        class="confirmation"
        role="alertdialog"
        aria-label="确认覆盖文档"
      >
        <strong>发现相同内容的文档</strong><span>确认覆盖后，旧文档会被替换并重新建立索引。</span>
        <div>
          <button type="button" class="primary-button" @click="confirmOverwrite">确认覆盖</button
          ><button
            type="button"
            class="secondary-button"
            @click="knowledge.overwriteCandidate = null"
          >
            取消
          </button>
        </div>
      </div>
      <AsyncStatusBadge
        :status="
          knowledge.uploadStatus === 'error'
            ? 'error'
            : knowledge.uploadStatus === 'uploading'
              ? 'loading'
              : knowledge.uploadStatus === 'indexing'
                ? 'loading'
                : 'idle'
        "
        :text="uploadStateText ?? '等待选择文件'"
      />
    </form>

    <div class="document-section">
      <div class="section-heading">
        <div>
          <h3>文档列表</h3>
          <p>详情默认折叠，展开后可查看服务端实际切分结果。</p>
        </div>
        <span v-if="knowledge.knowledgeBases.length === 1" class="base-label">默认知识库</span>
      </div>
      <AppLoadingState v-if="knowledge.status === 'loading'" text="正在读取知识库文档…" />
      <AppErrorState
        v-else-if="knowledge.status === 'error'"
        :message="knowledge.error ?? '无法读取知识库。'"
        retry
        @retry="knowledge.load"
      />
      <AppEmptyState
        v-else-if="knowledge.status === 'ready' && !knowledge.documents.length"
        title="暂无文档"
        description="选择一个 Markdown 或 PDF 文件开始建立知识资料。"
      />
      <div v-else class="document-list" aria-label="知识文档列表">
        <article v-for="document in knowledge.documents" :key="document.id" class="document-item">
          <div class="document-row">
            <div class="document-name">
              <FilePlus2 :size="18" aria-hidden="true" /><strong>{{ document.filename }}</strong
              ><span>{{ Math.ceil(document.size / 1024) }} KB</span>
            </div>
            <AsyncStatusBadge
              :status="
                taskFor(document)?.status === 'failed'
                  ? 'error'
                  : taskFor(document)?.status === 'succeeded' ||
                      document.indexStatus === 'succeeded'
                    ? 'success'
                    : taskFor(document)
                      ? 'loading'
                      : 'idle'
              "
              :text="statusText(document)"
            />
            <div class="document-actions">
              <button
                type="button"
                class="icon-button"
                :aria-expanded="knowledge.selectedDocumentId === document.id"
                :aria-label="knowledge.selectedDocumentId === document.id ? '收起详情' : '展开详情'"
                @click="knowledge.selectDocument(document.id)"
              >
                <ChevronDown
                  :size="18"
                  :class="{ rotated: knowledge.selectedDocumentId === document.id }"
                  aria-hidden="true"
                /></button
              ><button
                type="button"
                class="icon-button danger-button"
                aria-label="删除文档"
                @click="knowledge.requestDelete(document)"
              >
                <Trash2 :size="17" aria-hidden="true" />
              </button>
            </div>
          </div>
          <div v-if="knowledge.selectedDocumentId === document.id" class="document-detail">
            <div class="metadata-scroll">
              <dl>
                <div>
                  <dt>文件类型</dt>
                  <dd>{{ document.mimeType }}</dd>
                </div>
                <div>
                  <dt>SHA-256</dt>
                  <dd>{{ document.sha256 }}</dd>
                </div>
                <div>
                  <dt>上传时间</dt>
                  <dd>{{ document.uploadedAt }}</dd>
                </div>
                <div>
                  <dt>切分策略</dt>
                  <dd>{{ document.chunkingConfig.strategy }}</dd>
                </div>
              </dl>
            </div>
            <div v-if="taskFor(document)?.status === 'failed'" class="inline-error" role="alert">
              索引失败：{{ taskFor(document)?.failureReason || "服务端未提供更多原因。" }}
            </div>
            <div class="preview-panel">
              <h4>切分预览</h4>
              <div v-if="!knowledge.selectedDetail" class="preview-loading" role="status">
                {{ knowledge.detailError ?? "正在读取文档详情和切分预览…" }}
              </div>
              <ol v-else class="preview-scroll">
                <li v-for="chunk in previewFor(document)" :key="chunk.index">
                  <span>第 {{ chunk.index + 1 }} 段</span>
                  <p>{{ chunk.excerpt }}</p>
                  <code>{{ JSON.stringify(chunk.metadata) }}</code>
                </li>
              </ol>
            </div>
            <div class="detail-actions">
              <button
                v-if="
                  taskFor(document) &&
                  ['failed', 'cancelled', 'succeeded'].includes(taskFor(document)!.status)
                "
                type="button"
                class="secondary-button"
                @click="retry(document)"
              >
                <RotateCcw :size="15" aria-hidden="true" />重新建立索引</button
              ><button
                v-if="
                  taskFor(document) && ['pending', 'running'].includes(taskFor(document)!.status)
                "
                type="button"
                class="secondary-button"
                @click="cancel(document)"
              >
                <Square :size="14" aria-hidden="true" />取消索引
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>
    <div
      v-if="knowledge.deleteCandidate"
      class="confirmation destructive-confirm"
      role="alertdialog"
      aria-label="确认删除文档"
    >
      <strong>确认删除“{{ knowledge.deleteCandidate.filename }}”吗？</strong
      ><span>删除后会清理对应索引，且无法在此页面恢复。</span>
      <div>
        <button
          type="button"
          class="danger-button button-with-text"
          @click="knowledge.confirmDelete"
        >
          确认删除</button
        ><button type="button" class="secondary-button" @click="knowledge.deleteCandidate = null">
          取消
        </button>
      </div>
    </div>
  </section>
</template>
