import { describe, expect, it, vi } from "vitest";
import { parseContract, type DocumentIndexStatus } from "../src";

describe("索引领域合同", () => {
  it.each<DocumentIndexStatus>([
    "pending",
    "running",
    "succeeded",
    "failed",
    "cancelled",
  ])("接受 %s", (status) => {
    expect(parseContract("DocumentIndexStatus", status)).toBe(status);
  });
  it("拒绝底层 queued 和旧 indexed", () => {
    for (const value of ["queued", "indexed", "completed"])
      expect(() => parseContract("DocumentIndexStatus", value)).toThrow();
  });
});
