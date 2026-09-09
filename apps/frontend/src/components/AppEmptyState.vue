<script setup lang="ts">
import { Inbox } from "lucide-vue-next";
defineProps<{ title: string; description: string }>();
</script>
<template>
  <section class="app-state empty-state" role="status" aria-live="polite">
    <slot name="icon"><Inbox :size="32" aria-hidden="true" /></slot>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <slot />
  </section>
</template>
