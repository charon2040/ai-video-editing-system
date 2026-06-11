<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { useClipAppState } from "../stores/clipAppState";
import type { KnowledgePolicy, Project, VoiceMode, WorkflowTemplate } from "../types";
import { styleLabel, voiceModeLabel } from "../utils/format";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const routeProjectId = computed(() => String(route.params.projectId || app.activeProjectId.value || "default"));

const title = ref("");
const description = ref("");
const defaultKnowledgeBaseId = ref("");
const defaultKnowledgePolicy = ref<KnowledgePolicy>("none");
const defaultPipelineMode = ref("narration_clip");
const defaultDurationSeconds = ref("0");
const defaultStyle = ref("summary");
const defaultEnableDubbing = ref(false);
const defaultVoiceMode = ref<VoiceMode>("standard");
const defaultVoiceProfileId = ref("");
const defaultTtsSpeed = ref("1.00");
const defaultKeepOriginalAudio = ref(true);

const workflowOptions = computed<WorkflowTemplate[]>(() => {
  return app.workflowTemplates.value.length
    ? app.workflowTemplates.value
    : [{ id: "narration_clip", title: "AI 解说剪辑", description: "生成文案、确认后配音，并按配音时长匹配画面。" }];
});

const selectedWorkflow = computed(() => {
  return workflowOptions.value.find((item) => item.id === defaultPipelineMode.value)
    || workflowOptions.value[0]
    || { id: "narration_clip", title: "AI 解说剪辑", description: "" };
});

const voiceProfileOptions = computed(() => {
  return app.voiceProfiles.value.filter((profile) => {
    const kind = String(profile.voice_kind || "").toLowerCase();
    const sourceType = String(profile.source_type || "").toLowerCase();
    if (defaultVoiceMode.value === "clone") return kind === "clone" || sourceType === "user";
    return kind !== "clone" && sourceType !== "user";
  });
});

function normalizeKnowledgePolicy(value: unknown): KnowledgePolicy {
  const policy = String(value || "").trim().toLowerCase();
  return policy === "project_default" || policy === "selected" ? policy : "none";
}

function normalizeVoiceMode(value: unknown): VoiceMode {
  return value === "clone" ? "clone" : "standard";
}

function syncFromProject(project: Project) {
  title.value = String(project.title || "默认项目");
  description.value = String(project.description || "");
  defaultKnowledgeBaseId.value = String(project.default_knowledge_base_id || app.activeKnowledgeId.value || "");
  defaultKnowledgePolicy.value = normalizeKnowledgePolicy(project.default_knowledge_policy);
  const pipelineMode = String(project.default_pipeline_mode || "").trim();
  defaultPipelineMode.value = workflowOptions.value.some((item) => item.id === pipelineMode)
    ? pipelineMode
    : workflowOptions.value[0]?.id || "narration_clip";
  defaultDurationSeconds.value = String(project.default_duration_seconds || 0);
  defaultStyle.value = String(project.default_style || "summary");
  defaultEnableDubbing.value = Boolean(project.default_enable_dubbing);
  defaultVoiceMode.value = normalizeVoiceMode(project.default_voice_mode);
  defaultVoiceProfileId.value = String(project.default_voice_profile_id || "");
  defaultTtsSpeed.value = Number(project.default_tts_speed || 1).toFixed(2);
  defaultKeepOriginalAudio.value = project.default_keep_original_audio !== false;
}

async function initSettingsView() {
  await app.loadVoiceProfiles();
  await syncRouteProject();
}

async function syncRouteProject() {
  await app.selectProject(routeProjectId.value);
}

async function selectProject(projectId: string) {
  await app.selectProject(projectId);
  await router.replace({ name: "project-settings", params: { projectId } });
}

async function save() {
  await app.saveProjectSettings({
    id: app.activeProjectId.value,
    title: title.value.trim() || "默认项目",
    description: description.value.trim(),
    default_knowledge_base_id: defaultKnowledgeBaseId.value,
    default_knowledge_policy: defaultKnowledgePolicy.value,
    default_pipeline_mode: defaultPipelineMode.value,
    default_duration_seconds: Number(defaultDurationSeconds.value) || 0,
    default_style: defaultStyle.value,
    default_enable_dubbing: defaultEnableDubbing.value,
    default_voice_mode: defaultVoiceMode.value,
    default_voice_profile_id: defaultVoiceProfileId.value,
    default_tts_speed: Number(defaultTtsSpeed.value) || 1,
    default_keep_original_audio: defaultKeepOriginalAudio.value,
  });
}

onMounted(initSettingsView);
watch(routeProjectId, syncRouteProject);
watch(
  () => [
    app.activeProject.value,
    workflowOptions.value.map((item) => item.id).join("|"),
  ],
  () => syncFromProject(app.activeProject.value),
  { immediate: true },
);
</script>

