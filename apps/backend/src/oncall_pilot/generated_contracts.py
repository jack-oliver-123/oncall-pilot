"""由 scripts/generate_contracts.py 生成，请修改 OpenAPI 源文件。"""
# ruff: noqa: E501
from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal, TypeAlias, cast, get_args, get_origin

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    WithJsonSchema,
    model_validator,
)


def valid_timestamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        raise ValueError("时间必须是带时区的 RFC3339")
    TypeAdapter[AwareDatetime](AwareDatetime).validate_json(json.dumps(value))
    return value


class WireModel(BaseModel):
    """严格公共 wire 模型。"""
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always", allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def strict_literals(cls, value: object) -> object:
        if isinstance(value, dict):
            fields = cast(dict[str, object], value)
            for key, field in cls.model_fields.items():
                annotation = field.annotation
                if get_origin(annotation) is Literal and key in fields:
                    allowed = get_args(annotation)
                    if not any(type(fields[key]) is type(v) and fields[key] == v for v in allowed):
                        raise ValueError("literal 字段不允许类型转换")
        return cast(object, value)


RequestId: TypeAlias = Annotated[str, Field(pattern='^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')]


EventId: TypeAlias = Annotated[str, Field(min_length=1, pattern='^[^\\r\\n\\u0000]+$')]


Timestamp: TypeAlias = Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]


class ResponseMeta(WireModel):
    """ResponseMeta 合同。"""
    requestId: RequestId


class HealthData(WireModel):
    """HealthData 合同。"""
    status: Literal['ok']


class ErrorAuthUnauthenticated(WireModel):
    """ErrorAuthUnauthenticated 合同。"""
    code: Literal['AUTH_UNAUTHENTICATED']
    category: Literal['AUTH']
    httpStatus: Literal[401]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorAuthForbidden(WireModel):
    """ErrorAuthForbidden 合同。"""
    code: Literal['AUTH_FORBIDDEN']
    category: Literal['AUTH']
    httpStatus: Literal[403]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorBusinessNotFound(WireModel):
    """ErrorBusinessNotFound 合同。"""
    code: Literal['BUSINESS_NOT_FOUND']
    category: Literal['BUSINESS']
    httpStatus: Literal[404]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorBusinessConflict(WireModel):
    """ErrorBusinessConflict 合同。"""
    code: Literal['BUSINESS_CONFLICT']
    category: Literal['BUSINESS']
    httpStatus: Literal[409]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorValidationBadRequest(WireModel):
    """ErrorValidationBadRequest 合同。"""
    code: Literal['VALIDATION_BAD_REQUEST']
    category: Literal['VALIDATION']
    httpStatus: Literal[400]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorValidationMethodNotAllowed(WireModel):
    """ErrorValidationMethodNotAllowed 合同。"""
    code: Literal['VALIDATION_METHOD_NOT_ALLOWED']
    category: Literal['VALIDATION']
    httpStatus: Literal[405]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorValidationRequestInvalid(WireModel):
    """ErrorValidationRequestInvalid 合同。"""
    code: Literal['VALIDATION_REQUEST_INVALID']
    category: Literal['VALIDATION']
    httpStatus: Literal[422]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorSystemRateLimited(WireModel):
    """ErrorSystemRateLimited 合同。"""
    code: Literal['SYSTEM_RATE_LIMITED']
    category: Literal['SYSTEM']
    httpStatus: Literal[429]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorSystemInternalError(WireModel):
    """ErrorSystemInternalError 合同。"""
    code: Literal['SYSTEM_INTERNAL_ERROR']
    category: Literal['SYSTEM']
    httpStatus: Literal[500]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorSystemUnavailable(WireModel):
    """ErrorSystemUnavailable 合同。"""
    code: Literal['SYSTEM_UNAVAILABLE']
    category: Literal['SYSTEM']
    httpStatus: Literal[503]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class AuthInvalidCredentialsError(WireModel):
    """AuthInvalidCredentialsError 合同。"""
    code: Literal['AUTH_INVALID_CREDENTIALS']
    category: Literal['AUTH']
    httpStatus: Literal[401]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


