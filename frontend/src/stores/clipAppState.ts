import { useProjectKnowledgeState } from "./projectKnowledgeState";
import { useRuntimeState } from "./runtimeState";
import { useTaskState } from "./taskState";
import { useAuthState } from "./authState";

const runtimeState = useRuntimeState();
const projectState = useProjectKnowledgeState();
const taskState = useTaskState();
const authState = useAuthState();

let bootstrapPromise: Promise<void> | null = null;

async function selectProject(projectId: string) {
  await projectState.selectProject(projectId);
  await taskState.loadHistory(projectState.activeProjectId.value);
}

async function createProject() {
  await projectState.createProject();
  await taskState.loadHistory(projectState.activeProjectId.value);
}

async function runBootstrap() {
  const authenticated = await authState.initAuth();
  if (!authenticated) {
    return;
  }
  await Promise.all([
    runtimeState.loadRuntime(),
    runtimeState.loadVoiceProfiles(),
    runtimeState.loadWorkflowTemplates(),
    projectState.loadProjects(),
  ]);
  await Promise.all([
    projectState.loadKnowledge(projectState.activeProjectId.value),
    taskState.loadHistory(projectState.activeProjectId.value),
  ]);
}

async function bootstrap() {
  if (bootstrapPromise) {
    return bootstrapPromise;
  }
  bootstrapPromise = runBootstrap().finally(() => {
    bootstrapPromise = null;
  });
  return bootstrapPromise;
}

async function logout() {
  taskState.resetTaskState();
  runtimeState.resetRuntimeState();
  projectState.resetProjectState();
  await authState.logout();
}

export function useClipAppState() {
  return {
    currentUser: authState.currentUser,
    isAuthenticated: authState.isAuthenticated,
    authChecked: authState.authChecked,
    authLoading: authState.authLoading,
    authStatus: authState.authStatus,
    runtime: runtimeState.runtime,
    runtimeLoading: runtimeState.runtimeLoading,
    tasks: taskState.tasks,
    activeTaskId: taskState.activeTaskId,
    activeTask: taskState.activeTask,
    taskPlans: taskState.taskPlans,
    plansLoading: taskState.plansLoading,
    voiceProfiles: runtimeState.voiceProfiles,
    workflowTemplates: runtimeState.workflowTemplates,
    projects: projectState.projects,
    activeProjectId: projectState.activeProjectId,
    activeProject: projectState.activeProject,
    knowledgeItems: projectState.knowledgeItems,
    activeKnowledgeId: projectState.activeKnowledgeId,
    activeKnowledge: projectState.activeKnowledge,
    knowledgeStatus: projectState.knowledgeStatus,
    knowledgeSaving: projectState.knowledgeSaving,
    projectStatus: projectState.projectStatus,
    projectSaving: projectState.projectSaving,
    historyStatus: taskState.historyStatus,
    loadRuntime: runtimeState.loadRuntime,
    loadVoiceProfiles: runtimeState.loadVoiceProfiles,
    loadWorkflowTemplates: runtimeState.loadWorkflowTemplates,
    loadProjects: projectState.loadProjects,
    loadKnowledge: projectState.loadKnowledge,
    selectProject,
    createProject,
    deleteProject: projectState.deleteProject,
    setProjectDefaultKnowledge: projectState.setProjectDefaultKnowledge,
    saveProjectSettings: projectState.saveProjectSettings,
    saveKnowledge: projectState.saveKnowledge,
    createKnowledge: projectState.createKnowledge,
    importKnowledge: projectState.importKnowledge,
    deleteKnowledge: projectState.deleteKnowledge,
    loadHistory: taskState.loadHistory,
    loadTask: taskState.loadTask,
    openTask: taskState.openTask,
    loadTaskPlans: taskState.loadTaskPlans,
    stopPolling: taskState.stopPolling,
    startPolling: taskState.startPolling,
    handleTaskCreated: taskState.handleTaskCreated,
    deleteTask: taskState.deleteTask,
    clearFinishedTasks: taskState.clearFinishedTasks,
    saveDraft: taskState.saveDraft,
    approveDraft: taskState.approveDraft,
    replanTask: taskState.replanTask,
    retryAlignment: taskState.retryAlignment,
    login: authState.login,
    register: authState.register,
    logout,
    initAuth: authState.initAuth,
    bootstrap,
  };
}
