// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest";
import { errorCatalog } from "@oncall-pilot/api-contracts";
import { createAuthClient } from "../src/auth/authClient";
import { AUTH_TOKEN_KEY, createAuthState } from "../src/auth/authState";

const user = {
  id: "5b0eab8a-6c94-4b4a-bdb4-653a91271fe1",
  email: "person@example.com",
  createdAt: "2026-09-08T00:00:00Z",
};
const token = "a".repeat(43);
const credentials = { email: user.email, password: "secret-password" };
const success = (data: unknown) =>
  new Response(
    JSON.stringify({
      ok: true,
      data,
      meta: { requestId: "auth-test" },
    }),
    { headers: { "Content-Type": "application/json" } },
  );
const invalid = () =>
  new Response(
    JSON.stringify({
      ok: false,
      error: errorCatalog.AUTH_UNAUTHENTICATED,
      meta: { requestId: "auth-test" },
    }),
    { status: 401, headers: { "Content-Type": "application/json" } },
  );
const loginResponse = (value = token) => success({ user, token: value, tokenType: "Bearer" });
const create = (fetch: typeof globalThis.fetch) =>
  createAuthState({
    client: createAuthClient({ baseUrl: "http://127.0.0.1:8000", fetch }),
    storage: localStorage,
  });

beforeEach(() => localStorage.clear());

