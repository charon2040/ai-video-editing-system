<script setup lang="ts">
import type { RuntimeStatus } from "../types";

defineProps<{
  runtime: RuntimeStatus | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

function readyLabel(value: unknown, yes = "就绪", no = "未就绪") {
  return value ? yes : no;
}
</script>

<template>
  <section class="panel runtime-panel">
    <div class="panel-header">
      <div>
        <h2>运行环境</h2>
        <p>ASR、LLM、TTS 和后端运行状态集中显示，方便判断链路卡在哪一步。</p>
      </div>
      <button class="ghost-btn" type="button" @click="emit('refresh')">刷新环境</button>
    </div>

    <div v-if="loading" class="empty-state">正在读取运行环境...</div>
    <div v-else-if="!runtime" class="empty-state">运行环境读取失败。</div>
    <div v-else class="runtime-grid">
      <article class="runtime-card runtime-card-wide">
        <div class="runtime-card-head">
          <div>
            <div class="task-id">Runtime Topology</div>
            <h3>{{ runtime.topology?.separate_envs ? "ASR / TTS 已分环境" : "当前未分环境拆分" }}</h3>
          </div>
          <span class="badge" :class="runtime.topology?.separate_envs ? 'completed' : 'running'">
            {{ runtime.topology?.separate_envs ? "推荐结构" : "待收口" }}
          </span>
        </div>
        <p class="runtime-summary">{{ runtime.topology?.summary || "--" }}</p>
        <div class="runtime-path">Backend Python: {{ runtime.backend?.python || "--" }}</div>
      </article>

      <article class="runtime-card">
        <div class="runtime-card-head">
          <div>
            <div class="task-id">LLM</div>
            <h3>{{ runtime.llm?.model || "--" }}</h3>
          </div>
          <span class="badge" :class="runtime.llm?.configured ? 'completed' : 'failed'">
            {{ readyLabel(runtime.llm?.configured, "已配置", "缺配置") }}
          </span>
        </div>
        <div class="runtime-metrics">
          <div><span>Base URL</span><strong>{{ runtime.llm?.base_url || "--" }}</strong></div>
          <div><span>API Key</span><strong>{{ runtime.llm?.configured ? "已设置" : "未设置" }}</strong></div>
        </div>
      </article>

      <article class="runtime-card">
        <div class="runtime-card-head">
          <div>
            <div class="task-id">ASR</div>
            <h3>FunASR</h3>
          </div>
          <span class="badge" :class="runtime.asr?.ready ? 'completed' : 'failed'">
            {{ readyLabel(runtime.asr?.ready) }}
          </span>
        </div>
        <div class="runtime-metrics">
          <div><span>模式</span><strong>{{ runtime.asr?.mode || "--" }}</strong></div>
          <div><span>设备</span><strong>{{ runtime.asr?.device || "--" }}</strong></div>
        </div>
        <div class="runtime-path">{{ runtime.asr?.python || "--" }}</div>
        <div class="runtime-note">ASR Model: {{ runtime.asr?.model || "--" }}</div>
      </article>

      <article class="runtime-card runtime-card-wide">
        <div class="runtime-card-head">
          <div>
            <div class="task-id">TTS</div>
            <h3>CosyVoice 单服务</h3>
          </div>
          <span class="badge" :class="(runtime.tts?.cosyvoice as any)?.ready ? 'completed' : 'failed'">
            {{ readyLabel((runtime.tts?.cosyvoice as any)?.ready) }}
          </span>
        </div>
        <div class="runtime-metrics">
          <div><span>Provider</span><strong>{{ (runtime.tts?.cosyvoice as any)?.provider || "--" }}</strong></div>
          <div><span>模式</span><strong>{{ runtime.tts?.mode || "--" }}</strong></div>
          <div><span>普通音色</span><strong>{{ runtime.tts?.standard_profile_count || 0 }}</strong></div>
          <div><span>克隆模板</span><strong>{{ runtime.tts?.clone_profile_count || 0 }}</strong></div>
          <div><span>服务健康</span><strong>{{ readyLabel((runtime.tts?.cosyvoice as any)?.service_healthy) }}</strong></div>
        </div>
        <div class="runtime-path">{{ (runtime.tts?.cosyvoice as any)?.python || "--" }}</div>
        <div class="runtime-note">Service: {{ (runtime.tts?.cosyvoice as any)?.http_base_url || "--" }}</div>
      </article>
    </div>
  </section>
</template>
