<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { useClipAppState } from "../stores/clipAppState";
import { actualDurationLabel, badgeClass, finalDurationMs, formatDate, stageLabel } from "../utils/format";

const route = useRoute();
const app = useClipAppState();

const projectId = computed(() => String(route.params.projectId || app.activeProjectId.value || "default"));
const activeTasks = computed(() => app.tasks.value.filter((task) => task.status !== "completed" && task.status !== "failed"));
const finishedTasks = computed(() => app.tasks.value.filter((task) => task.status === "completed"));
const recentTasks = computed(() => app.tasks.value.slice(0, 5));

async function syncProject() {
  await app.selectProject(projectId.value);
}

onMounted(syncProject);
watch(projectId, syncProject);
</script>

<template>
  <div class="view-stack">
    <section class="page-title project-title">
      <div>
        <p class="eyebrow">Project Workspace</p>
        <h1>{{ app.activeProject.value.title || app.activeProjectId.value }}</h1>
        <p>
          项目是任务的工作空间：任务、默认知识库和默认工作流都挂在项目下。知识库是项目模板，不会强制注入任务。
        </p>
      </div>
      <div class="project-title-actions">
        <RouterLink class="primary-link" :to="{ name: 'project-create', params: { projectId: app.activeProjectId.value } }">
          新建任务
        </RouterLink>
        <RouterLink class="ghost-link" :to="{ name: 'project-tasks', params: { projectId: app.activeProjectId.value } }">
          查看任务
        </RouterLink>
        <RouterLink class="ghost-link" :to="{ name: 'project-settings', params: { projectId: app.activeProjectId.value } }">
          项目设置
        </RouterLink>
      </div>
    </section>

    <section class="route-grid project-route-grid">
      <RouterLink class="route-card" :to="{ name: 'project-create', params: { projectId: app.activeProjectId.value } }">
        <span>Workflow</span>
        <strong>创建任务</strong>
        <p>在当前项目下上传素材、写目标、选择是否使用项目默认知识库。</p>
      </RouterLink>
      <RouterLink class="route-card" :to="{ name: 'project-tasks', params: { projectId: app.activeProjectId.value } }">
        <span>Queue</span>
        <strong>项目任务</strong>
        <p>只查看这个项目里的等待确认、运行中、完成和失败任务。</p>
      </RouterLink>
      <RouterLink class="route-card" :to="{ name: 'project-knowledge', params: { projectId: app.activeProjectId.value } }">
        <span>Context</span>
        <strong>项目知识库</strong>
        <p>维护这个项目的长期实体、别名、人物关系和默认知识库。</p>
      </RouterLink>
      <RouterLink class="route-card" :to="{ name: 'project-settings', params: { projectId: app.activeProjectId.value } }">
        <span>Template</span>
        <strong>项目设置</strong>
        <p>配置创建任务时的默认知识库策略、配音、风格和目标时长。</p>
      </RouterLink>
      <RouterLink class="route-card" to="/runtime">
        <span>System</span>
        <strong>运行环境</strong>
        <p>检查 ASR、LLM、CosyVoice 和后端服务状态。</p>
      </RouterLink>
    </section>

    <section class="dashboard-grid">
      <article class="panel">
        <div class="panel-header compact-header">
          <div>
            <h2>项目概览</h2>
            <p>当前项目的任务和上下文状态。</p>
          </div>
        </div>
        <div class="metric-grid">
          <div class="metric-card"><span>活跃任务</span><strong>{{ activeTasks.length }}</strong></div>
          <div class="metric-card"><span>已完成</span><strong>{{ finishedTasks.length }}</strong></div>
          <div class="metric-card"><span>知识库</span><strong>{{ app.knowledgeItems.value.length }}</strong></div>
          <div class="metric-card"><span>默认知识库</span><strong>{{ app.activeProject.value.default_knowledge_base_id || "未设置" }}</strong></div>
          <div class="metric-card"><span>默认风格</span><strong>{{ app.activeProject.value.default_style || "summary" }}</strong></div>
          <div class="metric-card"><span>默认配音</span><strong>{{ app.activeProject.value.default_enable_dubbing ? "开启" : "关闭" }}</strong></div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-header compact-header">
          <div>
            <h2>最近任务</h2>
            <p>这里只展示当前项目的最近任务。</p>
          </div>
          <RouterLink class="ghost-link slim-link" :to="{ name: 'project-tasks', params: { projectId: app.activeProjectId.value } }">
            全部任务
          </RouterLink>
        </div>
        <div v-if="!recentTasks.length" class="empty-state">这个项目还没有任务。</div>
        <div v-else class="compact-task-list">
          <RouterLink
            v-for="task in recentTasks"
            :key="task.id"
            class="compact-task-item"
            :to="{ name: 'project-task-detail', params: { projectId: app.activeProjectId.value, id: task.id } }"
          >
            <div>
              <span class="task-id">Task {{ task.id }}</span>
              <strong>{{ task.payload?.original_filename || "--" }}</strong>
              <small>{{ formatDate(task.created_at) }} · {{ actualDurationLabel(finalDurationMs(task)) }}</small>
            </div>
            <span class="badge" :class="badgeClass(task.status)">{{ stageLabel(task.stage) }}</span>
          </RouterLink>
        </div>
      </article>
    </section>
  </div>
</template>
