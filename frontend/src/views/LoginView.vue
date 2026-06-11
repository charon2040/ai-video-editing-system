<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useClipAppState } from "../stores/clipAppState";

const app = useClipAppState();
const route = useRoute();
const router = useRouter();

const mode = ref<"login" | "register">("login");
const username = ref("local");
const password = ref("local123456");
const displayName = ref("");
const submitting = ref(false);
const errorMessage = ref("");

const title = computed(() => mode.value === "login" ? "登录工作台" : "创建本地账号");
const submitText = computed(() => mode.value === "login" ? "登录" : "注册并进入");
const secondaryText = computed(() => mode.value === "login" ? "没有账号？创建一个" : "已有账号？返回登录");
const passwordAutocomplete = computed(() => mode.value === "login" ? "current-password" : "new-password");

async function submit() {
  errorMessage.value = "";
  submitting.value = true;
  try {
    if (mode.value === "login") {
      await app.login(username.value, password.value);
    } else {
      await app.register(username.value, password.value, displayName.value);
    }
    const redirect = String(route.query.redirect || "/");
    await router.push(redirect);
    void app.bootstrap().catch((error) => {
      console.warn("Background bootstrap failed after auth:", error);
    });
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    submitting.value = false;
  }
}

function switchMode(nextMode: "login" | "register") {
  mode.value = nextMode;
  errorMessage.value = "";
  if (nextMode === "register" && username.value === "local") {
    username.value = "";
    password.value = "";
  }
}

function switchSecondaryMode() {
  switchMode(mode.value === "login" ? "register" : "login");
}
</script>

<template>
  <main class="login-view">
    <section class="login-hero">
      <p class="eyebrow">Local Accounts</p>
      <h1>{{ title }}</h1>
      <p>
        用户用于隔离项目、任务、知识库和上传的克隆配音模板。旧数据仍归属默认账号
        <strong>local / local123456</strong>。
      </p>
      <div class="login-tabs" role="tablist">
        <button
          class="ghost-btn"
          :class="{ active: mode === 'login' }"
          type="button"
          @click="switchMode('login')"
        >
          登录
        </button>
        <button
          class="ghost-btn"
          :class="{ active: mode === 'register' }"
          type="button"
          @click="switchMode('register')"
        >
          注册
        </button>
      </div>
    </section>

    <form class="panel login-card" @submit.prevent="submit">
      <label class="field">
        <span>用户名</span>
        <input v-model.trim="username" type="text" autocomplete="username" placeholder="3-32 位字母、数字、下划线" />
      </label>
      <label v-if="mode === 'register'" class="field">
        <span>显示名称</span>
        <input v-model.trim="displayName" type="text" autocomplete="name" placeholder="可选" />
      </label>
      <label class="field">
        <span>密码</span>
        <input v-model="password" type="password" :autocomplete="passwordAutocomplete" placeholder="至少 6 位" />
      </label>
      <p v-if="errorMessage" class="task-alert">{{ errorMessage }}</p>
      <p v-else class="muted">
        {{ app.authStatus.value || "进入工作台后会在后台加载项目、知识库和任务。" }}
      </p>
      <div class="form-actions">
        <button type="submit" :disabled="submitting || app.authLoading.value">
          {{ submitting || app.authLoading.value ? "处理中..." : submitText }}
        </button>
        <button class="ghost-btn" type="button" :disabled="submitting || app.authLoading.value" @click="switchSecondaryMode">
          {{ secondaryText }}
        </button>
      </div>
    </form>
  </main>
</template>
