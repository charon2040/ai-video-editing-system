<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import TaskHistory from "../components/TaskHistory.vue";
import { useClipAppState } from "../stores/clipAppState";

const route = useRoute();
const router = useRouter();
const app = useClipAppState();

const routeProjectId = computed(() => String(route.params.projectId || ""));

async function syncRouteProject() {
  if (routeProjectId.value) {
    await app.selectProject(routeProjectId.value);
    return;
  }
  await app.loadHistory(app.activeProjectId.value);
}

async function openTask(taskId: string) {
  await app.openTask(taskId);
  if (routeProjectId.value) {
    await router.push({ name: "project-task-detail", params: { projectId: app.activeProjectId.value, id: taskId } });
    return;
  }
  await router.push({ name: "task-detail", params: { id: taskId } });
}

onMounted(syncRouteProject);
watch(routeProjectId, syncRouteProject);
</script>

<template>
  <div class="view-stack">
    <section class="page-title">
      <p class="eyebrow">Task Center</p>
      <h1>任务中心</h1>
      <p>任务列表单独成页，避免和创建表单、运行环境混在一个长页面里。</p>
    </section>

    <TaskHistory
      :tasks="app.tasks.value"
      :active-task-id="app.activeTaskId.value"
      :status="app.historyStatus.value"
      @select="openTask"
      @delete="app.deleteTask"
      @clear="app.clearFinishedTasks"
      @refresh="() => app.loadHistory(app.activeProjectId.value)"
    />
  </div>
</template>
