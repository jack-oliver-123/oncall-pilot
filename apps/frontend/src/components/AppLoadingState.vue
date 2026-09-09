<script setup lang="ts">
import { LoaderCircle } from "lucide-vue-next";
withDefaults(defineProps<{ text?: string }>(), { text: "正在加载，请稍候…" });
</script>
<template>
  <div class="app-state" role="status" aria-live="polite" aria-busy="true">
    <LoaderCircle class="spin" :size="24" aria-hidden="true" />
    <p>{{ text }}</p>
  </div>
</template>