class BusinessEmailAlreadyExistsError(WireModel):
    """BusinessEmailAlreadyExistsError 合同。"""
    code: Literal['BUSINESS_EMAIL_ALREADY_EXISTS']
    category: Literal['BUSINESS']
    httpStatus: Literal[409]
    message: Annotated[str, Field(min_length=1)]
    details: dict[str, JsonValue] = Field(default_factory=dict)


ApiError: TypeAlias = Annotated[ErrorAuthUnauthenticated | ErrorAuthForbidden | ErrorBusinessNotFound | ErrorBusinessConflict | ErrorValidationBadRequest | ErrorValidationMethodNotAllowed | ErrorValidationRequestInvalid | ErrorSystemRateLimited | ErrorSystemInternalError | ErrorSystemUnavailable | AuthInvalidCredentialsError | BusinessEmailAlreadyExistsError, Field(discriminator='code')]


class ApiSuccess(WireModel):
    """ApiSuccess 合同。"""
    ok: Literal[True]
    data: JsonValue
    meta: ResponseMeta


class ApiFailure(WireModel):
    """ApiFailure 合同。"""
    ok: Literal[False]
    error: ApiError
    meta: ResponseMeta


ApiEnvelope: TypeAlias = ApiSuccess | ApiFailure


class HealthResponse(WireModel):
    """HealthResponse 合同。"""
    ok: Literal[True]
    data: HealthData
    meta: ResponseMeta


class ContentDelta(WireModel):
    """ContentDelta 合同。"""
    id: EventId
    type: Literal['content.delta']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    delta: str


class ReasoningDelta(WireModel):
    """ReasoningDelta 合同。"""
    id: EventId
    type: Literal['reasoning.delta']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    delta: str


class ToolStarted(WireModel):
    """ToolStarted 合同。"""
    id: EventId
    type: Literal['tool.call']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    callId: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    status: Literal['started']


class ToolDelta(WireModel):
    """ToolDelta 合同。"""
    id: EventId
    type: Literal['tool.call']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    callId: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    status: Literal['delta']
    delta: str


class ToolCompleted(WireModel):
    """ToolCompleted 合同。"""
    id: EventId
    type: Literal['tool.call']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    callId: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    status: Literal['completed']
    output: JsonValue


class ToolFailed(WireModel):
    """ToolFailed 合同。"""
    id: EventId
    type: Literal['tool.call']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    callId: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    status: Literal['failed']
    error: ApiError


ToolCall: TypeAlias = Annotated[ToolStarted | ToolDelta | ToolCompleted | ToolFailed, Field(discriminator='status')]


class ReferenceSource(WireModel):
    """ReferenceSource 合同。"""
    id: EventId
    type: Literal['reference.source']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    sourceId: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    url: Annotated[str, Field(min_length=1)]


class TaskStatus(WireModel):
    """TaskStatus 合同。"""
    id: EventId
    type: Literal['task.status']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    taskId: Annotated[str, Field(min_length=1)]
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']


class Report(WireModel):
    """Report 合同。"""
    id: EventId
    type: Literal['report']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    reportId: Annotated[str, Field(min_length=1)]
    title: Annotated[str, Field(min_length=1)]
    content: str


class Complete(WireModel):
    """Complete 合同。"""
    id: EventId
    type: Literal['complete']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    finishReason: Literal['stop', 'cancelled', 'error']


class ErrorEvent(WireModel):
    """ErrorEvent 合同。"""
    id: EventId
    type: Literal['error']
    channel: Literal['chat', 'aiops']
    timestamp: Timestamp
    error: ApiError


SseEvent: TypeAlias = Annotated[ContentDelta | ReasoningDelta | ToolCall | ReferenceSource | TaskStatus | Report | Complete | ErrorEvent, Field(discriminator='type')]


