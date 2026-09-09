<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  RadioTower,
  MessageSquare,
  BookOpen,
  Activity,
  Plug,
  LogOut,
  RefreshCw,
  UserRound,
} from "lucide-vue-next";
import { useApplication } from "../context";
import { publicConfig } from "../config";
import AsyncStatusBadge from "../components/AsyncStatusBadge.vue";
const { auth, feedback, publicApi } = useApplication();
const route = useRoute();
const router = useRouter();
const isChat = computed(() => route.name === "chat");
const navigation = [
  { name: "chat", text: "值班对话", icon: MessageSquare },
  { name: "knowledge", text: "知识库", icon: BookOpen },
  { name: "aiops", text: "智能运维", icon: Activity },
  { name: "mcp", text: "工具连接", icon: Plug },
];
const service = ref<"loading" | "success" | "error">("loading");
const serviceText = computed(
  () => ({ loading: "正在检查服务", success: "服务可连接", error: "服务无法连接" })[service.value],
);
let controller: AbortController | undefined;
let timeout: ReturnType<typeof setTimeout> | undefined;
async function checkService() {
  controller?.abort();
  clearTimeout(timeout);
  const current = new AbortController();
  controller = current;
  timeout = setTimeout(() => current.abort(), 8000);
  service.value = "loading";
  try {
    await publicApi.request("getHealth", { signal: current.signal });
    if (controller === current) service.value = "success";
  } catch {
    if (controller === current) service.value = "error";
  } finally {
    if (controller === current) clearTimeout(timeout);
  }
}
onMounted(checkService);
onBeforeUnmount(() => {
  controller?.abort();
  controller = undefined;
  clearTimeout(timeout);
});
async function logout() {
  try {
    await auth.logout();
    feedback.show("success", "已退出登录。");
  } catch {
    feedback.show("error", "已清除本地登录，但未能确认服务端退出。请检查网络。");
  }
  await router.replace({ name: "login" });
}
</script>
<template>
  <div
    v-if="auth.state.status === 'authenticated'"
    class="workspace-layout"
    :class="{ 'with-conversations': isChat }"
  >
    <a class="skip-link" href="#workspace-main">跳到工作区</a>
    <aside class="navigation-rail" aria-label="工作台导航">
      <div class="rail-brand" :aria-label="publicConfig.frontend.title">
        <RadioTower :size="28" aria-hidden="true" /><span>值班台</span>
      </div>
      <nav aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.name" :to="{ name: item.name }"
          ><component :is="item.icon" :size="22" :stroke-width="1.6" aria-hidden="true" /><span>{{
            item.text
          }}</span></RouterLink
        >
      </nav>
      <div class="rail-footer">
        <UserRound :size="21" aria-hidden="true" /><span>个人空间</span>
      </div>
    </aside>
    <aside v-if="isChat" class="conversation-region" aria-label="会话区域">
      <slot name="conversations"
        ><h2>会话</h2>
        <p>会话功能尚未开放</p>
        <span>对话开放后，会话将在这里显示。</span></slot
      >
    </aside>
    <div class="workspace-body">
      <header class="workspace-header">
        <div>
          <p class="workspace-brand" data-testid="brand">{{ publicConfig.frontend.title }}</p>
          <h1>{{ route.meta.title }}</h1>
        </div>
        <div class="workspace-tools">
          <div class="service-health" title="仅检查应用进程是否可连接，不代表所有功能可用">
            <AsyncStatusBadge :status="service" :text="serviceText" /><button
              class="icon-button"
              type="button"
              aria-label="刷新服务状态"
              :disabled="service === 'loading'"
              @click="checkService"
            >
              <RefreshCw :size="15" aria-hidden="true" />
            </button>
          </div>
          <div class="account">
            <span>{{ auth.state.user?.email }}</span
            ><button type="button" class="logout-button" @click="logout">
              <LogOut :size="16" aria-hidden="true" />退出登录
            </button>
          </div>
        </div>
      </header>
      <main id="workspace-main" class="route-canvas" tabindex="-1"><RouterView /></main>
    </div>
  </div>
</template>