<template>
  <div class="view-stack narrow-view">
    <section class="page-title project-title">
      <div>
        <p class="eyebrow">Project Settings</p>
        <h1>项目设置</h1>
        <p>这里维护项目模板。设置只会预填创建任务表单，不会在后台静默覆盖你本次任务的选择。</p>
      </div>
      <div class="project-title-actions">
        <RouterLink class="ghost-link" :to="{ name: 'project-workspace', params: { projectId: app.activeProjectId.value } }">
          返回项目
        </RouterLink>
        <RouterLink class="primary-link" :to="{ name: 'project-create', params: { projectId: app.activeProjectId.value } }">
          创建任务
        </RouterLink>
      </div>
    </section>

    <section class="panel settings-panel">
      <div class="panel-header">
        <div>
          <h2>默认模板</h2>
          <p>用户进入这个项目后，创建任务会先带入这些默认值，提交前仍可修改。</p>
        </div>
        <select
          class="compact-select"
          :value="app.activeProjectId.value"
          aria-label="选择项目"
          @change="selectProject(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="project in app.projects.value" :key="project.id" :value="project.id">
            {{ project.title || project.id }}
          </option>
        </select>
      </div>

      <form class="task-form" @submit.prevent="save">
        <div class="field-row">
          <label class="field">
            <span>项目名称</span>
            <input v-model="title" type="text" />
          </label>
          <label class="field">
            <span>默认工作流</span>
            <select v-model="defaultPipelineMode">
              <option v-for="item in workflowOptions" :key="item.id" :value="item.id">
                {{ item.title || item.id }}
              </option>
            </select>
          </label>
        </div>
        <p class="field-hint">
          {{ selectedWorkflow.description || "当前版本先保存项目默认模板，后续会把模板拆成可组合节点执行。" }}
        </p>

        <label class="field">
          <span>项目说明</span>
          <textarea v-model="description" rows="4" placeholder="描述这个项目适合处理什么内容，例如赛事复盘、课程切片、产品发布会等。" />
        </label>

        <div class="field-row">
          <label class="field">
            <span>默认知识库</span>
            <select v-model="defaultKnowledgeBaseId">
              <option value="">未设置</option>
              <option v-for="item in app.knowledgeItems.value" :key="item.id" :value="item.id">
                {{ item.title }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>默认知识库使用方式</span>
            <select v-model="defaultKnowledgePolicy">
              <option value="none">不使用知识库</option>
              <option value="project_default" :disabled="!defaultKnowledgeBaseId">使用项目默认知识库</option>
              <option value="selected" :disabled="!defaultKnowledgeBaseId">指定该知识库</option>
            </select>
          </label>
        </div>
        <p class="field-hint">
          长期知识库只适合放稳定实体、别名、人物关系和术语。本次视频才成立的左右方、阵容、临时身份仍应在创建任务时填写。
        </p>

        <div class="field-row">
          <label class="field">
            <span>默认目标时长</span>
            <select v-model="defaultDurationSeconds">
              <option value="0">自动</option>
              <option value="30">30 秒</option>
              <option value="45">45 秒</option>
              <option value="60">60 秒</option>
              <option value="90">90 秒</option>
            </select>
          </label>
          <label class="field">
            <span>默认输出风格</span>
            <select v-model="defaultStyle">
              <option value="summary">{{ styleLabel("summary") }}</option>
              <option value="highlight">{{ styleLabel("highlight") }}</option>
              <option value="analysis">{{ styleLabel("analysis") }}</option>
              <option value="short_hook">{{ styleLabel("short_hook") }}</option>
            </select>
          </label>
        </div>

        <div class="field-row">
          <label class="checkbox-card">
            <input v-model="defaultEnableDubbing" type="checkbox" />
            <span>默认开启 AI 配音</span>
          </label>
          <label class="checkbox-card">
            <input v-model="defaultKeepOriginalAudio" type="checkbox" />
            <span>默认保留低音量原声</span>
          </label>
        </div>

        <div class="field-row">
          <label class="field">
            <span>默认配音通道</span>
            <select v-model="defaultVoiceMode" @change="defaultVoiceProfileId = ''">
              <option value="standard">{{ voiceModeLabel("standard") }}</option>
              <option value="clone">{{ voiceModeLabel("clone") }}</option>
            </select>
          </label>
          <label class="field">
            <span>默认音色 / 模板</span>
            <select v-model="defaultVoiceProfileId">
              <option value="">自动选择</option>
              <option v-for="profile in voiceProfileOptions" :key="profile.id" :value="profile.id">
                {{ profile.label }}
              </option>
            </select>
          </label>
        </div>

        <label class="field">
          <span>默认配音语速</span>
          <select v-model="defaultTtsSpeed">
            <option value="0.85">0.85x 较慢</option>
            <option value="1.00">1.00x 默认</option>
            <option value="1.10">1.10x 稍快</option>
            <option value="1.20">1.20x 更快</option>
          </select>
        </label>

        <div class="form-actions">
          <button type="submit" :disabled="app.projectSaving.value">保存项目设置</button>
          <p class="submit-status">{{ app.projectStatus.value }}</p>
        </div>
      </form>
    </section>
  </div>
</template>
