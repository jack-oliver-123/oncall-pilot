// @vitest-environment jsdom
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import AppFeedback from "../src/components/AppFeedback.vue";
import AppLoadingState from "../src/components/AppLoadingState.vue";
import AppEmptyState from "../src/components/AppEmptyState.vue";
import AppErrorState from "../src/components/AppErrorState.vue";
import AsyncStatusBadge from "../src/components/AsyncStatusBadge.vue";
import { useFeedbackStore } from "../src/stores/feedback";
afterEach(() => vi.useRealTimers());
describe("共享交互状态", () => {
  it("新消息重置三秒 timer、支持三种反馈、关闭与卸载无残留 timer", async () => {
    vi.useFakeTimers();
    const pinia = createPinia();
    const store = useFeedbackStore(pinia);
    const wrapper = mount(AppFeedback, { global: { plugins: [pinia] } });
    store.show("success", "保存成功");
    await nextTick();
    expect(wrapper.get('[role="status"]').text()).toBe("保存成功");
    await vi.advanceTimersByTimeAsync(2500);
    store.show("info", "正在准备");
    await nextTick();
    await vi.advanceTimersByTimeAsync(500);
    expect(wrapper.text()).toContain("正在准备");
    await vi.advanceTimersByTimeAsync(2499);
    expect(store.message).not.toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    expect(store.message).toBeNull();
    store.show("error", "操作失败");
    await nextTick();
    expect(wrapper.get('[role="alert"]').attributes("aria-live")).toBe("assertive");
    await wrapper.get('button[aria-label="关闭提示"]').trigger("click");
    expect(store.message).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
    store.show("info", "下一条");
    await nextTick();
    wrapper.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
  it("加载、空、错误、异步状态包含文字与可访问语义", async () => {
    const loading = mount(AppLoadingState);
    expect(loading.get('[role="status"]').attributes("aria-busy")).toBe("true");
    expect(loading.text()).toContain("加载");
    const empty = mount(AppEmptyState, {
      props: { title: "暂无资料", description: "上传后会显示在这里" },
    });
    expect(empty.get('[role="status"]').text()).toContain("暂无资料");
    const error = mount(AppErrorState, { props: { message: "连接失败", retry: true } });
    expect(error.get('[role="alert"]').text()).toContain("连接失败");
    await error.get("button").trigger("click");
    expect(error.emitted("retry")).toHaveLength(1);
    for (const status of ["idle", "loading", "success", "error"] as const) {
      const badge = mount(AsyncStatusBadge, { props: { status, text: "文字状态" } });
      expect(badge.get('[role="status"]').text()).toBe("文字状态");
      expect(badge.get("svg").attributes("aria-hidden")).toBe("true");
      badge.unmount();
    }
    loading.unmount();
    empty.unmount();
    error.unmount();
  });
});
