import { defineStore } from "pinia";
import { onScopeDispose, ref } from "vue";
import type { createAuthState } from "../auth/authState";

// 只记录当前工作区选择；后续业务 store 自行提供真实领域合同并登记清理。
export function createProtectedDataStore(auth: ReturnType<typeof createAuthState>) {
  return defineStore("protectedData", () => {
    const activeResourceId = ref<string | null>(null);
    function reset() {
      activeResourceId.value = null;
    }
    onScopeDispose(auth.registerProtectedStore(reset));
    return { activeResourceId, reset };
  });
}
