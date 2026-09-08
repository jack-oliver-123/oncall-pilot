// 由 scripts/generate_contracts.py 生成，请修改 OpenAPI 源文件。
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export type RequestId = string;

export type EventId = string;

export type Timestamp = string;

export type ResponseMeta = {
  "requestId": RequestId;
};

export type HealthData = {
  "status": "ok";
};

export type ErrorAuthUnauthenticated = {
  "code": "AUTH_UNAUTHENTICATED";
  "category": "AUTH";
  "httpStatus": 401;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorAuthForbidden = {
  "code": "AUTH_FORBIDDEN";
  "category": "AUTH";
  "httpStatus": 403;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorBusinessNotFound = {
  "code": "BUSINESS_NOT_FOUND";
  "category": "BUSINESS";
  "httpStatus": 404;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorBusinessConflict = {
  "code": "BUSINESS_CONFLICT";
  "category": "BUSINESS";
  "httpStatus": 409;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorValidationBadRequest = {
  "code": "VALIDATION_BAD_REQUEST";
  "category": "VALIDATION";
  "httpStatus": 400;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorValidationMethodNotAllowed = {
  "code": "VALIDATION_METHOD_NOT_ALLOWED";
  "category": "VALIDATION";
  "httpStatus": 405;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorValidationRequestInvalid = {
  "code": "VALIDATION_REQUEST_INVALID";
  "category": "VALIDATION";
  "httpStatus": 422;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorSystemRateLimited = {
  "code": "SYSTEM_RATE_LIMITED";
  "category": "SYSTEM";
  "httpStatus": 429;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorSystemInternalError = {
  "code": "SYSTEM_INTERNAL_ERROR";
  "category": "SYSTEM";
  "httpStatus": 500;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ErrorSystemUnavailable = {
  "code": "SYSTEM_UNAVAILABLE";
  "category": "SYSTEM";
  "httpStatus": 503;
  "message": string;
  "details"?: Record<string, JsonValue>;
};

export type ApiError = ErrorAuthUnauthenticated | ErrorAuthForbidden | ErrorBusinessNotFound | ErrorBusinessConflict | ErrorValidationBadRequest | ErrorValidationMethodNotAllowed | ErrorValidationRequestInvalid | ErrorSystemRateLimited | ErrorSystemInternalError | ErrorSystemUnavailable;

export type ApiSuccess = {
  "ok": true;
  "data": JsonValue;
  "meta": ResponseMeta;
};

export type ApiFailure = {
  "ok": false;
  "error": ApiError;
  "meta": ResponseMeta;
};

export type ApiEnvelope = ApiSuccess | ApiFailure;

export type HealthResponse = {
  "ok": true;
  "data": HealthData;
  "meta": ResponseMeta;
};

export type ContentDelta = {
  "id": EventId;
  "type": "content.delta";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "delta": string;
};

export type ReasoningDelta = {
  "id": EventId;
  "type": "reasoning.delta";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "delta": string;
};

export type ToolStarted = {
  "id": EventId;
  "type": "tool.call";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "callId": string;
  "name": string;
  "status": "started";
};

export type ToolDelta = {
  "id": EventId;
  "type": "tool.call";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "callId": string;
  "name": string;
  "status": "delta";
  "delta": string;
};

export type ToolCompleted = {
  "id": EventId;
  "type": "tool.call";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "callId": string;
  "name": string;
  "status": "completed";
  "output": JsonValue;
};

export type ToolFailed = {
  "id": EventId;
  "type": "tool.call";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "callId": string;
  "name": string;
  "status": "failed";
  "error": ApiError;
};

export type ToolCall = ToolStarted | ToolDelta | ToolCompleted | ToolFailed;

export type ReferenceSource = {
  "id": EventId;
  "type": "reference.source";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "sourceId": string;
  "title": string;
  "url": string;
};

export type TaskStatus = {
  "id": EventId;
  "type": "task.status";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "taskId": string;
  "status": "queued" | "running" | "completed" | "failed" | "cancelled";
};

export type Report = {
  "id": EventId;
  "type": "report";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "reportId": string;
  "title": string;
  "content": string;
};

export type Complete = {
  "id": EventId;
  "type": "complete";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "finishReason": "stop" | "cancelled" | "error";
};

export type ErrorEvent = {
  "id": EventId;
  "type": "error";
  "channel": "chat" | "aiops";
  "timestamp": Timestamp;
  "error": ApiError;
};

export type SseEvent = ContentDelta | ReasoningDelta | ToolCall | ReferenceSource | TaskStatus | Report | Complete | ErrorEvent;

export const errorCatalog = {
  "AUTH_UNAUTHENTICATED": {
    "code": "AUTH_UNAUTHENTICATED",
    "category": "AUTH",
    "httpStatus": 401,
    "message": "请先登录。"
  },
  "AUTH_FORBIDDEN": {
    "code": "AUTH_FORBIDDEN",
    "category": "AUTH",
    "httpStatus": 403,
    "message": "没有执行此操作的权限。"
  },
  "BUSINESS_NOT_FOUND": {
    "code": "BUSINESS_NOT_FOUND",
    "category": "BUSINESS",
    "httpStatus": 404,
    "message": "请求的资源不存在。"
  },
  "BUSINESS_CONFLICT": {
    "code": "BUSINESS_CONFLICT",
    "category": "BUSINESS",
    "httpStatus": 409,
    "message": "当前状态无法执行此操作。"
  },
  "VALIDATION_BAD_REQUEST": {
    "code": "VALIDATION_BAD_REQUEST",
    "category": "VALIDATION",
    "httpStatus": 400,
    "message": "请求格式不正确。"
  },
  "VALIDATION_METHOD_NOT_ALLOWED": {
    "code": "VALIDATION_METHOD_NOT_ALLOWED",
    "category": "VALIDATION",
    "httpStatus": 405,
    "message": "不支持此请求方式。"
  },
  "VALIDATION_REQUEST_INVALID": {
    "code": "VALIDATION_REQUEST_INVALID",
    "category": "VALIDATION",
    "httpStatus": 422,
    "message": "请求参数不符合要求。"
  },
  "SYSTEM_RATE_LIMITED": {
    "code": "SYSTEM_RATE_LIMITED",
    "category": "SYSTEM",
    "httpStatus": 429,
    "message": "请求过于频繁，请稍后重试。"
  },
  "SYSTEM_INTERNAL_ERROR": {
    "code": "SYSTEM_INTERNAL_ERROR",
    "category": "SYSTEM",
    "httpStatus": 500,
    "message": "服务暂时出现问题，请稍后重试。"
  },
  "SYSTEM_UNAVAILABLE": {
    "code": "SYSTEM_UNAVAILABLE",
    "category": "SYSTEM",
    "httpStatus": 503,
    "message": "服务暂时不可用，请稍后重试。"
  }
} as const;
export type ErrorCode = keyof typeof errorCatalog;
export const operations = {
  "getHealth": {
    "path": "/health",
    "method": "GET",
    "responseSchema": "HealthResponse"
  }
} as const;
export interface OperationResponses {
  getHealth: HealthResponse;
}
export interface SchemaTypes {
  RequestId: RequestId;
  EventId: EventId;
  Timestamp: Timestamp;
  ResponseMeta: ResponseMeta;
  HealthData: HealthData;
  ErrorAuthUnauthenticated: ErrorAuthUnauthenticated;
  ErrorAuthForbidden: ErrorAuthForbidden;
  ErrorBusinessNotFound: ErrorBusinessNotFound;
  ErrorBusinessConflict: ErrorBusinessConflict;
  ErrorValidationBadRequest: ErrorValidationBadRequest;
  ErrorValidationMethodNotAllowed: ErrorValidationMethodNotAllowed;
  ErrorValidationRequestInvalid: ErrorValidationRequestInvalid;
  ErrorSystemRateLimited: ErrorSystemRateLimited;
  ErrorSystemInternalError: ErrorSystemInternalError;
  ErrorSystemUnavailable: ErrorSystemUnavailable;
  ApiError: ApiError;
  ApiSuccess: ApiSuccess;
  ApiFailure: ApiFailure;
  ApiEnvelope: ApiEnvelope;
  HealthResponse: HealthResponse;
  ContentDelta: ContentDelta;
  ReasoningDelta: ReasoningDelta;
  ToolStarted: ToolStarted;
  ToolDelta: ToolDelta;
  ToolCompleted: ToolCompleted;
  ToolFailed: ToolFailed;
  ToolCall: ToolCall;
  ReferenceSource: ReferenceSource;
  TaskStatus: TaskStatus;
  Report: Report;
  Complete: Complete;
  ErrorEvent: ErrorEvent;
  SseEvent: SseEvent;
}
