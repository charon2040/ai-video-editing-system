<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { KnowledgePolicy, ProjectKnowledge, TaskItem, VoiceProfile } from "../types";

const props = defineProps<{
  task: TaskItem;
  voiceProfiles: VoiceProfile[];
  knowledgeItems: ProjectKnowledge[];
}>();

const emit = defineEmits<{
  replan: [payload: { taskId: string; formData: FormData }];
}>();

const replanText = ref("");
const replanProjectContext = ref("");
const replanKnowledgePolicy = ref<KnowledgePolicy>("none");
const replanKnowledgeId = ref("");
const replanDuration = ref("0");
const replanStyle = ref("summary");
const replanEnableDubbing = ref(false);
const replanKeepOriginalAudio = ref(true);
const replanVoiceMode = ref("standard");
const replanVoiceProfileId = ref("");
const replanTtsSpeed = ref("1.00");
const replanStatus = ref("不会重新上传视频，优先复用 ASR。");

const currentProjectDefaultKnowledgeId = computed(() => {
  return String(props.task.payload?.project_default_knowledge_base_id || "").trim();
});

const currentProjectDefaultKnowledgeTitle = computed(() => {
  const defaultId = currentProjectDefaultKnowledgeId.value;
  if (!defaultId) return "未设置";
  const item = props.knowledgeItems.find((knowledge) => knowledge.id === defaultId);
  return item?.title || defaultId;
});

const voiceProfilesForReplan = computed(() => {
  return props.voiceProfiles.filter((profile) => {
    const kind = String(profile.voice_kind || "").toLowerCase();
    const sourceType = String(profile.source_type || "").toLowerCase();
    if (replanVoiceMode.value === "clone") return kind === "clone" || sourceType === "user";
    return kind !== "clone" && sourceType !== "user";
  });
});

function normalizeKnowledgePolicy(policy: string, knowledgeId = ""): KnowledgePolicy {
  const value = String(policy || "").trim().toLowerCase();
  if (value === "none" || value === "project_default" || value === "selected") {
    return value;
  }
  return String(knowledgeId || "").trim() ? "selected" : "none";
}

function replan() {
  if (!replanText.value.trim()) {
    replanStatus.value = "请先填写新的目标或要求。";
    return;
  }
  const formData = new FormData();
  formData.append("requirements", replanText.value.trim());
  formData.append("project_context", replanProjectContext.value.trim());
  formData.append("knowledge_policy", replanKnowledgePolicy.value);
  formData.append("knowledge_base_id", replanKnowledgePolicy.value === "selected" ? replanKnowledgeId.value : "");
  formData.append("duration_seconds", replanDuration.value);
  formData.append("style", replanStyle.value);
  formData.append("enable_dubbing", replanEnableDubbing.value ? "true" : "false");
  formData.append("voice_mode", replanVoiceMode.value);
  formData.append("keep_original_audio", replanKeepOriginalAudio.value ? "true" : "false");
  formData.append("voice_profile_id", replanVoiceProfileId.value || "");
  formData.append("tts_speed", replanTtsSpeed.value);
  replanStatus.value = "正在基于当前素材重新生成...";
  emit("replan", { taskId: props.task.id, formData });
}

watch(
  () => props.task,
  (task) => {
    const payload = task.payload || {};
    replanText.value = String(payload.request_text || "");
    replanProjectContext.value = String(payload.project_context_extra || "");
    replanKnowledgeId.value = String(payload.knowledge_base_id || "");
    replanKnowledgePolicy.value = normalizeKnowledgePolicy(
      String(payload.knowledge_policy || ""),
      replanKnowledgeId.value,
    );
    replanDuration.value = String(payload.duration_seconds || "0");
    replanStyle.value = String(payload.style || "summary");
    replanEnableDubbing.value = Boolean(payload.enable_dubbing);
    replanKeepOriginalAudio.value = payload.keep_original_audio !== false;
    replanVoiceMode.value = String(payload.voice_mode || "standard");
    replanVoiceProfileId.value = String(payload.voice_profile_id || "");
    replanTtsSpeed.value = String(payload.tts_speed || "1.00");
  },
  { immediate: true },
);

