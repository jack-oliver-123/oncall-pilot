import { inject, type InjectionKey } from "vue";
import type { createApplication } from "./application";

export const applicationKey: InjectionKey<ReturnType<typeof createApplication>> =
  Symbol("application");
export function useApplication() {
  const application = inject(applicationKey);
  if (!application) throw new Error("应用尚未初始化");
  return application;
}
