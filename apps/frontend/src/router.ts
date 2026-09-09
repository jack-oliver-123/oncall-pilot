import { createRouter, type Router, type RouterHistory } from "vue-router";
import type { createAuthState } from "./auth/authState";
import AuthView from "./views/AuthView.vue";
import WorkspaceLayout from "./layouts/WorkspaceLayout.vue";
import PlaceholderView from "./views/PlaceholderView.vue";

export function safeRedirect(router: Router, value: unknown): string {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\\\u0000-\u0020]/.test(value)
  )
    return "/chat";
  const resolved = router.resolve(value);
  return resolved.meta.requiresAuth && resolved.name !== "fallback" ? resolved.fullPath : "/chat";
}

export function createWorkspaceRouter(
  history: RouterHistory,
  auth: ReturnType<typeof createAuthState>,
) {
  const router = createRouter({
    history,
    routes: [
      { path: "/login", name: "login", component: AuthView, meta: { publicOnly: true } },
      { path: "/register", name: "register", component: AuthView, meta: { publicOnly: true } },
      {
        path: "/",
        component: WorkspaceLayout,
        meta: { requiresAuth: true },
        children: [
          { path: "", redirect: "/chat" },
          ...[
            {
              path: "chat",
              title: "值班对话",
              description: "对话功能尚未开放。开放后，你可以在这里发起值班对话。",
            },
            {
              path: "knowledge",
              title: "知识库",
              description: "知识库功能尚未开放。开放后，你可以在这里整理值班资料。",
            },
            {
              path: "aiops",
              title: "智能运维",
              description: "智能运维功能尚未开放。开放后，你可以在这里处理运维事项。",
            },
            {
              path: "mcp",
              title: "工具连接",
              description: "工具连接功能尚未开放。开放后，你可以在这里管理可用工具。",
            },
          ].map(({ path, title, description }) => ({
            path,
            name: path,
            component: PlaceholderView,
            meta: { title, description },
          })),
        ],
      },
      { path: "/:pathMatch(.*)*", name: "fallback", redirect: "/chat" },
    ],
  });
  let initialization: Promise<void> | undefined;
  router.beforeEach(async (to) => {
    initialization ??= auth.initialize().catch(() => {
      /* App 显示恢复错误并提供显式重试。 */
    });
    await initialization;
    if (to.meta.requiresAuth && auth.state.status !== "authenticated")
      return { name: "login", query: { redirect: to.fullPath } };
    if (to.meta.publicOnly && auth.state.status === "authenticated") return { name: "chat" };
    return true;
  });
  return router;
}
