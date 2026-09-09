import { createApp, watch } from "vue";
import { createPinia, defineStore, disposePinia } from "pinia";
import { createWebHistory, type RouterHistory } from "vue-router";
import App from "./App.vue";
import { createAuthClient } from "./auth/authClient";
import { createAuthState } from "./auth/authState";
import { applicationKey } from "./context";
import { createWorkspaceRouter, safeRedirect } from "./router";
import { createProtectedDataStore } from "./stores/protectedData";
import { useFeedbackStore } from "./stores/feedback";
import { createApiClient, type TransportOptions } from "./transport/apiClient";

export function createApplication(
  options: Pick<TransportOptions, "baseUrl" | "fetch"> & {
    storage: Pick<Storage, "getItem" | "setItem" | "removeItem">;
    history?: RouterHistory;
  },
) {
  const pinia = createPinia();
  const app = createApp(App);
  app.use(pinia);
  const auth = defineStore("auth", () =>
    createAuthState({ client: createAuthClient(options), storage: options.storage }),
  )(pinia);
  const protectedData = createProtectedDataStore(auth)(pinia);
  const feedback = useFeedbackStore(pinia);
  const unregisterFeedback = auth.registerProtectedStore(feedback.clear);
  const router = createWorkspaceRouter(options.history ?? createWebHistory(), auth);
  const stop = watch(
    () => auth.state.status,
    (status) => {
      if (status === "authenticated" && router.currentRoute.value.meta.publicOnly)
        void router.replace(safeRedirect(router, router.currentRoute.value.query.redirect));
      if (status === "anonymous" && router.currentRoute.value.meta.requiresAuth)
        void router.replace({
          name: "login",
          query: { redirect: router.currentRoute.value.fullPath },
        });
    },
  );
  const publicApi = createApiClient(options);
  function dispose() {
    stop();
    unregisterFeedback();
    disposePinia(pinia);
  }
  app.onUnmount(dispose);
  const application = { app, pinia, auth, protectedData, feedback, router, publicApi, dispose };
  app.provide(applicationKey, application);
  return application;
}