describe("authClient 与认证状态", () => {
  it("两个不同用户切换时清理数据并丢弃旧用户迟到响应", async () => {
    const other = {
      ...user,
      id: "ee125a44-639c-4c1f-a5c3-70533b8b75d8",
      email: "other@example.com",
    };
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(loginResponse())
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(success(null))
      .mockResolvedValueOnce(success({ user: other, token: "b".repeat(43), tokenType: "Bearer" }));
    const auth = create(fetch);
    await auth.login(credentials);
    const visible = [user.email];
    auth.registerProtectedStore(() => visible.splice(0));
    const oldRequest = auth.request("getCurrentUser").then((result) => visible.push(result.email));
    const rejected = expect(oldRequest).rejects.toMatchObject({ name: "AbortError" });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    await auth.logout();
    expect(visible).toEqual([]);
    await auth.login({ ...credentials, email: other.email });
    finish(success(user));
    await rejected;
    expect(auth.state.user).toEqual(other);
    expect(visible).toEqual([]);
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
      "http://127.0.0.1:8000/auth/login",
      "http://127.0.0.1:8000/auth/me",
      "http://127.0.0.1:8000/auth/logout",
      "http://127.0.0.1:8000/auth/login",
    ]);
  });

  it("资源 403 保留有效认证，不按资源不存在清理用户身份", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(loginResponse())
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: false,
            error: errorCatalog.AUTH_FORBIDDEN,
            meta: { requestId: "scope-test" },
          }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
      );
    const auth = create(fetch);
    await auth.login(credentials);
    const clear = vi.fn();
    auth.registerProtectedStore(clear);
    await expect(auth.request("getCurrentUser")).rejects.toMatchObject({
      error: { code: "AUTH_FORBIDDEN", httpStatus: 403 },
    });
    expect(auth.state.user).toEqual(user);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe(token);
    expect(clear).not.toHaveBeenCalled();
  });

  it("注册不登录，登录只保存 token，发送合同请求", async () => {
    localStorage.setItem("unrelated-preference", "dark");
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(success(user))
      .mockResolvedValueOnce(loginResponse());
    const auth = create(fetch);
    expect(await auth.register(credentials)).toEqual(user);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(auth.state.user).toBeNull();
    await auth.login(credentials);
    expect(auth.state.user).toEqual(user);
    expect(auth.state.status).toBe("authenticated");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe(token);
    expect(localStorage.length).toBe(2);
    expect(JSON.stringify(localStorage)).not.toContain(credentials.password);
    expect(String(fetch.mock.calls[0]![0])).toBe("http://127.0.0.1:8000/auth/register");
    expect(String(fetch.mock.calls[1]![0])).toBe("http://127.0.0.1:8000/auth/login");
    expect(JSON.parse(fetch.mock.calls[1]![1]!.body as string)).toEqual(credentials);
    expect(new Headers(fetch.mock.calls[1]![1]!.headers).has("Authorization")).toBe(false);
  });
  it("initialize 无 token 不请求，有 token 必须通过 me 验证", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(success(user));
    const auth = create(fetch);
    await auth.initialize();
    expect(fetch).not.toHaveBeenCalled();
    expect(auth.state.status).toBe("anonymous");
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const restored = create(fetch);
    expect(restored.state.user).toBeNull();
    await restored.initialize();
    expect(restored.state.user).toEqual(user);
    expect(String(fetch.mock.calls[0]![0])).toBe("http://127.0.0.1:8000/auth/me");
    expect(new Headers(fetch.mock.calls[0]![1]!.headers).get("Authorization")).toBe(
      `Bearer ${token}`,
    );
  });
  it("401 清除身份和全部受保护 store，保留其他本地配置", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem("preference", "dark");
    const auth = create(vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(invalid()));
    const protectedItems = ["previous-user-item"];
    auth.registerProtectedStore(() => protectedItems.splice(0));
    await auth.initialize();
    expect(auth.state.user).toBeNull();
    expect(auth.state.status).toBe("anonymous");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(protectedItems).toEqual([]);
    expect(localStorage.getItem("preference")).toBe("dark");
  });
  it("恢复网络失败保持 token 可重试，不虚构认证成功", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const auth = create(
      vi.fn<typeof globalThis.fetch>().mockRejectedValueOnce(new TypeError("offline")),
    );
    await expect(auth.initialize()).rejects.toThrow("offline");
    expect(auth.state.user).toBeNull();
    expect(auth.state.status).toBe("error");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe(token);
  });
  it.each([false, true])("登出立即清理本地，服务端失败=%s 时保留失败语义", async (fails) => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(loginResponse());
    if (fails) fetch.mockRejectedValueOnce(new TypeError("offline"));
    else fetch.mockResolvedValueOnce(success(null));
    const auth = create(fetch);
    await auth.login(credentials);
    const clear = vi.fn();
    auth.registerProtectedStore(clear);
    const operation = auth.logout();
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(auth.state.user).toBeNull();
    expect(clear).toHaveBeenCalledOnce();
    if (fails) await expect(operation).rejects.toThrow("offline");
    else await operation;
    const [url, init] = fetch.mock.calls[1]!;
    expect(String(url)).toBe("http://127.0.0.1:8000/auth/logout");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Authorization")).toBe(`Bearer ${token}`);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("迟到 me 不复活已登出的身份", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(success(null));
    const auth = create(fetch);
    const restoring = auth.initialize();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    await auth.logout();
    finish(success(user));
    await restoring;
    expect(auth.state.user).toBeNull();
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });
  it("旧请求的 401 不清除后来登录的新会话", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    let finish!: (response: Response) => void;
    const nextToken = "b".repeat(43);
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(loginResponse(nextToken));
    const auth = create(fetch);
    const restoring = auth.initialize();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    await auth.login(credentials);
    finish(invalid());
    await restoring;
    expect(auth.state.user).toEqual(user);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe(nextToken);
  });
  it("受保护客户端遇到 401 清理本地状态", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(loginResponse())
      .mockResolvedValueOnce(invalid());
    const auth = create(fetch);
    await auth.login(credentials);
    const clear = vi.fn();
    auth.registerProtectedStore(clear);
    await expect(auth.request("getCurrentUser")).rejects.toMatchObject({ name: "ApiClientError" });
    expect(auth.state.user).toBeNull();
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(clear).toHaveBeenCalledOnce();
  });

  it.each(["logout", "switch"])("%s 后迟到成功不会重新填入受保护 store", async (action) => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(loginResponse())
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(action === "logout" ? success(null) : loginResponse("b".repeat(43)));
    const auth = create(fetch);
    await auth.login(credentials);
    const items: string[] = [];
    auth.registerProtectedStore(() => items.splice(0));
    const request = auth.request("getCurrentUser").then((value) => {
      items.push(value.email);
    });
    const rejected = expect(request).rejects.toMatchObject({ name: "AbortError" });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    if (action === "logout") await auth.logout();
    else await auth.login(credentials);
    finish(success(user));
    await rejected;
    expect(items).toEqual([]);
  });

  it("迟到登录不覆盖已登出身份", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const auth = create(fetch);
    const signingIn = auth.login(credentials);
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    await auth.logout();
    finish(loginResponse());
    await signingIn;
    expect(auth.state.user).toBeNull();
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });

  it("旧受保护请求的 401 不影响新登录", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(loginResponse())
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce(loginResponse("b".repeat(43)));
    const auth = create(fetch);
    await auth.login(credentials);
    const pending = auth.request("getCurrentUser");
    const rejected = expect(pending).rejects.toMatchObject({ name: "ApiClientError" });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    await auth.login(credentials);
    finish(invalid());
    await rejected;
    expect(auth.state.user).toEqual(user);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe("b".repeat(43));
  });
});
