// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("virtual:public-config", () => ({
  default: {
    frontend: {
      title: "On-call Pilot",
      apiBaseUrl: "http://127.0.0.1:8000",
      analytics: { publicKey: "" },
    },
  },
}));

import App from "../src/App.vue";

describe("On-call Pilot 值班工作台", () => {
  it("向非技术值班人员呈现诚实的 foundation 状态", () => {
    const wrapper = mount(App);

    expect(wrapper.get("[data-testid='brand']").text()).toBe("On-call Pilot");
    expect(wrapper.get("h1").text()).toBe("值班工作台");
    expect(wrapper.get("h2").text()).toBe("工作台正在准备中");
    expect(wrapper.text()).toContain("当前版本暂未开放业务操作。");
  });

  it("只提供品牌图标和语义结构，不伪造可交互功能", () => {
    const wrapper = mount(App);

    expect(wrapper.find("header").exists()).toBe(true);
    expect(wrapper.find("main").exists()).toBe(true);
    expect(wrapper.get("section").attributes("aria-labelledby")).toBe("workspace-title");
    expect(wrapper.get("#workspace-title").element).toBe(wrapper.get("h1").element);
    expect(wrapper.find("svg").attributes("aria-hidden")).toBe("true");
    expect(wrapper.findAll("a, button, input, select, textarea")).toHaveLength(0);
    expect(wrapper.findAll("[tabindex]")).toHaveLength(0);
  });
});
