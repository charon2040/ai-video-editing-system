import { computed, ref } from "vue";
import { api } from "../api/client";
import type { Project, ProjectKnowledge, TaskItem } from "../types";

const projects = ref<Project[]>([]);
const activeProjectId = ref("default");
const knowledgeItems = ref<ProjectKnowledge[]>([]);
const activeKnowledgeId = ref("default");
const knowledgeStatus = ref("正在读取知识库...");
const knowledgeSaving = ref(false);
const projectStatus = ref("项目配置用于预填任务表单，不会在后台静默覆盖本次任务选择。");
const projectSaving = ref(false);

function defaultProject(): Project {
  return {
    id: "default",
    title: "默认项目",
    description: "",
    default_knowledge_base_id: "default",
    default_pipeline_mode: "narration_clip",
    default_knowledge_policy: "none",
    default_duration_seconds: 0,
    default_style: "summary",
    default_enable_dubbing: false,
    default_voice_mode: "standard",
    default_voice_profile_id: "",
    default_tts_speed: 1,
    default_keep_original_audio: true,
  };
}

const activeProject = computed<Project>(() => {
  return projects.value.find((item) => item.id === activeProjectId.value)
    || projects.value[0]
    || defaultProject();
});

const activeKnowledge = computed<ProjectKnowledge>(() => {
  return knowledgeItems.value.find((item) => item.id === activeKnowledgeId.value)
    || knowledgeItems.value[0]
    || { id: "default", project_id: activeProjectId.value, title: "项目知识库", content: "" };
});

async function loadProjects() {
  try {
    const data = await api.listProjects();
    projects.value = (data.items || []).length ? data.items : [defaultProject()];
    if (!projects.value.some((item) => item.id === activeProjectId.value)) {
      activeProjectId.value = projects.value[0]?.id || "default";
    }
  } catch (error) {
    projects.value = [defaultProject()];
    knowledgeStatus.value = `项目列表读取失败：${(error as Error).message}`;
  }
}

function pickDefaultKnowledgeId(items: ProjectKnowledge[]) {
  const projectDefaultId = String(activeProject.value.default_knowledge_base_id || "").trim();
  if (projectDefaultId && items.some((item) => item.id === projectDefaultId)) {
    return projectDefaultId;
  }
  if (items.some((item) => item.id === activeKnowledgeId.value)) {
    return activeKnowledgeId.value;
  }
  return items[0]?.id || projectDefaultId || "default";
}

async function loadKnowledge(projectId = activeProjectId.value) {
  const normalizedProjectId = String(projectId || "default").trim() || "default";
  knowledgeStatus.value = "正在读取知识库...";
  try {
    const data = await api.listKnowledge(normalizedProjectId);
    knowledgeItems.value = (data.items || []).length
      ? data.items
      : [{ id: `${normalizedProjectId}_default_kb`, project_id: normalizedProjectId, title: "项目知识库", content: "" }];
    activeKnowledgeId.value = pickDefaultKnowledgeId(knowledgeItems.value);
    knowledgeStatus.value = `知识库已加载：${activeProject.value.title || activeProjectId.value}`;
  } catch (error) {
    knowledgeStatus.value = `知识库读取失败：${(error as Error).message}`;
  }
}

function knowledgeItemsMatchProject(projectId: string) {
  const normalizedProjectId = String(projectId || "default").trim() || "default";
  return knowledgeItems.value.length > 0 && knowledgeItems.value.every((item) => {
    return String(item.project_id || "default") === normalizedProjectId;
  });
}

async function ensureTaskProjectContext(task: TaskItem) {
  const taskProjectId = String(task.payload?.project_id || task.project_id || "default").trim() || "default";
  if (activeProjectId.value === taskProjectId && knowledgeItemsMatchProject(taskProjectId)) {
    return;
  }
  activeProjectId.value = taskProjectId;
  await loadKnowledge(taskProjectId);
}

