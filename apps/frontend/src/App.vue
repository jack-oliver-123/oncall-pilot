<script setup lang="ts">
import { useApplication } from "./context";
import { safeRedirect } from "./router";
import AppLoadingState from "./components/AppLoadingState.vue";
import AppErrorState from "./components/AppErrorState.vue";
import AppFeedback from "./components/AppFeedback.vue";
const { auth, router } = useApplication();
async function retry() {
  try {
    await auth.initialize();
    if (auth.state.status === "authenticated")
      await router.replace(safeRedirect(router, router.currentRoute.value.query.redirect));
  } catch {
    /* 保留错误面板，允许再次重试。 */
  }
}
</script>
<template>
  <div class="app-shell">
    <div v-if="auth.state.status === 'error'" class="recovery-state">
      <h1>暂时无法恢复登录</h1>
      <AppErrorState
        message="无法连接服务。你的登录凭据已保留，请检查网络后重试。"
        retry
        @retry="retry"
      />
    </div>
    <div
      v-else-if="
        auth.state.status === 'idle' ||
        (auth.state.status === 'loading' && !router.currentRoute.value.meta.publicOnly)
      "
      class="recovery-state"
    >
      <AppLoadingState text="正在确认登录状态…" />
    </div>
    <RouterView v-else /><AppFeedback />
  </div>
</template>
