import { describe, expect, expectTypeOf, it } from "vitest";
import document from "../openapi/foundation.openapi.json";
import { errorCatalog, operations, parseContract, type AuthUser, type LoginResponse } from "../src/index";

describe("认证合同", () => {
  it("登记四个操作与 bearer 安全边界", () => {
    expect(operations.registerUser).toMatchObject({ path: "/auth/register", method: "POST" });
    expect(operations.loginUser).toMatchObject({ path: "/auth/login", method: "POST" });
    expect(operations.logoutUser).toMatchObject({ path: "/auth/logout", method: "POST" });
    expect(operations.getCurrentUser).toMatchObject({ path: "/auth/me", method: "GET" });
    expect(document.components.securitySchemes.BearerAuth).toMatchObject({ type: "http", scheme: "bearer" });
    expect(document.paths["/auth/me"].get.security).toEqual([{ BearerAuth: [] }]);
    expect(document.paths["/auth/logout"].post.security).toEqual([{ BearerAuth: [] }]);
    expect(errorCatalog.AUTH_INVALID_CREDENTIALS.httpStatus).toBe(401);
    expect(errorCatalog.BUSINESS_EMAIL_ALREADY_EXISTS.httpStatus).toBe(409);
  });
  it("验证请求且不允许 owner 或私有字段", () => {
    const input = { email: " Person@Example.com ", password: "safe password" };
    expect(parseContract("RegisterRequest", input)).toEqual(input);
    expect(parseContract("LoginRequest", input)).toEqual(input);
    for (const invalid of [
      { ...input, password: "short" }, { ...input, password: "a".repeat(129) },
      { ...input, password: "😀".repeat(4) },
      { ...input, email: "bad" }, { ...input, ownerId: "other" },
    ]) expect(() => parseContract("RegisterRequest", invalid)).toThrow();
    expect(parseContract("RegisterRequest", { ...input, password: "😀".repeat(8) }).password).toBe("😀".repeat(8));
  });
  it("公开用户不暴露凭据且登录不声明过期", () => {
    const user = { id: "5b0eab8a-6c94-4b4a-bdb4-653a91271fe1", email: "person@example.com", createdAt: "2026-09-08T00:00:00Z" };
    expect(parseContract("AuthUser", user)).toEqual(user);
    expect(() => parseContract("AuthUser", { ...user, passwordHash: "secret" })).toThrow();
    const response = { ok: true, data: { user, token: "a".repeat(43), tokenType: "Bearer" }, meta: { requestId: "auth-1" } };
    expect(parseContract("LoginResponse", response)).toEqual(response);
    expect(() => parseContract("LoginResponse", { ...response, data: { ...response.data, expiresAt: null } })).toThrow();
    expectTypeOf<LoginResponse["data"]["user"]>().toEqualTypeOf<AuthUser>();
  });
});
