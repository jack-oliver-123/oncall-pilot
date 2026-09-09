// @vitest-environment jsdom
import { flushPromises } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { errorCatalog } from "@oncall-pilot/api-contracts";
import { createApplication } from "../src/application";
import { AUTH_TOKEN_KEY } from "../src/auth/authState";
import { safeRedirect } from "../src/router";

vi.mock("virtual:public-config", () => ({
  default: { frontend: { title: "On-call Pilot", apiBaseUrl: "http://localhost:8000" } },
}));

const user = {
  id: "5b0eab8a-6c94-4b4a-bdb4-653a91271fe1",
  email: "person@example.com",
  createdAt: "2026-09-08T00:00:00Z",
};
const token = "a".repeat(43);
const credentials = { email: user.email, password: "secret-password" };
const success = (data: unknown) =>
  new Response(JSON.stringify({ ok: true, data, meta: { requestId: "shell-test" } }), {
    headers: { "Content-Type": "application/json" },
  });
const unauthorized = () =>
  new Response(
    JSON.stringify({
      ok: false,
      error: errorCatalog.AUTH_UNAUTHENTICATED,
      meta: { requestId: "shell-test" },
    }),
    { status: 401, headers: { "Content-Type": "application/json" } },
  );
function setup(fetch = vi.fn<typeof globalThis.fetch>()) {
  return {
    ...createApplication({
      baseUrl: "http://localhost:8000",
      storage: localStorage,
      fetch,
      history: createMemoryHistory(),
    }),
    fetch,
  };
}
afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("工作台认证路由与状态", () => {
  it("首次导航只初始化一次，保护路由并保留完整 redirect", async () => {
    const app = setup();
    const initialize = vi.spyOn(app.auth, "initialize");
    await app.router.push("/knowledge?tab=recent#items");
    expect(app.router.currentRoute.value.path).toBe("/login");
    expect(app.router.currentRoute.value.query.redirect).toBe("/knowledge?tab=recent#items");
    await app.router.push("/register");
    await app.router.push("/mcp");
    expect(initialize).toHaveBeenCalledTimes(1);
    expect(app.fetch).not.toHaveBeenCalled();
  });
  it("通过真实 me 合同恢复身份，publicOnly、根与未知路由回 chat", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const app = setup(vi.fn<typeof fetch>().mockResolvedValue(success(user)));
    await app.router.push("/knowledge");
    expect(app.auth.state.user?.email).toBe(user.email);
    expect(String(app.fetch.mock.calls[0]?.[0])).toBe("http://localhost:8000/auth/me");
    for (const path of ["/login", "/register", "/", "/missing"]) {
      await app.router.push(path);
      expect(app.router.currentRoute.value.path).toBe("/chat");
    }
    expect(app.fetch).toHaveBeenCalledTimes(1);
  });
  it("安全 redirect 只接受明确的受保护路由", () => {
    const { router } = setup();
    expect(safeRedirect(router, "/knowledge?q=x#docs")).toBe("/knowledge?q=x#docs");
    for (const value of [
      "https://evil.test",
      "//evil.test",
      "/\\evil.test",
      "/login",
      "/unknown",
      ["/chat"],
      undefined,
    ])
      expect(safeRedirect(router, value)).toBe("/chat");
  });
  it("恢复 401 清理 token；网络失败可显式重试", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const first = setup(vi.fn<typeof fetch>().mockResolvedValue(unauthorized()));
    await first.router.push("/chat");
    expect(first.auth.state.status).toBe("anonymous");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const second = setup(
      vi
        .fn<typeof fetch>()
        .mockRejectedValueOnce(new TypeError("offline"))
        .mockResolvedValueOnce(success(user)),
    );
    await second.router.push("/knowledge");
    expect(second.auth.state.status).toBe("error");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe(token);
    await second.auth.initialize();
    await second.router.replace(
      safeRedirect(second.router, second.router.currentRoute.value.query.redirect),
    );
    expect(second.router.currentRoute.value.path).toBe("/knowledge");
  });
  it("登出先撤销再清理所有登记 store，注销回调不执行", async () => {
    let finish!: (response: Response) => void;
    const app = setup(
      vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(success({ user, token, tokenType: "Bearer" }))
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              finish = resolve;
            }),
        ),
    );
    await app.auth.login(credentials);
    app.protectedData.activeResourceId = "private-resource";
    const reset = vi.fn();
    const removed = vi.fn();
    app.auth.registerProtectedStore(reset);
    app.auth.registerProtectedStore(removed)();
    const pending = app.auth.logout();
    await flushPromises();
    expect(reset).not.toHaveBeenCalled();
    expect(app.auth.state.user).toBeNull();
    finish(success(null));
    await pending;
    expect(reset).toHaveBeenCalledOnce();
    expect(removed).not.toHaveBeenCalled();
    expect(app.protectedData.activeResourceId).toBeNull();
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
  });
  it("HTTP 401 清理 protectedData，离开受保护画布", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    const app = setup(
      vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(success(user))
        .mockResolvedValueOnce(unauthorized()),
    );
    await app.router.push("/knowledge");
    app.protectedData.activeResourceId = "private";
    await expect(app.auth.request("getCurrentUser")).rejects.toThrow();
    await flushPromises();
    expect(app.protectedData.activeResourceId).toBeNull();
    expect(app.router.currentRoute.value.path).toBe("/login");
  });
});

it("提交期间切换 publicOnly 页面，迟到登录仍回到受保护内部目标", async () => {
  let finish!: (response: Response) => void;
  const app = setup(
    vi.fn<typeof fetch>().mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    ),
  );
  await app.router.push("/login?redirect=/knowledge");
  const login = app.auth.login(credentials);
  await flushPromises();
  await app.router.push("/register?redirect=/knowledge");
  finish(success({ user, token, tokenType: "Bearer" }));
  await login;
  await flushPromises();
  expect(app.router.currentRoute.value.path).toBe("/knowledge");
  app.dispose();
});

it("反馈随身份清理，已 dispose 的 protectedData 不再执行清理回调", async () => {
  const app = setup(
    vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(success({ user, token, tokenType: "Bearer" }))
      .mockResolvedValueOnce(success(null)),
  );
  await app.auth.login(credentials);
  app.feedback.show("info", "前一账号的消息");
  app.protectedData.activeResourceId = "disposed-resource";
  app.protectedData.$dispose();
  await app.auth.logout();
  expect(app.feedback.message).toBeNull();
  expect(app.protectedData.activeResourceId).toBe("disposed-resource");
  app.dispose();
});
