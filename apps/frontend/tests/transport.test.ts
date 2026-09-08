import { describe, expect, expectTypeOf, it, vi } from "vitest";
import fixtures from "../../../packages/api-contracts/fixtures/protocol.json";
import { ProtocolError, type SseEvent } from "@oncall-pilot/api-contracts";
import { ApiClientError, createApiClient } from "../src/transport/apiClient";
import { createSseClient, SseFrameParser } from "../src/transport/sseClient";

const baseUrl = "https://api.example.test/";
const encode = (text: string) => new TextEncoder().encode(text);
const jsonResponse = (value: unknown, status = 200, headers: HeadersInit = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
const sample = fixtures.events[0]!;
const frame = (event: (typeof fixtures.events)[number], newline = "\n") =>
  `id: ${event.id}${newline}event: ${event.type}${newline}data: ${JSON.stringify(event)}${newline}${newline}`;

describe("apiClient", () => {
  it("typed data、请求标识、bearer 和 signal 注入", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(jsonResponse(fixtures.successes[0]));
    const controller = new AbortController();
    const api = createApiClient({
      baseUrl,
      fetch,
      getRequestId: () => "client-42",
      getBearer: async () => "test-bearer",
    });
    const result = await api.request("getHealth", { signal: controller.signal });
    expectTypeOf(result).toEqualTypeOf<{ status: "ok" }>();
    expect(result).toEqual({ status: "ok" });
    const [url, init] = fetch.mock.calls[0]!;
    expect(String(url)).toBe(baseUrl + "health");
    expect(init?.method).toBe("GET");
    expect(init?.signal).toBe(controller.signal);
    const headers = new Headers(init?.headers);
    expect(headers.get("X-Request-ID")).toBe("client-42");
    expect(headers.get("Authorization")).toBe("Bearer test-bearer");
  });
  it.each(fixtures.failures)("四类目录错误 $error.code", async (failure) => {
    const api = createApiClient({
      baseUrl,
      fetch: vi.fn().mockResolvedValue(jsonResponse(failure, failure.error.httpStatus)),
    });
    await expect(api.request("getHealth")).rejects.toMatchObject({
      name: "ApiClientError",
      error: failure.error,
      requestId: failure.meta.requestId,
    });
  });
  it("无 bearer 时不发送认证，允许显式请求 ID", async () => {
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(jsonResponse(fixtures.successes[0]));
    await createApiClient({ baseUrl, fetch }).request("getHealth", {
      headers: { "X-Request-ID": "explicit-42" },
    });
    const headers = new Headers(fetch.mock.calls[0]?.[1]?.headers);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.get("X-Request-ID")).toBe("explicit-42");
  });
  it("拒绝非法 JSON、形状、状态和不一致 response ID", async () => {
    const invalid = [
      new Response("bad", { headers: { "Content-Type": "application/json" } }),
      new Response("{}", { headers: { "Content-Type": "text/html" } }),
      jsonResponse({ status: "ok" }),
      jsonResponse(fixtures.successes[0], 500),
      jsonResponse(fixtures.successes[0], 201),
      jsonResponse(fixtures.failures[0], 200),
      jsonResponse(fixtures.failures[0], 403),
      jsonResponse(fixtures.successes[0], 200, { "X-Request-ID": "different" }),
      jsonResponse(fixtures.successes[1]),
    ];
    for (const response of invalid) {
      const api = createApiClient({ baseUrl, fetch: vi.fn().mockResolvedValue(response) });
      await expect(api.request("getHealth")).rejects.toBeInstanceOf(ProtocolError);
    }
  });
  it("网络错误与取消不伪装为业务错误", async () => {
    const error = new TypeError("网络失败");
    const fetch = vi.fn().mockRejectedValue(error);
    await expect(createApiClient({ baseUrl, fetch }).request("getHealth")).rejects.toBe(error);
    const cancelled = new DOMException("取消", "AbortError");
    await expect(
      createApiClient({ baseUrl, fetch: vi.fn().mockRejectedValue(cancelled) }).request(
        "getHealth",
      ),
    ).rejects.toBe(cancelled);
  });
});

