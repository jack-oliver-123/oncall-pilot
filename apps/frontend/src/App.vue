<script setup lang="ts">
import { RadioTower } from "lucide-vue-next";

import { publicConfig } from "./config";
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand-lockup">
        <RadioTower class="brand-icon" :size="24" :stroke-width="1.8" aria-hidden="true" />
        <span class="brand-name" data-testid="brand">{{ publicConfig.frontend.title }}</span>
      </div>
    </header>

    <main class="workspace-shell">
      <div class="handover-rail" aria-hidden="true">
        <span class="handover-line"></span>
      </div>

      <section class="workspace" aria-labelledby="workspace-title">
        <h1 id="workspace-title">值班工作台</h1>
        <div class="workspace-copy">
          <h2>工作台正在准备中</h2>
          <p>当前版本暂未开放业务操作。</p>
        </div>
      </section>
    </main>
  </div>
</template>