class AuthUser(WireModel):
    """AuthUser 合同。"""
    id: Annotated[str, Field(pattern='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
    email: Annotated[str, Field(pattern='^[^\\s@]+@[^\\s@]+$')]
    createdAt: Timestamp


class RegisterRequest(WireModel):
    """RegisterRequest 合同。"""
    email: Annotated[str, Field(pattern='^[ \\t]*[^\\s@]+@[^\\s@]+[ \\t]*$')]
    password: Annotated[str, Field(pattern='^[\\s\\S]{8,128}$')]


class LoginRequest(WireModel):
    """LoginRequest 合同。"""
    email: Annotated[str, Field(pattern='^[ \\t]*[^\\s@]+@[^\\s@]+[ \\t]*$')]
    password: Annotated[str, Field(pattern='^[\\s\\S]{8,128}$')]


class LoginData(WireModel):
    """LoginData 合同。"""
    user: AuthUser
    token: Annotated[str, Field(pattern='^[A-Za-z0-9_-]{43}$')]
    tokenType: Literal['Bearer']


class UserResponse(WireModel):
    """UserResponse 合同。"""
    ok: Literal[True]
    data: AuthUser
    meta: ResponseMeta


class LoginResponse(WireModel):
    """LoginResponse 合同。"""
    ok: Literal[True]
    data: LoginData
    meta: ResponseMeta


class LogoutResponse(WireModel):
    """LogoutResponse 合同。"""
    ok: Literal[True]
    data: None
    meta: ResponseMeta


BackgroundJobStatus: TypeAlias = Literal['queued', 'running', 'succeeded', 'failed', 'cancelled']


class BackgroundJob(WireModel):
    """BackgroundJob 合同。"""
    id: str
    ownerUserId: str
    kind: str
    resourceType: str | None
    resourceId: str | None
    leaseOwner: str | None
    retryOfJobId: str | None
    errorMessage: str | None
    status: BackgroundJobStatus
    payload: JsonValue
    attempt: int
    maxAttempts: int
    timeoutSeconds: float
    availableAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]
    createdAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]
    updatedAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]
    leaseExpiresAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})] | None
    cancelRequestedAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})] | None
    startedAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})] | None
    completedAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})] | None


class BackgroundJobEvent(WireModel):
    """BackgroundJobEvent 合同。"""
    id: str
    jobId: str
    sequence: int
    eventType: str
    payload: JsonValue
    createdAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]


class BackgroundJobResponse(WireModel):
    """BackgroundJobResponse 合同。"""
    ok: Literal[True]
    data: BackgroundJob
    meta: ResponseMeta


class BackgroundJobListResponse(WireModel):
    """BackgroundJobListResponse 合同。"""
    ok: Literal[True]
    data: list[BackgroundJob]
    meta: ResponseMeta


class KnowledgeBase(WireModel):
    """KnowledgeBase 合同。"""
    id: str
    ownerUserId: str
    createdAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]


class KnowledgeBaseListResponse(WireModel):
    """KnowledgeBaseListResponse 合同。"""
    ok: Literal[True]
    data: list[KnowledgeBase]
    meta: ResponseMeta


class ChunkPreview(WireModel):
    """ChunkPreview 合同。"""
    index: int
    excerpt: Annotated[str, Field(max_length=400)]
    metadata: JsonValue


class ChunkPreviewResponse(WireModel):
    """ChunkPreviewResponse 合同。"""
    ok: Literal[True]
    data: Annotated[list[ChunkPreview], Field(max_length=12)]
    meta: ResponseMeta


class FixedCharacterConfig(WireModel):
    """FixedCharacterConfig 合同。"""
    strategy: Literal['fixed-character']
    maxCharacters: Annotated[int, Field(ge=1)]
    overlap: Annotated[int, Field(ge=0)]


class MarkdownHeadingConfig(WireModel):
    """MarkdownHeadingConfig 合同。"""
    strategy: Literal['markdown-heading']


