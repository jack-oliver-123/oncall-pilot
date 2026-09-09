<script setup lang="ts">
import { CircleCheck, CircleAlert, Clock3, LoaderCircle } from "lucide-vue-next";
defineProps<{ status: "idle" | "loading" | "success" | "error"; text: string }>();
const icons = { idle: Clock3, loading: LoaderCircle, success: CircleCheck, error: CircleAlert };
</script>
<template>
  <span class="status-badge" :class="'status-' + status" role="status" aria-live="polite"
    ><component
      :is="icons[status]"
      :size="15"
      :class="{ spin: status === 'loading' }"
      aria-hidden="true"
    />{{ text }}</span
  >
</template>