async function selectProject(projectId: string) {
  const nextId = String(projectId || "default").trim() || "default";
  const projectChanged = activeProjectId.value !== nextId;
  activeProjectId.value = nextId;
  if (projectChanged || !knowledgeItemsMatchProject(nextId)) {
    await loadKnowledge(nextId);
  }
}

async function createProject() {
  knowledgeSaving.value = true;
  knowledgeStatus.value = "正在新建项目...";
  try {
    const title = `新项目 ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
    const project = await api.createProject({ title });
    await loadProjects();
    await selectProject(project.id);
    knowledgeStatus.value = `已新建项目：${project.title || project.id}`;
  } catch (error) {
    knowledgeStatus.value = `新建项目失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

async function deleteProject(projectId = activeProjectId.value) {
  const normalizedProjectId = String(projectId || "").trim();
  if (!normalizedProjectId) return;
  const target = projects.value.find((item) => item.id === normalizedProjectId);
  const targetTitle = target?.title || normalizedProjectId;
  const confirmed = window.confirm(`确定删除项目“${targetTitle}”吗？项目知识库会一起删除；如项目内还有任务，需要先删除任务。`);
  if (!confirmed) return;

  projectSaving.value = true;
  projectStatus.value = "正在删除项目...";
  try {
    const result = await api.deleteProject(normalizedProjectId);
    projects.value = Array.isArray(result.items) && result.items.length
      ? result.items
      : projects.value.filter((item) => item.id !== normalizedProjectId);
    const replacementId = String(result.replacement_project_id || "").trim();
    activeProjectId.value = replacementId
      || projects.value.find((item) => item.id !== normalizedProjectId)?.id
      || projects.value[0]?.id
      || "default";
    await loadKnowledge(activeProjectId.value);
    projectStatus.value = `已删除项目：${targetTitle}`;
    knowledgeStatus.value = `已切换到项目：${activeProject.value.title || activeProjectId.value}`;
  } catch (error) {
    projectStatus.value = `删除项目失败：${(error as Error).message}`;
    knowledgeStatus.value = projectStatus.value;
  } finally {
    projectSaving.value = false;
  }
}

async function setProjectDefaultKnowledge(knowledgeId = activeKnowledgeId.value) {
  const project = activeProject.value;
  const selectedId = String(knowledgeId || "").trim();
  if (!project.id || !selectedId) return;
  knowledgeSaving.value = true;
  knowledgeStatus.value = "正在设置项目默认知识库...";
  try {
    const updated = await api.updateProject(project.id, {
      default_knowledge_base_id: selectedId,
    });
    const index = projects.value.findIndex((item) => item.id === updated.id);
    if (index >= 0) {
      projects.value.splice(index, 1, updated);
    } else {
      projects.value.push(updated);
    }
    activeProjectId.value = updated.id;
    activeKnowledgeId.value = selectedId;
    knowledgeStatus.value = `已设置默认知识库：${activeKnowledge.value.title || selectedId}`;
  } catch (error) {
    knowledgeStatus.value = `设置默认知识库失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

async function saveProjectSettings(payload: Partial<Project>) {
  const projectId = String(payload.id || activeProjectId.value || "default").trim() || "default";
  projectSaving.value = true;
  projectStatus.value = "正在保存项目设置...";
  try {
    const updated = await api.updateProject(projectId, payload);
    const index = projects.value.findIndex((item) => item.id === updated.id);
    if (index >= 0) {
      projects.value.splice(index, 1, updated);
    } else {
      projects.value.push(updated);
    }
    activeProjectId.value = updated.id;
    projectStatus.value = "项目设置已保存。新建任务会使用这些配置作为可见默认值。";
    await loadKnowledge(updated.id);
  } catch (error) {
    projectStatus.value = `项目设置保存失败：${(error as Error).message}`;
  } finally {
    projectSaving.value = false;
  }
}

async function saveKnowledge(payload: { id: string; title: string; content: string }) {
  knowledgeSaving.value = true;
  knowledgeStatus.value = "正在保存知识库...";
  try {
    const item = await api.updateKnowledge(payload.id, {
      project_id: activeProjectId.value,
      title: payload.title,
      content: payload.content,
    });
    const index = knowledgeItems.value.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) {
      knowledgeItems.value.splice(index, 1, item);
    } else {
      knowledgeItems.value.push(item);
    }
    activeKnowledgeId.value = item.id;
    knowledgeStatus.value = item.updated_at
      ? `知识库 ${item.title} 已保存。最后更新：${item.updated_at}`
      : `知识库 ${item.title} 已保存。`;
  } catch (error) {
    knowledgeStatus.value = `保存失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

async function createKnowledge() {
  knowledgeSaving.value = true;
  knowledgeStatus.value = "正在新建知识库...";
  try {
    const item = await api.createKnowledge({
      project_id: activeProjectId.value,
      title: "新知识库",
      content: "",
    });
    knowledgeItems.value.push(item);
    activeKnowledgeId.value = item.id;
    knowledgeStatus.value = `已新建知识库：${item.title || item.id}`;
  } catch (error) {
    knowledgeStatus.value = `新建失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

async function importKnowledge(file: File) {
  if (!file) return;
  knowledgeSaving.value = true;
  knowledgeStatus.value = `正在导入知识库：${file.name}`;
  try {
    const item = await api.importKnowledge(activeProjectId.value, file);
    const index = knowledgeItems.value.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) {
      knowledgeItems.value.splice(index, 1, item);
    } else {
      knowledgeItems.value.push(item);
    }
    activeKnowledgeId.value = item.id;
    knowledgeStatus.value = `已导入知识库：${item.title || file.name}`;
  } catch (error) {
    knowledgeStatus.value = `导入失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

async function deleteKnowledge(knowledgeId = activeKnowledgeId.value) {
  const normalizedKnowledgeId = String(knowledgeId || "").trim();
  if (!normalizedKnowledgeId) return;
  const target = knowledgeItems.value.find((item) => item.id === normalizedKnowledgeId);
  const targetTitle = target?.title || normalizedKnowledgeId;
  const confirmed = window.confirm(`确定删除知识库“${targetTitle}”吗？删除后不可恢复。`);
  if (!confirmed) return;

  knowledgeSaving.value = true;
  knowledgeStatus.value = "正在删除知识库...";
  try {
    const result = await api.deleteKnowledge(normalizedKnowledgeId, activeProjectId.value);
    if (Array.isArray(result.items) && result.items.length) {
      knowledgeItems.value = result.items;
    } else {
      knowledgeItems.value = knowledgeItems.value.filter((item) => item.id !== normalizedKnowledgeId);
    }
    const replacementId = String(result.replacement_knowledge_base_id || "").trim();
    activeKnowledgeId.value = replacementId
      || knowledgeItems.value.find((item) => item.id !== normalizedKnowledgeId)?.id
      || knowledgeItems.value[0]?.id
      || "default";
    await loadProjects();
    knowledgeStatus.value = `已删除知识库：${targetTitle}`;
  } catch (error) {
    knowledgeStatus.value = `删除失败：${(error as Error).message}`;
  } finally {
    knowledgeSaving.value = false;
  }
}

function resetProjectState() {
  projects.value = [];
  activeProjectId.value = "default";
  knowledgeItems.value = [];
  activeKnowledgeId.value = "default";
  knowledgeStatus.value = "正在读取知识库...";
  knowledgeSaving.value = false;
  projectStatus.value = "项目配置用于预填任务表单，不会在后台静默覆盖本次任务选择。";
  projectSaving.value = false;
}

export function useProjectKnowledgeState() {
  return {
    projects,
    activeProjectId,
    activeProject,
    knowledgeItems,
    activeKnowledgeId,
    activeKnowledge,
    knowledgeStatus,
    knowledgeSaving,
    projectStatus,
    projectSaving,
    loadProjects,
    loadKnowledge,
    knowledgeItemsMatchProject,
    ensureTaskProjectContext,
    selectProject,
    createProject,
    deleteProject,
    setProjectDefaultKnowledge,
    saveProjectSettings,
    saveKnowledge,
    createKnowledge,
    importKnowledge,
    deleteKnowledge,
    resetProjectState,
  };
}