class ParagraphConfig(WireModel):
    """ParagraphConfig 合同。"""
    strategy: Literal['paragraph']


ChunkingConfig: TypeAlias = Annotated[FixedCharacterConfig | MarkdownHeadingConfig | ParagraphConfig, Field(discriminator='strategy')]


class KnowledgeDocument(WireModel):
    """KnowledgeDocument 合同。"""
    id: str
    ownerUserId: str
    knowledgeBaseId: str
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    size: Annotated[int, Field(ge=1, le=10485760)]
    mimeType: str
    sha256: Annotated[str, Field(pattern='^[0-9a-f]{64}$')]
    uploadedAt: Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]
    indexStatus: Literal['pending', 'indexed', 'failed']
    chunkingConfig: ChunkingConfig


class KnowledgeDocumentListResponse(WireModel):
    """KnowledgeDocumentListResponse 合同。"""
    ok: Literal[True]
    data: list[KnowledgeDocument]
    meta: ResponseMeta


class KnowledgeDocumentResponse(WireModel):
    """KnowledgeDocumentResponse 合同。"""
    ok: Literal[True]
    data: KnowledgeDocument
    meta: ResponseMeta

DOCUMENT_UPLOAD_POLICY: dict[str, Any] = {'maxBytes': 10485760,
 'extensions': ['.md', '.pdf'],
 'markdownMimeTypes': ['text/markdown', 'text/plain'],
 'pdfMimeType': 'application/pdf',
 'defaultMaxCharacters': 1200,
 'defaultOverlap': 200,
 'maxPreviewChunks': 12,
 'maxExcerptCharacters': 400}

ErrorCode: TypeAlias = Literal['AUTH_UNAUTHENTICATED', 'AUTH_FORBIDDEN', 'BUSINESS_NOT_FOUND', 'BUSINESS_CONFLICT', 'VALIDATION_BAD_REQUEST', 'VALIDATION_METHOD_NOT_ALLOWED', 'VALIDATION_REQUEST_INVALID', 'SYSTEM_RATE_LIMITED', 'SYSTEM_INTERNAL_ERROR', 'SYSTEM_UNAVAILABLE', 'AUTH_INVALID_CREDENTIALS', 'BUSINESS_EMAIL_ALREADY_EXISTS']

ERROR_CATALOG: dict[ErrorCode, dict[str, JsonValue]] = {'AUTH_UNAUTHENTICATED': {'code': 'AUTH_UNAUTHENTICATED',
                          'category': 'AUTH',
                          'httpStatus': 401,
                          'message': '请先登录。'},
 'AUTH_FORBIDDEN': {'code': 'AUTH_FORBIDDEN',
                    'category': 'AUTH',
                    'httpStatus': 403,
                    'message': '没有执行此操作的权限。'},
 'BUSINESS_NOT_FOUND': {'code': 'BUSINESS_NOT_FOUND',
                        'category': 'BUSINESS',
                        'httpStatus': 404,
                        'message': '请求的资源不存在。'},
 'BUSINESS_CONFLICT': {'code': 'BUSINESS_CONFLICT',
                       'category': 'BUSINESS',
                       'httpStatus': 409,
                       'message': '当前状态无法执行此操作。'},
 'VALIDATION_BAD_REQUEST': {'code': 'VALIDATION_BAD_REQUEST',
                            'category': 'VALIDATION',
                            'httpStatus': 400,
                            'message': '请求格式不正确。'},
 'VALIDATION_METHOD_NOT_ALLOWED': {'code': 'VALIDATION_METHOD_NOT_ALLOWED',
                                   'category': 'VALIDATION',
                                   'httpStatus': 405,
                                   'message': '不支持此请求方式。'},
 'VALIDATION_REQUEST_INVALID': {'code': 'VALIDATION_REQUEST_INVALID',
                                'category': 'VALIDATION',
                                'httpStatus': 422,
                                'message': '请求参数不符合要求。'},
 'SYSTEM_RATE_LIMITED': {'code': 'SYSTEM_RATE_LIMITED',
                         'category': 'SYSTEM',
                         'httpStatus': 429,
                         'message': '请求过于频繁，请稍后重试。'},
 'SYSTEM_INTERNAL_ERROR': {'code': 'SYSTEM_INTERNAL_ERROR',
                           'category': 'SYSTEM',
                           'httpStatus': 500,
                           'message': '服务暂时出现问题，请稍后重试。'},
 'SYSTEM_UNAVAILABLE': {'code': 'SYSTEM_UNAVAILABLE',
                        'category': 'SYSTEM',
                        'httpStatus': 503,
                        'message': '服务暂时不可用，请稍后重试。'},
 'AUTH_INVALID_CREDENTIALS': {'code': 'AUTH_INVALID_CREDENTIALS',
                              'category': 'AUTH',
                              'httpStatus': 401,
                              'message': '邮箱或密码错误。'},
 'BUSINESS_EMAIL_ALREADY_EXISTS': {'code': 'BUSINESS_EMAIL_ALREADY_EXISTS',
                                   'category': 'BUSINESS',
                                   'httpStatus': 409,
                                   'message': '该邮箱已注册。'}}

