import { ref } from "vue";
import { api } from "../api/client";
import type { ClipPlan, DraftBeat, TaskDeleteResult, TaskItem } from "../types";
import { canDeleteTask, isAwaitingDraftReview } from "../utils/format";
import { useProjectKnowledgeState } from "./projectKnowledgeState";

const tasks = ref<TaskItem[]>([]);
const activeTaskId = ref("");
const activeTask = ref<TaskItem | null>(null);
const taskPlans = ref<ClipPlan[]>([]);
const plansLoading = ref(false);
const historyStatus = ref("运行中任务不会被清空，等待确认的文案任务只能单独删除。");
let pollTimer: number | null = null;

const projectState = useProjectKnowledgeState();

function summarizeDeleteResult(result: TaskDeleteResult, taskId = "") {
  const target = taskId || result.task_id || "任务";
  if (!result.delete_source_requested) {
    return `${target} 已删除，已保留原视频与 ASR 缓存。`;
  }

  const sourceLabel = result.deleted_source
    ? "源视频已删除"
    : `源视频保留${result.source_retained_reason ? `：${result.source_retained_reason}` : ""}`;
  const cacheLabel = result.deleted_asr_cache
    ? "ASR 缓存已删除"
    : `ASR 缓存保留${result.asr_cache_retained_reason ? `：${result.asr_cache_retained_reason}` : ""}`;
  return `${target} 已删除，${sourceLabel}，${cacheLabel}。`;
}

function summarizeBulkDeleteResult(result: TaskDeleteResult) {
  const count = result.deleted_count ?? result.task_ids?.length ?? 0;
  if (!result.delete_source_requested) {
    return `已清空 ${count} 个已结束任务，已保留原视频与 ASR 缓存。`;
  }

  const items = result.items || [];
  const sourceCount = items.filter((item) => item.deleted_source).length;
  const cacheCount = items.filter((item) => item.deleted_asr_cache).length;
  return `已清空 ${count} 个已结束任务，同时删除 ${sourceCount} 个无引用源视频、${cacheCount} 份无引用 ASR 缓存。`;
}

async function loadHistory(projectId = projectState.activeProjectId.value) {
  try {
    const normalizedProjectId = String(projectId || "").trim();
    const data = await api.listTasks(normalizedProjectId);
    tasks.value = data.items || [];
    historyStatus.value = normalizedProjectId
      ? `已加载项目任务：${projectState.activeProject.value.title || normalizedProjectId}`
      : "已加载全部任务。";
  } catch (error) {
    tasks.value = [];
    historyStatus.value = `任务列表读取失败：${(error as Error).message}`;
  }
}

async function loadTask(taskId: string) {
  try {
    const [task, eventsData] = await Promise.all([
      api.getTask(taskId),
      api.getTaskEvents(taskId).catch(() => ({ items: [] })),
    ]);
    task.events = eventsData.items || [];
    activeTaskId.value = task.id;
    activeTask.value = task;
    await projectState.ensureTaskProjectContext(task);
    if (task.status === "completed") {
      await loadTaskPlans(task.id);
    } else {
      taskPlans.value = [];
    }
    if (isAwaitingDraftReview(task)) {
      stopPolling();
      await loadHistory(projectState.activeProjectId.value);
      return;
    }
    if (task.status === "completed" || task.status === "failed") {
      stopPolling();
      await loadHistory(projectState.activeProjectId.value);
    }
  } catch (error) {
    historyStatus.value = `任务读取失败：${(error as Error).message}`;
    stopPolling();
  }
}

async function openTask(taskId: string) {
  await loadTask(taskId);
  const task = activeTask.value;
  if (task && task.status !== "completed" && task.status !== "failed" && !isAwaitingDraftReview(task)) {
    startPolling(task.id);
  }
}

