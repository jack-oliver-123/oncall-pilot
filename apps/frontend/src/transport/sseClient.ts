import { parseContract, ProtocolError, type SseEvent } from "@oncall-pilot/api-contracts";
import { readEnvelope, sendRequest, type TransportOptions } from "./apiClient";

export class SseFrameParser {
  private readonly decoder = new TextDecoder("utf-8");
  private line = "";
  private data: string[] = [];
  private eventType = "";
  private frameId: string | undefined;
  private skipLF = false;
  private size = 0;
  private ended = false;

  constructor(private readonly maxFrameSize = 1024 * 1024) {
    if (!Number.isSafeInteger(maxFrameSize) || maxFrameSize < 1)
      throw new RangeError("frame 上限必须是正整数");
  }

  push(chunk: Uint8Array): SseEvent[] {
    if (this.ended) throw new ProtocolError("SSE parser 已结束");
    return this.consume(this.decoder.decode(chunk, { stream: true }));
  }

  finish(): SseEvent[] {
    if (this.ended) throw new ProtocolError("SSE parser 已结束");
    this.ended = true;
    const events = this.consume(this.decoder.decode());
    this.line = "";
    this.data = [];
    return events;
  }

  private consume(text: string): SseEvent[] {
    const result: SseEvent[] = [];
    for (const character of text) {
      if (this.skipLF) {
        this.skipLF = false;
        if (character === "\n") continue;
      }
      this.size += character.length;
      if (this.size > this.maxFrameSize) throw new ProtocolError("SSE frame 超过大小限制");
      if (character === "\r" || character === "\n") {
        const event = this.processLine(this.line);
        this.line = "";
        if (event) result.push(event);
        this.skipLF = character === "\r";
      } else {
        this.line += character;
      }
    }
    return result;
  }

  private processLine(line: string): SseEvent | undefined {
    if (line === "") {
      const data = this.data;
      const eventType = this.eventType;
      const frameId = this.frameId;
      this.data = [];
      this.eventType = "";
      this.frameId = undefined;
      this.size = 0;
      if (data.length === 0) return undefined;
      let value: unknown;
      try {
        value = JSON.parse(data.join("\n"));
      } catch {
        throw new ProtocolError("SSE data 包含无效 JSON");
      }
      const event = parseContract("SseEvent", value);
      if (
        (eventType !== "" && eventType !== event.type) ||
        (frameId !== undefined && frameId !== event.id)
      ) {
        throw new ProtocolError("SSE frame 与 JSON 事件标识不一致");
      }
      return event;
    }
    if (line.startsWith(":")) return undefined;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") this.data.push(value);
    if (field === "event") this.eventType = value;
    if (field === "id" && !value.includes("\0")) this.frameId = value;
    return undefined;
  }
}

export function createSseClient(options: TransportOptions) {
  return {
    async *stream(path: string, init: RequestInit = {}): AsyncGenerator<SseEvent> {
      const controller = new AbortController();
      const abort = () => controller.abort(init.signal?.reason);
      init.signal?.addEventListener("abort", abort, { once: true });
      if (init.signal?.aborted) abort();
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      let response: Response | undefined;
      try {
        response = await sendRequest(
          options,
          path,
          { ...init, signal: controller.signal },
          "text/event-stream",
        );
        if (!response.ok) {
          await readEnvelope(response);
          throw new ProtocolError("SSE 握手失败");
        }
        if (
          response.status !== 200 ||
          response.headers.get("Content-Type")?.split(";")[0]?.trim().toLowerCase() !==
            "text/event-stream"
        ) {
          throw new ProtocolError("SSE 握手必须返回 200 text/event-stream");
        }
        if (!response.body) throw new ProtocolError("SSE 响应没有可读取的 body");
        reader = response.body.getReader();
        const parser = new SseFrameParser();
        while (true) {
          controller.signal.throwIfAborted();
          const chunk = await reader.read();
          controller.signal.throwIfAborted();
          if (chunk.done) break;
          for (const event of parser.push(chunk.value)) {
            controller.signal.throwIfAborted();
            yield event;
          }
        }
        for (const event of parser.finish()) yield event;
      } finally {
        init.signal?.removeEventListener("abort", abort);
        controller.abort();
        if (reader) {
          try {
            await reader.cancel();
          } catch {
            /* 已中止的 reader 可能拒绝 cancel。 */
          }
          reader.releaseLock();
        } else if (response?.body && !response.body.locked) {
          try {
            await response.body.cancel();
          } catch {
            /* 保留原始握手错误。 */
          }
        }
      }
    },
  };
}
