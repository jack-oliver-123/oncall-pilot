<script setup lang="ts">
import { CircleAlert } from "lucide-vue-next";
defineProps<{ message: string; retry?: boolean }>();
defineEmits<{ retry: [] }>();
</script>
<template>
  <div class="error-state">
    <p role="alert"><CircleAlert :size="18" aria-hidden="true" />{{ message }}</p>
    <button v-if="retry" type="button" class="secondary-button" @click="$emit('retry')">
      重试
    </button>
  </div>
</template>
