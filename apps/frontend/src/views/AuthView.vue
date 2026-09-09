<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { RadioTower, ArrowRight } from "lucide-vue-next";
import { useApplication } from "../context";
import { publicConfig } from "../config";
import { safeRedirect } from "../router";
import { ApiClientError } from "../transport/apiClient";
import AppErrorState from "../components/AppErrorState.vue";
const { auth, feedback } = useApplication();
const route = useRoute();
const router = useRouter();
const registering = computed(() => route.name === "register");
const email = ref("");
const password = ref("");
const confirmation = ref("");
const busy = ref(false);
const error = ref("");
let version = 0;
watch(
  () => route.name,
  () => {
    version++;
    password.value = "";
    confirmation.value = "";
    error.value = "";
    busy.value = false;
  },
);
async function submit() {
  if (busy.value) return;
  error.value = "";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    error.value = "请输入有效的邮箱地址。";
    return;
  }
  if (password.value.length < 8 || password.value.length > 128) {
    error.value = "密码长度应为 8–128 个字符。";
    return;
  }
  if (registering.value && password.value !== confirmation.value) {
    error.value = "两次输入的密码不一致。";
    return;
  }
  busy.value = true;
  const current = ++version;
  const destination = safeRedirect(router, route.query.redirect);
  const isRegistration = registering.value;
  try {
    const input = { email: email.value.trim(), password: password.value };
    if (isRegistration) {
      await auth.register(input);
      if (current !== version) return;
      feedback.show("success", "注册成功，请登录。");
      await router.replace({ name: "login", query: { redirect: destination } });
    } else {
      await auth.login(input);
      if (current !== version || auth.state.status !== "authenticated") return;
      await router.replace(destination);
    }
  } catch (cause) {
    if (current === version)
      error.value =
        cause instanceof ApiClientError ? cause.message : "暂时无法完成请求，请检查连接后重试。";
  } finally {
    if (current === version) {
      busy.value = false;
      password.value = "";
      confirmation.value = "";
    }
  }
}
</script>
<template>
  <main class="auth-page">
    <section class="auth-intro" aria-label="值班工作台介绍">
      <div class="brand-lockup">
        <RadioTower :size="27" aria-hidden="true" /><span class="brand-name" data-testid="brand">{{
          publicConfig.frontend.title
        }}</span>
      </div>
      <div class="intro-copy">
        <span class="eyebrow">值班工作台</span>
        <h2>从这里，<br />接续你的值班工作。</h2>
        <p>一个清晰、有序的工作空间。<br />登录后进入你的专属工作台。</p>
      </div>
      <p class="intro-note">对话、知识库、智能运维与工具连接将逐步开放。</p>
    </section>
    <section class="auth-form-area" aria-labelledby="auth-title">
      <form class="auth-form" novalidate :aria-busy="busy" @submit.prevent="submit">
        <span class="eyebrow">{{ registering ? "开始使用" : "欢迎回来" }}</span>
        <h1 id="auth-title">{{ registering ? "创建账号" : "登录工作台" }}</h1>
        <p class="form-description">
          {{ registering ? "使用邮箱创建你的值班账号。" : "使用你的邮箱和密码继续。" }}
        </p>
        <fieldset :disabled="busy">
          <label for="email">邮箱</label
          ><input
            id="email"
            v-model="email"
            type="email"
            autocomplete="username"
            required
            maxlength="254"
            placeholder="name@company.com"
          />
          <label for="password">密码</label
          ><input
            id="password"
            v-model="password"
            type="password"
            :autocomplete="registering ? 'new-password' : 'current-password'"
            required
            minlength="8"
            maxlength="128"
            aria-describedby="password-hint"
          />
          <p id="password-hint" class="field-hint">8–128 个字符</p>
          <template v-if="registering"
            ><label for="confirmation">确认密码</label
            ><input
              id="confirmation"
              v-model="confirmation"
              type="password"
              autocomplete="new-password"
              required
              maxlength="128"
          /></template>
        </fieldset>
        <AppErrorState v-if="error" :message="error" />
        <button class="primary-button submit-button" type="submit" :disabled="busy">
          {{ busy ? "正在提交…" : registering ? "创建账号" : "登录"
          }}<ArrowRight :size="18" aria-hidden="true" />
        </button>
        <p class="auth-switch">
          {{ registering ? "已有账号？" : "还没有账号？"
          }}<RouterLink
            :to="{
              name: registering ? 'login' : 'register',
              query: { redirect: safeRedirect(router, route.query.redirect) },
            }"
            >{{ registering ? "前往登录" : "创建账号" }}</RouterLink
          >
        </p>
      </form>
    </section>
  </main>
</template>
