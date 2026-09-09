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
  const streams = new Set<AbortController>();

  function cancelStreams() {
    for (const controller of streams) controller.abort();
    streams.clear();
  }

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
    cancelStreams();
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
    cancelStreams();
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
    const current = ++version;
    cancelStreams();
    token = undefined;
    state.user = null;
    state.status = "loading";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      if (captured) await client.request("logoutUser", captured, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
      if (current === version) clearIdentity();
    }
  }

  async function* stream(path: string, init: RequestInit = {}) {
    const captured = token;
    const current = version;
    if (!captured || state.status !== "authenticated")
      throw new DOMException("请求所属身份已失效", "AbortError");
    const controller = new AbortController();
    const abort = () => controller.abort(init.signal?.reason);
    init.signal?.addEventListener("abort", abort, { once: true });
    if (init.signal?.aborted) abort();
    streams.add(controller);
    try {
      for await (const event of client.stream(path, captured, {
        ...init,
        signal: controller.signal,
      })) {
        controller.signal.throwIfAborted();
        if (current !== version || captured !== token)
          throw new DOMException("请求所属身份已失效", "AbortError");
        yield event;
      }
    } catch (error) {
      if (isUnauthorized(error) && current === version && captured === token) clearIdentity();
      throw error;
    } finally {
      init.signal?.removeEventListener("abort", abort);
      controller.abort();
      streams.delete(controller);
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
    stream,
    registerProtectedStore(reset: () => void) {
      protectedStores.add(reset);
      return () => protectedStores.delete(reset);
    },
  };
}