watch(
  () => props.knowledgeItems.map((item) => item.id).join("|"),
  () => {
    if (replanKnowledgePolicy.value !== "selected") return;
    if (props.knowledgeItems.some((item) => item.id === replanKnowledgeId.value)) return;
    replanKnowledgeId.value = props.knowledgeItems[0]?.id || "";
  },
);
</script>

<template>
  <details class="task-section">
    <summary>
      <div><strong>重新生成方案</strong><small>复用原视频和 ASR，重新走文案与选片流程</small></div>
      <span class="section-pill">Replan</span>
    </summary>
    <div class="task-form task-section-body">
      <label class="field"><span>新的目标 / 要求</span><textarea v-model="replanText" rows="5" /></label>
      <label class="field"><span>本次补充事实</span><textarea v-model="replanProjectContext" rows="4" /></label>
      <div class="field-row">
        <label class="field">
          <span>知识库使用方式</span>
          <select v-model="replanKnowledgePolicy">
            <option value="none">不使用知识库</option>
            <option value="project_default" :disabled="!currentProjectDefaultKnowledgeId">
              使用项目默认：{{ currentProjectDefaultKnowledgeTitle }}
            </option>
            <option value="selected">指定知识库</option>
          </select>
        </label>
        <label class="field">
          <span>目标时长</span>
          <select v-model="replanDuration">
            <option value="0">自动</option>
            <option value="30">30 秒</option>
            <option value="45">45 秒</option>
            <option value="60">60 秒</option>
            <option value="90">90 秒</option>
          </select>
        </label>
      </div>
      <label v-if="replanKnowledgePolicy === 'selected'" class="field">
        <span>指定知识库</span>
        <select v-model="replanKnowledgeId">
          <option v-for="item in knowledgeItems" :key="item.id" :value="item.id">{{ item.title }}</option>
        </select>
      </label>
      <p v-else-if="replanKnowledgePolicy === 'project_default'" class="field-hint">
        本次会读取当前任务项目的默认知识库：{{ currentProjectDefaultKnowledgeTitle }}。
      </p>
      <p v-else class="field-hint">本次不会注入知识库，只使用视频字幕和你填写的补充事实。</p>
      <div class="field-row">
        <label class="field">
          <span>风格</span>
          <select v-model="replanStyle">
            <option value="summary">总结</option>
            <option value="highlight">高光</option>
            <option value="analysis">复盘</option>
            <option value="short_hook">短视频感</option>
          </select>
        </label>
        <label class="field">
          <span>配音通道</span>
          <select v-model="replanVoiceMode">
            <option value="standard">普通配音</option>
            <option value="clone">克隆配音</option>
          </select>
        </label>
      </div>
      <div class="field-row">
        <label class="checkbox-card"><input v-model="replanEnableDubbing" type="checkbox" /><span>开启 AI 配音</span></label>
        <label class="checkbox-card"><input v-model="replanKeepOriginalAudio" type="checkbox" /><span>保留低音量原声</span></label>
      </div>
      <div class="field-row">
        <label class="field">
          <span>音色 / 模板</span>
          <select v-model="replanVoiceProfileId">
            <option v-for="profile in voiceProfilesForReplan" :key="profile.id" :value="profile.id">{{ profile.label }}</option>
          </select>
        </label>
        <label class="field">
          <span>语速</span>
          <select v-model="replanTtsSpeed">
            <option value="0.85">0.85x 较慢</option>
            <option value="1.00">1.00x 默认</option>
            <option value="1.10">1.10x 稍快</option>
            <option value="1.20">1.20x 更快</option>
          </select>
        </label>
      </div>
      <div class="form-actions">
        <button type="button" @click="replan">基于当前素材重新生成</button>
        <p class="submit-status">{{ replanStatus }}</p>
      </div>
    </div>
  </details>
</template>
