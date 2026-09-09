import {
  parseContract,
  type LoginRequest,
  type OperationResponses,
  type RegisterRequest,
} from "@oncall-pilot/api-contracts";
import { createApiClient, type TransportOptions } from "../transport/apiClient";
import { createSseClient } from "../transport/sseClient";

export function createAuthClient(options: Omit<TransportOptions, "getBearer">) {
  const publicApi = createApiClient(options);
  function request<K extends keyof OperationResponses>(
    operation: K,
    token: string | undefined,
    init: Omit<RequestInit, "method"> = {},
  ) {
    // 捕获发起时 token，使迟到响应只影响它所属的认证状态。
    return createApiClient({ ...options, getBearer: () => token }).request(operation, init);
  }

  return {
    register(input: RegisterRequest) {
      return publicApi.request("registerUser", {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parseContract("RegisterRequest", input)),
      });
    },
    login(input: LoginRequest) {
      return publicApi.request("loginUser", {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parseContract("LoginRequest", input)),
      });
    },
    me(token: string) {
      return request("getCurrentUser", token);
    },
    logout(token: string) {
      return request("logoutUser", token);
    },
    request,
    stream(path: string, token: string | undefined, init: RequestInit = {}) {
      return createSseClient({ ...options, getBearer: () => token }).stream(path, init);
    },
  };
}

export type AuthClient = ReturnType<typeof createAuthClient>;
