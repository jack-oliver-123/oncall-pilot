import { describe, expect, expectTypeOf, it } from "vitest";

import type { HealthResponse } from "../src/index";

describe("HealthResponse", () => {
  it("固定健康检查的 wire shape", () => {
    const response = { status: "ok" } satisfies HealthResponse;

    expect(response).toEqual({ status: "ok" });
    expectTypeOf<HealthResponse>().toEqualTypeOf<{ status: "ok" }>();
  });
});