async function loadTaskPlans(taskId: string) {
  plansLoading.value = true;
  try {
    const data = await api.listTaskPlans(taskId);
    taskPlans.value = data.items || [];
  } catch {
    taskPlans.value = [];
  } finally {
    plansLoading.value = false;
  }
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling(taskId: string) {
  stopPolling();
  pollTimer = window.setInterval(() => {
    void loadTask(taskId);
  }, 2500);
}

async function handleTaskCreated(task: TaskItem) {
  const taskProjectId = String(task.payload?.project_id || task.project_id || projectState.activeProjectId.value || "default").trim() || "default";
  projectState.activeProjectId.value = taskProjectId;
  activeTaskId.value = task.id;
  activeTask.value = task;
  taskPlans.value = [];
  await loadHistory(taskProjectId);
  startPolling(task.id);
}

async function deleteTask(taskId: string) {
  const task = tasks.value.find((item) => item.id === taskId) || activeTask.value;
  if (!task || !canDeleteTask(task)) return;
  const confirmed = window.confirm(`确定删除任务 ${taskId} 吗？会删除导出结果、配音临时文件和方案记录。`);
  if (!confirmed) return;
  const deleteSource = window.confirm("是否同时删除原视频和无引用 ASR 缓存？取消则只删除任务产物，保留素材以便后续复用。");
  try {
    const result = await api.deleteTask(taskId, deleteSource);
    if (activeTaskId.value === taskId) {
      stopPolling();
      activeTaskId.value = "";
      activeTask.value = null;
      taskPlans.value = [];
    }
    await loadHistory(projectState.activeProjectId.value);
    historyStatus.value = summarizeDeleteResult(result, taskId);
  } catch (error) {
    historyStatus.value = `删除失败：${(error as Error).message}`;
  }
}

async function clearFinishedTasks() {
  const confirmed = window.confirm(`确定清空项目 ${projectState.activeProject.value.title || projectState.activeProjectId.value} 下所有已完成和失败任务吗？等待确认的文案任务会保留。`);
  if (!confirmed) return;
  const deleteSource = window.confirm("是否同时删除这些任务对应的原视频和无引用 ASR 缓存？取消则只删除任务产物。");
  try {
    const result = await api.clearFinishedTasks(projectState.activeProjectId.value, deleteSource);
    if (activeTask.value?.status === "completed" || activeTask.value?.status === "failed") {
      activeTask.value = null;
      activeTaskId.value = "";
      stopPolling();
    }
    await loadHistory(projectState.activeProjectId.value);
    historyStatus.value = summarizeBulkDeleteResult(result);
  } catch (error) {
    historyStatus.value = `清空失败：${(error as Error).message}`;
  }
}

function buildDraftFormData(beats: DraftBeat[], draftScript: string) {
  const formData = new FormData();
  formData.append("draft_script", draftScript);
  formData.append("beats_json", JSON.stringify(beats));
  return formData;
}

async function saveDraft(payload: { taskId: string; beats: DraftBeat[]; draftScript: string }) {
  try {
    const task = await api.saveDraft(payload.taskId, buildDraftFormData(payload.beats, payload.draftScript));
    activeTask.value = task;
    activeTaskId.value = task.id;
    await loadHistory(projectState.activeProjectId.value);
  } catch (error) {
    historyStatus.value = `保存草稿失败：${(error as Error).message}`;
  }
}

async function approveDraft(payload: { taskId: string; beats: DraftBeat[]; draftScript: string }) {
  try {
    const task = await api.approveDraft(payload.taskId, buildDraftFormData(payload.beats, payload.draftScript));
    activeTask.value = task;
    activeTaskId.value = task.id;
    await loadHistory(projectState.activeProjectId.value);
    startPolling(task.id);
  } catch (error) {
    historyStatus.value = `确认文案失败：${(error as Error).message}`;
  }
}

async function replanTask(payload: { taskId: string; formData: FormData }) {
  try {
    const task = await api.replanTask(payload.taskId, payload.formData);
    activeTask.value = task;
    activeTaskId.value = task.id;
    taskPlans.value = [];
    await loadHistory(projectState.activeProjectId.value);
    startPolling(task.id);
  } catch (error) {
    historyStatus.value = `重新生成失败：${(error as Error).message}`;
  }
}

async function retryAlignment(taskId: string) {
  try {
    const task = await api.retryAlignment(taskId);
    activeTask.value = task;
    activeTaskId.value = task.id;
    taskPlans.value = [];
    await loadHistory(projectState.activeProjectId.value);
    startPolling(task.id);
  } catch (error) {
    historyStatus.value = `重新选片失败：${(error as Error).message}`;
  }
}

function resetTaskState() {
  stopPolling();
  tasks.value = [];
  activeTaskId.value = "";
  activeTask.value = null;
  taskPlans.value = [];
  plansLoading.value = false;
  historyStatus.value = "运行中任务不会被清空，等待确认的文案任务只能单独删除。";
}

export function useTaskState() {
  return {
    tasks,
    activeTaskId,
    activeTask,
    taskPlans,
    plansLoading,
    historyStatus,
    loadHistory,
    loadTask,
    openTask,
    loadTaskPlans,
    stopPolling,
    startPolling,
    handleTaskCreated,
    deleteTask,
    clearFinishedTasks,
    saveDraft,
    approveDraft,
    replanTask,
    retryAlignment,
    resetTaskState,
  };
}
