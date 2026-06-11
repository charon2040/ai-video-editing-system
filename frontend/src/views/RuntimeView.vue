<script setup lang="ts">
import { onMounted } from "vue";
import RuntimePanel from "../components/RuntimePanel.vue";
import { useClipAppState } from "../stores/clipAppState";

const app = useClipAppState();

onMounted(() => {
  void app.loadRuntime();
});
</script>

<template>
  <div class="view-stack">
    <section class="page-title">
      <p class="eyebrow">Runtime</p>
      <h1>运行环境</h1>
      <p>环境状态单独成页，用来判断 ASR、LLM、CosyVoice 和后端配置是否正常。</p>
    </section>

    <RuntimePanel :runtime="app.runtime.value" :loading="app.runtimeLoading.value" @refresh="app.loadRuntime" />
  </div>
</template>