describe("SseFrameParser", () => {
  it.each(["\n", "\r\n", "\r"])("任意字节边界切分，包括中文和换行 %j", (newline) => {
    const bytes = encode(
      "\uFEFF: 心跳" + newline + newline + fixtures.events.map((e) => frame(e, newline)).join(""),
    );
    for (let index = 0; index <= bytes.length; index++) {
      const parser = new SseFrameParser();
      expect([
        ...parser.push(bytes.slice(0, index)),
        ...parser.push(bytes.slice(index)),
        ...parser.finish(),
      ]).toEqual(fixtures.events);
    }
    const parser = new SseFrameParser();
    const events: SseEvent[] = [];
    for (const byte of bytes) events.push(...parser.push(Uint8Array.of(byte)));
    events.push(...parser.finish());
    expect(events).toEqual(fixtures.events);
  });
  it("多行 data、注释、未知字段、空 frame", () => {
    const multiline = JSON.stringify(sample, null, 2)
      .split("\n")
      .map((line) => "data: " + line)
      .join("\n");
    const parser = new SseFrameParser();
    expect(
      parser.push(encode(`:heartbeat\n\nretry: 1000\nunknown: yes\n\n${multiline}\n\n`)),
    ).toEqual([sample]);
  });
  it("EOF 不派发未结束 frame，最后 CR 可以终止空行", () => {
    const parser = new SseFrameParser();
    expect(parser.push(encode("data: " + JSON.stringify(sample) + "\n"))).toEqual([]);
    expect(parser.finish()).toEqual([]);
    expect(() => parser.push(new Uint8Array())).toThrow();
    expect(new SseFrameParser().push(encode(frame(sample, "\r")))).toEqual([sample]);
  });
  it("拒绝未知事件、非法 JSON、元数据矛盾和超限 frame", () => {
    for (const text of [
      "data: bad\n\n",
      frame({ ...sample, type: "private" }),
      `event: other\ndata: ${JSON.stringify(sample)}\n\n`,
      `id: other\ndata: ${JSON.stringify(sample)}\n\n`,
    ]) {
      expect(() => new SseFrameParser().push(encode(text))).toThrow(ProtocolError);
    }
    expect(() => new SseFrameParser(4).push(encode("12345"))).toThrow(ProtocolError);
  });
});

describe("sseClient", () => {
  it("解码事件并在自然 EOF 释放 reader", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encode(fixtures.events.map((e) => frame(e)).join("")));
        controller.close();
      },
    });
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(
        new Response(body, { headers: { "Content-Type": "text/event-stream; charset=utf-8" } }),
      );
    const client = createSseClient({
      baseUrl,
      fetch,
      getRequestId: () => "sse-42",
      getBearer: () => "stream-token",
    });
    const values: SseEvent[] = [];
    for await (const event of client.stream("/future-stream")) values.push(event);
    expect(values).toEqual(fixtures.events);
    expect(body.locked).toBe(false);
    const headers = new Headers(fetch.mock.calls[0]?.[1]?.headers);
    expect(headers.get("Accept")).toBe("text/event-stream");
    expect(headers.get("Authorization")).toBe("Bearer stream-token");
    expect(headers.get("X-Request-ID")).toBe("sse-42");
  });
  it("提前结束取消流，不自动重连", async () => {
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encode(frame(sample)));
      },
      cancel,
    });
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
    const iterator = createSseClient({ baseUrl, fetch }).stream("/future-stream");
    expect((await iterator.next()).value).toEqual(sample);
    await iterator.return(undefined);
    expect(cancel).toHaveBeenCalledOnce();
    expect(body.locked).toBe(false);
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("取消后不继续派发同一 chunk 中的缓存事件", async () => {
    const controller = new AbortController();
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({
      start(stream) {
        stream.enqueue(encode(frame(sample) + frame(sample)));
      },
      cancel,
    });
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } }));
    const stream = createSseClient({ baseUrl, fetch }).stream("/future-stream", {
      signal: controller.signal,
    });
    await stream.next();
    controller.abort();
    await expect(stream.next()).rejects.toMatchObject({ name: "AbortError" });
    expect(cancel).toHaveBeenCalledOnce();
    expect(body.locked).toBe(false);
  });
  it("握手错误复用 ApiClientError，错误 Content-Type 关闭 body", async () => {
    const error = fixtures.failures[0]!;
    const stream = createSseClient({
      baseUrl,
      fetch: vi.fn().mockResolvedValue(jsonResponse(error, 401)),
    }).stream("/future-stream");
    await expect(stream.next()).rejects.toBeInstanceOf(ApiClientError);
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({ cancel });
    const invalid = createSseClient({
      baseUrl,
      fetch: vi.fn().mockResolvedValue(new Response(body)),
    }).stream("/future-stream");
    await expect(invalid.next()).rejects.toBeInstanceOf(ProtocolError);
    expect(cancel).toHaveBeenCalledOnce();
  });
  it("在等待数据时传递 AbortSignal 并释放锁", async () => {
    const abortController = new AbortController();
    let body: ReadableStream<Uint8Array> | undefined;
    const fetch: typeof globalThis.fetch = vi.fn(async (_url, init) => {
      body = new ReadableStream<Uint8Array>({
        start(controller) {
          init?.signal?.addEventListener(
            "abort",
            () => controller.error(new DOMException("取消", "AbortError")),
            { once: true },
          );
        },
      });
      return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
    });
    const iterator = createSseClient({ baseUrl, fetch }).stream("/future-stream", {
      signal: abortController.signal,
    });
    const pending = iterator.next();
    await vi.waitFor(() => expect(body?.locked).toBe(true));
    abortController.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(body?.locked).toBe(false);
  });
});
