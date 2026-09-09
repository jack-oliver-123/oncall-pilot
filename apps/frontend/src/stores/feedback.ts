import { defineStore } from "pinia";
import { ref } from "vue";

export type FeedbackKind = "success" | "info" | "error";
export const useFeedbackStore = defineStore("feedback", () => {
  const message = ref<{ id: number; kind: FeedbackKind; text: string } | null>(null);
  let nextId = 0;
  function show(kind: FeedbackKind, text: string) {
    message.value = { id: ++nextId, kind, text };
  }
  function clear() {
    message.value = null;
  }
  return { message, show, clear };
});
