// @vitest-environment jsdom
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { errorCatalog } from "@oncall-pilot/api-contracts";
import App from "../src/App.vue";
import WorkspaceLayout from "../src/layouts/WorkspaceLayout.vue";
import { createApplication } from "../src/application";
import { applicationKey } from "../src/context";
import { AUTH_TOKEN_KEY } from "../src/auth/authState";
vi.mock("virtual:public-config", () => ({
  default: { frontend: { title: "On-call Pilot", apiBaseUrl: "http://localhost:8000" } },
}));
const user = {
  id: "5b0eab8a-6c94-4b4a-bdb4-653a91271fe1",
  email: "person@example.com",
  createdAt: "2026-09-08T00:00:00Z",
};
const success = (data: unknown) =>
  new Response(JSON.stringify({ ok: true, data, meta: { requestId: "ui-test" } }), {
    headers: { "Content-Type": "application/json" },
  });
let wrapper: VueWrapper | undefined;
let application: ReturnType<typeof createApplication> | undefined;
async function setup(path: string, fetch: typeof globalThis.fetch) {
  application = createApplication({
    baseUrl: "http://localhost:8000",
    storage: localStorage,
    fetch,
    history: createMemoryHistory(),
  });
  await application.router.push(path);
  wrapper = mount(App, {
    global: {
      plugins: [application.pinia, application.router],
      provide: { [applicationKey as symbol]: application },
    },
  });
  await flushPromises();
  return { ...application, wrapper };
}
afterEach(() => {
  wrapper?.unmount();
  application?.dispose();
  localStorage.clear();
});
describe("中文工作台界面", () => {
  it("登录表单标签、校验与真实合同提交，保留目标路由", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(success({ user, token: "a".repeat(43), tokenType: "Bearer" }))
      .mockResolvedValueOnce(success({ status: "ok" }));
    const app = await setup("/knowledge?tab=recent", fetch);
    await app.wrapper.get("form").trigger("submit");
    expect(app.wrapper.get('[role="alert"]').text()).toContain("邮箱");
    expect(fetch).not.toHaveBeenCalled();
    await app.wrapper.get("#email").setValue(user.email);
    await app.wrapper.get("#password").setValue("secret-password");
    await app.wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(app.router.currentRoute.value.fullPath).toBe("/knowledge?tab=recent");
    expect(JSON.parse(fetch.mock.calls[0]![1]!.body as string)).toEqual({
      email: user.email,
      password: "secret-password",
    });
    expect(app.wrapper.get("h1").text()).toBe("知识库");
  });
  it("注册检查两次密码，成功返回登录并保持未认证", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(success(user));
    const app = await setup("/register?redirect=/mcp", fetch);
    await app.wrapper.get("#email").setValue(user.email);
    await app.wrapper.get("#password").setValue("secret-password");
    await app.wrapper.get("#confirmation").setValue("wrong-password");
    await app.wrapper.get("form").trigger("submit");
    expect(app.wrapper.get('[role="alert"]').text()).toContain("不一致");
    expect(fetch).not.toHaveBeenCalled();
    await app.wrapper.get("#confirmation").setValue("secret-password");
    await app.wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(app.router.currentRoute.value.name).toBe("login");
    expect(app.router.currentRoute.value.query.redirect).toBe("/mcp");
    expect(app.wrapper.text()).toContain("注册成功，请登录");
    expect(app.auth.state.user).toBeNull();
    expect(localStorage.length).toBe(0);
  });
  it("请求中禁止重复提交，服务错误使用 alert 且不误报成功", async () => {
    let finish!: (response: Response) => void;
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const app = await setup("/login", fetch);
    await app.wrapper.get("#email").setValue(user.email);
    await app.wrapper.get("#password").setValue("secret-password");
    await app.wrapper.get("form").trigger("submit");
    await app.wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(fetch).toHaveBeenCalledOnce();
    expect(app.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    finish(
      new Response(
        JSON.stringify({
          ok: false,
          error: errorCatalog.AUTH_INVALID_CREDENTIALS,
          meta: { requestId: "ui-test" },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );
    await flushPromises();
    expect(app.wrapper.get('[role="alert"]').text()).toContain(
      errorCatalog.AUTH_INVALID_CREDENTIALS.message,
    );
    expect(app.feedback.message).toBeNull();
    expect(app.wrapper.get<HTMLInputElement>("#password").element.value).toBe("");
  });
  it("四路由占位与导航同步，仅 Chat 出现会话列，服务状态来自真实响应", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "a".repeat(43));
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(success(user))
      .mockResolvedValueOnce(success({ status: "ok" }))
      .mockRejectedValueOnce(new TypeError("offline"));
    const app = await setup("/chat", fetch);
    expect(app.wrapper.text()).toContain("服务可连接");
    for (const [path, title] of [
      ["chat", "值班对话"],
      ["knowledge", "知识库"],
      ["aiops", "智能运维"],
      ["mcp", "工具连接"],
    ]) {
      await app.router.push("/" + path);
      await flushPromises();
      expect(app.wrapper.get("h1").text()).toBe(title);
      expect(app.wrapper.get('[aria-current="page"]').text()).toBe(title);
      expect(app.wrapper.find('[aria-label="会话区域"]').exists()).toBe(path === "chat");
      expect(app.wrapper.get("main").text()).toContain("尚未开放");
      expect(app.wrapper.get("main").findAll("button, input")).toHaveLength(0);
    }
    await app.wrapper.get('[aria-label="刷新服务状态"]').trigger("click");
    await flushPromises();
    expect(app.wrapper.text()).toContain("服务无法连接");
  });
  it("只有 Chat 可渲染会话区域插槽", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "a".repeat(43));
    const app = await setup(
      "/chat",
      vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(success(user))
        .mockResolvedValue(success({ status: "ok" })),
    );
    const layout = mount(WorkspaceLayout, {
      slots: { conversations: "<p>已接入的会话区域</p>" },
      global: { plugins: [app.pinia, app.router], provide: { [applicationKey as symbol]: app } },
    });
    expect(layout.text()).toContain("已接入的会话区域");
    await app.router.push("/knowledge");
    await flushPromises();
    expect(layout.text()).not.toContain("已接入的会话区域");
    layout.unmount();
  });
  it("恢复网络错误阻止受保护内容并可通过按钮重试", async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "a".repeat(43));
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(success(user))
      .mockResolvedValueOnce(success({ status: "ok" }));
    const app = await setup("/knowledge", fetch);
    expect(app.wrapper.text()).toContain("暂时无法恢复登录");
    expect(app.wrapper.find("nav").exists()).toBe(false);
    await app.wrapper.get("button").trigger("click");
    await flushPromises();
    expect(app.wrapper.get("h1").text()).toBe("知识库");
  });
});
