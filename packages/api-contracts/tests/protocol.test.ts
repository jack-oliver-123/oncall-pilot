import { describe, expect, expectTypeOf, it } from "vitest";
import fixtures from "../fixtures/protocol.json";
import { errorCatalog, operations, parseContract, ProtocolError } from "../src/index";
import type { ApiError, HealthResponse, SseEvent } from "../src/index";

describe("HTTP 合同", () => {
  it.each(fixtures.successes)("保留成功数据 $data", (sample) => {
    expect(parseContract("ApiSuccess", sample)).toEqual(sample);
  });
  it.each(fixtures.failures)("验证目录错误 $error.code", (sample) => {
    expect(parseContract("ApiFailure", sample)).toEqual(sample);
    expect(Object.values(errorCatalog)).toContainEqual(sample.error);
    expect(() => parseContract("ApiFailure", { ...sample, error: { ...sample.error, httpStatus: 200 } })).toThrow(ProtocolError);
  });
  it("四类错误均已登记且 health typed path 对齐", () => {
    expect(new Set(Object.values(errorCatalog).map((e) => e.category))).toEqual(new Set(["AUTH", "BUSINESS", "VALIDATION", "SYSTEM"]));
    expect(operations.getHealth.path).toBe("/health");
    expectTypeOf<HealthResponse["data"]>().toEqualTypeOf<{ status: "ok" }>();
  });
  it("拒绝缺失、额外字段、类型伪装和不安全 ID", () => {
    const base = fixtures.successes[0]!;
    for (const invalid of [{ ...base, ok: 1 }, { ...base, extra: true }, { ok: true, data: {} }, { ...base, meta: { requestId: "a\n" } }]) {
      expect(() => parseContract("ApiSuccess", invalid)).toThrow(ProtocolError);
    }
    expect(() => parseContract("ApiSuccess", { ...base, data: undefined })).toThrow(ProtocolError);
  });
});

describe("SSE 合同", () => {
  it.each(fixtures.events)("接受 $type $status", (sample) => {
    expect(parseContract("SseEvent", sample)).toEqual(sample);
    expect(() => parseContract("SseEvent", { ...sample, channel: "private" })).toThrow();
    expect(() => parseContract("SseEvent", { ...sample, timestamp: "2026-02-30T00:00:00Z" })).toThrow();
    const { id: _id, ...missingId } = sample;
    expect(() => parseContract("SseEvent", missingId)).toThrow();
  });
  it("穷尽八类目录和四态工具生命周期", () => {
    expect(new Set(fixtures.events.map((e) => e.type))).toEqual(new Set(["content.delta", "reasoning.delta", "tool.call", "reference.source", "task.status", "report", "complete", "error"]));
    const tools = fixtures.events.filter((e) => e.type === "tool.call");
    expect(tools.map((e) => e.status)).toEqual(["started", "delta", "completed", "failed"]);
    for (const tool of tools) {
      expect(() => parseContract("SseEvent", { ...tool, status: "completed", output: undefined })).toThrow();
    }
    expect(() => parseContract("SseEvent", { ...fixtures.events[0], type: "private.event" })).toThrow();
  });
  it("HTTP/SSE/tool failed 复用同一 error 类型和实例", () => {
    expectTypeOf<Extract<SseEvent, { type: "error" }>["error"]>().toEqualTypeOf<ApiError>();
    expectTypeOf<Extract<SseEvent, { type: "tool.call"; status: "failed" }>["error"]>().toEqualTypeOf<ApiError>();
    for (const failure of fixtures.failures) {
      const sample = fixtures.events.find((event) => event.type === "error")!;
      expect(parseContract("SseEvent", { ...sample, error: failure.error })).toMatchObject({ error: failure.error });
    }
  });
});
