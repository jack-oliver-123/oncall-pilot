import {
  operations,
  parseContract,
  ProtocolError,
  type ApiEnvelope,
  type ApiError,
  type OperationResponses,
} from "@oncall-pilot/api-contracts";

export interface TransportOptions {
  baseUrl: string;
  fetch?: typeof fetch;
  getRequestId?: () => string | Promise<string>;
  getBearer?: () => string | undefined | Promise<string | undefined>;
}

export class ApiClientError extends Error {
  constructor(
    public readonly error: ApiError,
    public readonly requestId: string,
  ) {
    super(error.message);
    this.name = "ApiClientError";
  }
}

export async function sendRequest(
  options: TransportOptions,
  path: string,
  init: RequestInit,
  accept: string,
): Promise<Response> {
  const base = new URL(options.baseUrl.endsWith("/") ? options.baseUrl : options.baseUrl + "/");
  if (!path.startsWith("/") || path.startsWith("//"))
    throw new ProtocolError("请求路径必须位于 API 根地址下");
  const url = new URL(path.slice(1), base);
  if (url.origin !== base.origin) throw new ProtocolError("请求路径不能改变 API 来源");
  const headers = new Headers(init.headers);
  headers.set("Accept", accept);
  const requestId =
    headers.get("X-Request-ID") ?? (await options.getRequestId?.()) ?? crypto.randomUUID();
  headers.set("X-Request-ID", parseContract("RequestId", requestId));
  const bearer = await options.getBearer?.();
  if (bearer !== undefined) headers.set("Authorization", `Bearer ${bearer}`);
  return (options.fetch ?? globalThis.fetch)(url, { ...init, headers });
}

export async function readEnvelope(response: Response): Promise<ApiEnvelope> {
  if (
    response.headers.get("Content-Type")?.split(";")[0]?.trim().toLowerCase() !== "application/json"
  ) {
    throw new ProtocolError("响应必须是 application/json");
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch (error) {
    if (error instanceof SyntaxError) throw new ProtocolError("响应包含无效 JSON");
    throw error;
  }
  const envelope = parseContract("ApiEnvelope", value);
  const responseId = response.headers.get("X-Request-ID");
  if (responseId !== null && responseId !== envelope.meta.requestId) {
    throw new ProtocolError("响应头与 envelope 的请求标识不一致");
  }
  if (
    envelope.ok !== response.ok ||
    (!envelope.ok && envelope.error.httpStatus !== response.status)
  ) {
    throw new ProtocolError("HTTP 状态与 envelope 不一致");
  }
  if (!envelope.ok) throw new ApiClientError(envelope.error, envelope.meta.requestId);
  return envelope;
}

export function createApiClient(options: TransportOptions) {
  return {
    async request<K extends keyof OperationResponses>(
      operation: K,
      init: Omit<RequestInit, "method"> = {},
    ): Promise<OperationResponses[K]["data"]> {
      const contract = operations[operation];
      const response = await sendRequest(
        options,
        contract.path,
        { ...init, method: contract.method },
        "application/json",
      );
      const envelope = await readEnvelope(response);
      if (response.status !== 200) throw new ProtocolError("响应状态未在 operation 中声明");
      // operation 与 responseSchema 的对应关系来自同一生成表；运行时已逐项验证。
      return parseContract(contract.responseSchema, envelope).data as OperationResponses[K]["data"];
    },
  };
}