OPERATION_DOCS: dict[str, dict[str, Any]] = {'getHealth': {'parameters': [{'name': 'X-Request-ID',
                               'in': 'header',
                               'required': False,
                               'description': '合法值透传；缺失或非法值生成新的标识。',
                               'schema': {'type': 'string'}}],
               'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                      'schema': {'type': 'string',
                                                                                 'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'registerUser': {'parameters': [{'name': 'X-Request-ID',
                                  'in': 'header',
                                  'required': False,
                                  'description': '合法值透传；缺失或非法值生成新的标识。',
                                  'schema': {'type': 'string'}}],
                  'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                     'schema': {'type': 'string',
                                                                                'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                     'schema': {'type': 'string',
                                                                                'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                     'schema': {'type': 'string',
                                                                                'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                '409': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                     'schema': {'type': 'string',
                                                                                'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'loginUser': {'parameters': [{'name': 'X-Request-ID',
                               'in': 'header',
                               'required': False,
                               'description': '合法值透传；缺失或非法值生成新的标识。',
                               'schema': {'type': 'string'}}],
               'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                      'schema': {'type': 'string',
                                                                                 'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                             '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                  'schema': {'type': 'string',
                                                                             'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'logoutUser': {'parameters': [{'name': 'X-Request-ID',
                                'in': 'header',
                                'required': False,
                                'description': '合法值透传；缺失或非法值生成新的标识。',
                                'schema': {'type': 'string'}}],
                'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                   'schema': {'type': 'string',
                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                              '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                   'schema': {'type': 'string',
                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                              '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                   'schema': {'type': 'string',
                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                              'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                              '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                   'schema': {'type': 'string',
                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                  'WWW-Authenticate': {'description': 'HTTP '
                                                                                      'bearer '
                                                                                      '认证挑战。',
                                                                       'schema': {'type': 'string'}}}},
                              '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                   'schema': {'type': 'string',
                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'getCurrentUser': {'parameters': [{'name': 'X-Request-ID',
                                    'in': 'header',
                                    'required': False,
                                    'description': '合法值透传；缺失或非法值生成新的标识。',
                                    'schema': {'type': 'string'}}],
                    'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                  '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                  '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                  'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                  '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                      'WWW-Authenticate': {'description': 'HTTP '
                                                                                          'bearer '
                                                                                          '认证挑战。',
                                                                           'schema': {'type': 'string'}}}},
                                  '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                       'schema': {'type': 'string',
                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'listBackgroundJobs': {'parameters': [{'name': 'X-Request-ID',
                                        'in': 'header',
                                        'required': False,
                                        'description': '合法值透传；缺失或非法值生成新的标识。',
                                        'schema': {'type': 'string'}}],
                        'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                          'WWW-Authenticate': {'description': 'HTTP '
                                                                                              'bearer '
                                                                                              '认证挑战。',
                                                                               'schema': {'type': 'string'}}}},
                                      '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'getBackgroundJob': {'parameters': [{'name': 'id',
                                      'in': 'path',
                                      'required': True,
                                      'schema': {'type': 'string'}},
                                     {'name': 'X-Request-ID',
                                      'in': 'header',
                                      'required': False,
                                      'description': '合法值透传；缺失或非法值生成新的标识。',
                                      'schema': {'type': 'string'}}],
                      'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                    '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                    '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                    'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                    '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                        'WWW-Authenticate': {'description': 'HTTP '
                                                                                            'bearer '
                                                                                            '认证挑战。',
                                                                             'schema': {'type': 'string'}}}},
                                    '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                         'schema': {'type': 'string',
                                                                                    'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'cancelBackgroundJob': {'parameters': [{'name': 'id',
                                         'in': 'path',
                                         'required': True,
                                         'schema': {'type': 'string'}},
                                        {'name': 'X-Request-ID',
                                         'in': 'header',
                                         'required': False,
                                         'description': '合法值透传；缺失或非法值生成新的标识。',
                                         'schema': {'type': 'string'}}],
                         'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                       '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                       '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                       'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                       '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                           'WWW-Authenticate': {'description': 'HTTP '
                                                                                               'bearer '
                                                                                               '认证挑战。',
                                                                                'schema': {'type': 'string'}}}},
                                       '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                       '409': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                            'schema': {'type': 'string',
                                                                                       'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'retryBackgroundJob': {'parameters': [{'name': 'id',
                                        'in': 'path',
                                        'required': True,
                                        'schema': {'type': 'string'}},
                                       {'name': 'X-Request-ID',
                                        'in': 'header',
                                        'required': False,
                                        'description': '合法值透传；缺失或非法值生成新的标识。',
                                        'schema': {'type': 'string'}}],
                        'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                          'WWW-Authenticate': {'description': 'HTTP '
                                                                                              'bearer '
                                                                                              '认证挑战。',
                                                                               'schema': {'type': 'string'}}}},
                                      '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '409': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'listKnowledgeBases': {'parameters': [{'name': 'X-Request-ID',
                                        'in': 'header',
                                        'required': False,
                                        'description': '合法值透传；缺失或非法值生成新的标识。',
                                        'schema': {'type': 'string'}}],
                        'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                          'WWW-Authenticate': {'description': 'HTTP '
                                                                                              'bearer '
                                                                                              '认证挑战。',
                                                                               'schema': {'type': 'string'}}}},
                                      '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                           'schema': {'type': 'string',
                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                      'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'listKnowledgeDocuments': {'parameters': [{'name': 'kb',
                                            'in': 'path',
                                            'required': True,
                                            'schema': {'type': 'string'}},
                                           {'name': 'X-Request-ID',
                                            'in': 'header',
                                            'required': False,
                                            'description': '合法值透传；缺失或非法值生成新的标识。',
                                            'schema': {'type': 'string'}}],
                            'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                          '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                              'WWW-Authenticate': {'description': 'HTTP '
                                                                                                  'bearer '
                                                                                                  '认证挑战。',
                                                                                   'schema': {'type': 'string'}}}},
                                          '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                          '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                          '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                               'schema': {'type': 'string',
                                                                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                          'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                   'schema': {'type': 'string',
                                                                                              'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'uploadKnowledgeDocument': {'parameters': [{'name': 'kb',
                                             'in': 'path',
                                             'required': True,
                                             'schema': {'type': 'string'}},
                                            {'name': 'X-Request-ID',
                                             'in': 'header',
                                             'required': False,
                                             'description': '合法值透传；缺失或非法值生成新的标识。',
                                             'schema': {'type': 'string'}}],
                             'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                               'WWW-Authenticate': {'description': 'HTTP '
                                                                                                   'bearer '
                                                                                                   '认证挑战。',
                                                                                    'schema': {'type': 'string'}}}},
                                           '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '400': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '409': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                    'schema': {'type': 'string',
                                                                                               'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'getKnowledgeDocument': {'parameters': [{'name': 'kb',
                                          'in': 'path',
                                          'required': True,
                                          'schema': {'type': 'string'}},
                                         {'name': 'document',
                                          'in': 'path',
                                          'required': True,
                                          'schema': {'type': 'string'}},
                                         {'name': 'X-Request-ID',
                                          'in': 'header',
                                          'required': False,
                                          'description': '合法值透传；缺失或非法值生成新的标识。',
                                          'schema': {'type': 'string'}}],
                          'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                        '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                            'WWW-Authenticate': {'description': 'HTTP '
                                                                                                'bearer '
                                                                                                '认证挑战。',
                                                                                 'schema': {'type': 'string'}}}},
                                        '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                        '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                        '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                             'schema': {'type': 'string',
                                                                                        'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                        'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                 'schema': {'type': 'string',
                                                                                            'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'deleteKnowledgeDocument': {'parameters': [{'name': 'kb',
                                             'in': 'path',
                                             'required': True,
                                             'schema': {'type': 'string'}},
                                            {'name': 'document',
                                             'in': 'path',
                                             'required': True,
                                             'schema': {'type': 'string'}},
                                            {'name': 'X-Request-ID',
                                             'in': 'header',
                                             'required': False,
                                             'description': '合法值透传；缺失或非法值生成新的标识。',
                                             'schema': {'type': 'string'}}],
                             'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                               'WWW-Authenticate': {'description': 'HTTP '
                                                                                                   'bearer '
                                                                                                   '认证挑战。',
                                                                                    'schema': {'type': 'string'}}}},
                                           '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                'schema': {'type': 'string',
                                                                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                           'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                    'schema': {'type': 'string',
                                                                                               'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}},
 'previewKnowledgeDocumentChunks': {'parameters': [{'name': 'kb',
                                                    'in': 'path',
                                                    'required': True,
                                                    'schema': {'type': 'string'}},
                                                   {'name': 'document',
                                                    'in': 'path',
                                                    'required': True,
                                                    'schema': {'type': 'string'}},
                                                   {'name': 'X-Request-ID',
                                                    'in': 'header',
                                                    'required': False,
                                                    'description': '合法值透传；缺失或非法值生成新的标识。',
                                                    'schema': {'type': 'string'}}],
                                    'responses': {'200': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                       'schema': {'type': 'string',
                                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                                  '401': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                       'schema': {'type': 'string',
                                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                                                      'WWW-Authenticate': {'description': 'HTTP '
                                                                                                          'bearer '
                                                                                                          '认证挑战。',
                                                                                           'schema': {'type': 'string'}}}},
                                                  '403': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                       'schema': {'type': 'string',
                                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                                  '422': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                       'schema': {'type': 'string',
                                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                                  '500': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                       'schema': {'type': 'string',
                                                                                                  'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}},
                                                  'default': {'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                                                           'schema': {'type': 'string',
                                                                                                      'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}}}}}}

PROTECTED_OPERATION: dict[str, Any] = {'security': [{'BearerAuth': []}],
 'responses': {'401': {'description': '缺少有效认证会话。',
                       'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                    'schema': {'type': 'string',
                                                               'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}},
                                   'WWW-Authenticate': {'description': 'HTTP bearer 认证挑战。',
                                                        'schema': {'type': 'string'}}},
                       'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiFailure'}}}},
               '403': {'description': '受保护资源不可访问或不存在；不披露资源细节。',
                       'headers': {'X-Request-ID': {'description': '请求关联标识',
                                                    'schema': {'type': 'string',
                                                               'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'}}},
                       'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiFailure'}}}}}}
