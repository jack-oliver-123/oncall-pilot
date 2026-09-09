<script setup lang="ts">
import { useRoute } from "vue-router";
import { MessageSquare, BookOpen, Activity, Plug } from "lucide-vue-next";
import AppEmptyState from "../components/AppEmptyState.vue";
const route = useRoute();
const icons = { chat: MessageSquare, knowledge: BookOpen, aiops: Activity, mcp: Plug };
</script>
<template>
  <div class="route-placeholder">
    <AppEmptyState
      :title="String(route.meta.title) + '正在准备中'"
      :description="String(route.meta.description)"
      ><template #icon
        ><div class="placeholder-icon">
          <component
            :is="icons[route.name as keyof typeof icons]"
            :size="32"
            :stroke-width="1.4"
            aria-hidden="true"
          /></div></template
      ><span class="availability-label">尚未开放</span></AppEmptyState
    >
  </div>
</template>
