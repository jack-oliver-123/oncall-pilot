<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";
import { Check, Info, CircleAlert, X } from "lucide-vue-next";
import { useFeedbackStore } from "../stores/feedback";
const feedback = useFeedbackStore();
const icons = { success: Check, info: Info, error: CircleAlert };
let timer: ReturnType<typeof setTimeout> | undefined;
function cancelTimer() {
  clearTimeout(timer);
  timer = undefined;
}
watch(
  () => feedback.message?.id,
  (id) => {
    cancelTimer();
    if (id !== undefined) timer = setTimeout(() => feedback.clear(), 3000);
  },
  { immediate: true, flush: "sync" },
);
onBeforeUnmount(cancelTimer);
</script>
<template>
  <div v-if="feedback.message" class="feedback" :class="'feedback-' + feedback.message.kind">
    <div
      :key="feedback.message.id"
      :role="feedback.message.kind === 'error' ? 'alert' : 'status'"
      :aria-live="feedback.message.kind === 'error' ? 'assertive' : 'polite'"
    >
      <component :is="icons[feedback.message.kind]" :size="20" aria-hidden="true" /><span>{{
        feedback.message.text
      }}</span>
    </div>
    <button type="button" aria-label="关闭提示" @click="feedback.clear">
      <X :size="18" aria-hidden="true" />
    </button>
  </div>
</template>
