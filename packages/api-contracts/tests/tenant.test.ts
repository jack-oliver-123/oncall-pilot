import { describe, expect, it } from "vitest";
import document from "../openapi/foundation.openapi.json";
import { errorCatalog, parseContract, protectedOperation } from "../src/index";

describe("受保护操作复用边界", () => {
  it("非公开操作均声明 bearer 和共享 401/403", () => {
    expect(protectedOperation).toEqual(document["x-protected-operation"]);
    expect(document["x-public-operations"]).toEqual(["getHealth", "registerUser", "loginUser"]);
    for (const methods of Object.values(document.paths)) {
      for (const operation of Object.values(methods)) {
        if (document["x-public-operations"].includes(operation.operationId)) continue;
        expect(operation).toMatchObject(protectedOperation);
      }
    }
    for (const response of Object.values(document.components.responses)) {
      expect(response.content["application/json"].schema).toEqual({ $ref: "#/components/schemas/ApiFailure" });
    }
  });
  it("403 使用稳定且不包含资源细节的错误", () => {
    expect(errorCatalog.AUTH_FORBIDDEN.httpStatus).toBe(403);
    expect(errorCatalog.AUTH_UNAUTHENTICATED.httpStatus).toBe(401);
    const failure = { ok: false, error: errorCatalog.AUTH_FORBIDDEN, meta: { requestId: "scope-test" } };
    expect(parseContract("ApiFailure", failure)).toEqual(failure);
    expect(Object.keys(failure.error).sort()).toEqual(["category", "code", "httpStatus", "message"]);
  });
});
