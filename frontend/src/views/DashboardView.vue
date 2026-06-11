<script setup lang="ts">
import { onMounted } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { useClipAppState } from "../stores/clipAppState";

const router = useRouter();
const app = useClipAppState();

async function createProject() {
  await app.createProject();
  await router.push({ name: "project-workspace", params: { projectId: app.activeProjectId.value } });
}

function canDeleteProject(projectId: string) {
  const id = String(projectId || "").trim();
  return Boolean(id) && id !== "default" && !id.endsWith("_default");
}

onMounted(() => {
  if (!app.projects.value.length) void app.loadProjects();
});
</script>

<template>
  <div class="dashboard-view">
    <header class="hero">
      <div>
        <p class="eyebrow">Project Workspaces</p>
        <h1>选择项目</h1>
        <p class="hero-copy">
          项目是任务的工作空间。进入项目后，再创建任务、查看该项目任务、维护项目默认知识库和上下文模板。
        </p>
        <div class="hero-actions">
          <button type="button" @click="createProject">新建项目</button>
          <RouterLink class="ghost-link" to="/runtime">运行环境</RouterLink>
        </div>
      </div>
      <div class="hero-panel">
        <div class="hero-stat"><span>Project</span><strong>任务分类</strong></div>
        <div class="hero-stat"><span>Template</span><strong>默认知识库</strong></div>
        <div class="hero-stat"><span>Workflow</span><strong>默认工作流</strong></div>
        <div class="hero-stat"><span>Task</span><strong>项目内创建</strong></div>
      </div>
    </header>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>项目列表</h2>
          <p>点击项目进入工作台。任务列表和知识库会按项目隔离展示。</p>
        </div>
        <button class="ghost-btn" type="button" @click="createProject">新建项目</button>
      </div>

      <div v-if="!app.projects.value.length" class="empty-state">还没有项目。</div>
      <div v-else class="project-grid">
        <article
          v-for="project in app.projects.value"
          :key="project.id"
          class="project-card"
        >
          <RouterLink
            class="project-card-link"
            :to="{ name: 'project-workspace', params: { projectId: project.id } }"
          >
            <span class="task-id">Project {{ project.id }}</span>
            <strong>{{ project.title || project.id }}</strong>
            <p>{{ project.description || "项目工作空间：任务、默认知识库和默认工作流都归到这里。" }}</p>
            <div class="task-card-stats">
              <span>默认知识库 {{ project.default_knowledge_base_id || "未设置" }}</span>
              <span>{{ project.default_pipeline_mode || "narration_clip" }}</span>
            </div>
          </RouterLink>
          <div class="project-card-actions">
            <button
              v-if="canDeleteProject(project.id)"
              class="ghost-btn danger-btn slim-btn"
              type="button"
              :disabled="app.projectSaving.value"
              @click="app.deleteProject(project.id)"
            >
              删除项目
            </button>
            <span v-else class="muted">默认项目不可删除</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
