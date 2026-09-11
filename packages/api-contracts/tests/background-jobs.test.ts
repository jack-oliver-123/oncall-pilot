import { describe, expect, it } from "vitest";
import { operations, parseContract } from "../src/index";

const job = {
  id: "job", ownerUserId: "owner", kind: "index", resourceType: "document", resourceId: "doc",
  status: "queued", payload: { text: "中文" }, attempt: 0, maxAttempts: 3, timeoutSeconds: 30,
  availableAt: "2026-09-10T00:00:00Z", leaseOwner: null, leaseExpiresAt: null,
  cancelRequestedAt: null, retryOfJobId: null, errorMessage: null,
  createdAt: "2026-09-10T00:00:00Z", updatedAt: "2026-09-10T00:00:00Z",
  startedAt: null, completedAt: null,
};
describe("持久后台任务合同", () => {
  it("登记查询、取消和重试操作", () => {
    expect(operations.listBackgroundJobs).toMatchObject({ path: "/background-jobs", method: "GET" });
    expect(operations.getBackgroundJob.path).toBe("/background-jobs/{id}");
    expect(operations.cancelBackgroundJob).toMatchObject({ path: "/background-jobs/{id}:cancel", method: "POST" });
    expect(operations.retryBackgroundJob).toMatchObject({ path: "/background-jobs/{id}:retry", method: "POST" });
  });
  it("接受五种状态，拒绝虚构字段和非法时间", () => {
    for (const status of ["queued", "running", "succeeded", "failed", "cancelled"]) {
      expect(parseContract("BackgroundJob", { ...job, status }).status).toBe(status);
    }
    for (const invalid of [{ ...job, status: "pending" }, { ...job, heartbeatAt: null },
      { ...job, result: {} }, { ...job, availableAt: "yesterday" }, { ...job, attempt: "0" }]) {
      expect(() => parseContract("BackgroundJob", invalid)).toThrow();
    }
  });
  it("支持有序持久事件的公开形状", () => {
    const event = { id: "e", jobId: "job", sequence: 1, eventType: "progress", payload: { progress: 1 }, createdAt: job.createdAt };
    expect(parseContract("BackgroundJobEvent", event)).toEqual(event);
  });
});
