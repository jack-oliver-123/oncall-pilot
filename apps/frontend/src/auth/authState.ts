import { reactive, readonly } from "vue";
import type {
  AuthUser,
  LoginRequest,
  OperationResponses,
  RegisterRequest,
} from "@oncall-pilot/api-contracts";
import { ApiClientError } from "../transport/apiClient";
import type { AuthClient } from "./authClient";

export const AUTH_TOKEN_KEY = "oncall-pilot.auth.token";

interface AuthStateOptions {
  client: AuthClient;
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">;
}

type AuthStatus = "idle" | "loading" | "anonymous" | "authenticated" | "error";

function isUnauthorized(error: unknown) {
  return error instanceof ApiClientError && error.error.httpStatus === 401;
}

export function createAuthState({ client, storage }: AuthStateOptions) {
  const state = reactive<{ status: AuthStatus; user: AuthUser | null }>({
    status: "idle",
    user: null,
  });
  let token = storage.getItem(AUTH_TOKEN_KEY) ?? undefined;
  let version = 0;
  const protectedStores = new Set<() => void>();

  function clearProtected() {
    const errors: unknown[] = [];
    for (const reset of protectedStores) {
      try {
        reset();
      } catch (error) {
        errors.push(error);
      }
    }
    if (errors.length) throw new AggregateError(errors, "部分本地状态清理失败");
  }

  function clearIdentity() {
    version++;
    token = undefined;
    state.user = null;
    state.status = "anonymous";
    try {
      storage.removeItem(AUTH_TOKEN_KEY);
    } finally {
      clearProtected();
    }
  }

  async function initialize() {
    const current = ++version;
    const captured = token;
    state.user = null;
    clearProtected();
    if (!captured) {
      state.status = "anonymous";
      return;
    }
    state.status = "loading";
    try {
      const user = await client.me(captured);
      if (current !== version) return;
      state.user = user;
      state.status = "authenticated";
    } catch (error) {
      if (current !== version) return;
      if (isUnauthorized(error)) {
        clearIdentity();
        return;
      }
      state.status = "error";
      throw error;
    }
  }

  async function login(input: LoginRequest) {
    clearIdentity();
    const current = version;
    state.status = "loading";
    try {
      const result = await client.login(input);
      if (current !== version) return;
      storage.setItem(AUTH_TOKEN_KEY, result.token);
      token = result.token;
      state.user = result.user;
      state.status = "authenticated";
    } catch (error) {
      if (current !== version) return;
      state.status = "anonymous";
      throw error;
    }
  }

  async function logout() {
    const captured = token;
    // 清理失败也必须尝试撤销已捕获的服务端会话。
    try {
      clearIdentity();
    } finally {
      if (captured) await client.logout(captured);
    }
  }

  async function request<K extends keyof OperationResponses>(
    operation: K,
    init: Omit<RequestInit, "method"> = {},
  ): Promise<OperationResponses[K]["data"]> {
    const captured = token;
    const current = version;
    try {
      const result = await client.request(operation, captured, init);
      if (current !== version || captured !== token) {
        throw new DOMException("请求所属身份已失效", "AbortError");
      }
      return result;
    } catch (error) {
      if (isUnauthorized(error) && current === version && captured === token) clearIdentity();
      throw error;
    }
  }

  return {
    state: readonly(state),
    register: (input: RegisterRequest) => client.register(input),
    initialize,
    login,
    logout,
    request,
    registerProtectedStore(reset: () => void) {
      protectedStores.add(reset);
      return () => protectedStores.delete(reset);
    },
  };
}
