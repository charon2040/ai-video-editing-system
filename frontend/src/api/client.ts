import type {
  AuthSession,
  ClipPlan,
  Project,
  ProjectDeleteResult,
  ProjectKnowledge,
  ProjectKnowledgeDeleteResult,
  RuntimeStatus,
  TaskDeleteResult,
  TaskEvent,
  TaskItem,
  VoiceProfile,
  WorkflowTemplate,
} from "../types";

function parseErrorMessage(rawText: string): string {
  const text = String(rawText || "").trim();
  if (!text) return "";
  try {
    const payload = JSON.parse(text);
    if (typeof payload?.detail === "string") return payload.detail;
    if (Array.isArray(payload?.detail)) {
      return payload.detail
        .map((item: any) => String(item?.msg || item || "").trim())
        .filter(Boolean)
        .join("; ");
    }
    if (payload?.message) return String(payload.message);
  } catch {
    return text;
  }
  return text;
}

export async function apiRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(parseErrorMessage(text) || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  authMe: () => apiRequest<AuthSession>("/api/auth/me"),
  login: (payload: { username: string; password: string }) => apiRequest<AuthSession>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  register: (payload: { username: string; password: string; display_name?: string }) => apiRequest<AuthSession>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  logout: () => apiRequest<{ authenticated: boolean }>("/api/auth/logout", { method: "POST" }),
  listTasks: (projectId = "") => apiRequest<{ items: TaskItem[] }>(
    `/api/tasks${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
  ),
  getTask: (taskId: string) => apiRequest<TaskItem>(`/api/tasks/${encodeURIComponent(taskId)}`),
  getTaskEvents: (taskId: string) => apiRequest<{ items: TaskEvent[] }>(`/api/tasks/${encodeURIComponent(taskId)}/events`),
  deleteTask: (taskId: string, deleteSource = false) => apiRequest<TaskDeleteResult>(
    `/api/tasks/${encodeURIComponent(taskId)}${deleteSource ? "?delete_source=true" : ""}`,
    { method: "DELETE" },
  ),
  clearFinishedTasks: (projectId = "", deleteSource = false) => apiRequest<TaskDeleteResult>(
    `/api/tasks?scope=finished${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}${deleteSource ? "&delete_source=true" : ""}`,
    { method: "DELETE" },
  ),
  listTaskPlans: (taskId: string) => apiRequest<{ items: ClipPlan[] }>(`/api/tasks/${encodeURIComponent(taskId)}/plans`),
  createTask: (formData: FormData) => apiRequest<TaskItem>("/api/tasks", { method: "POST", body: formData }),
  replanTask: (taskId: string, formData: FormData) => apiRequest<TaskItem>(`/api/tasks/${encodeURIComponent(taskId)}/replan`, { method: "POST", body: formData }),
  saveDraft: (taskId: string, formData: FormData) => apiRequest<TaskItem>(`/api/tasks/${encodeURIComponent(taskId)}/draft`, { method: "POST", body: formData }),
  approveDraft: (taskId: string, formData: FormData) => apiRequest<TaskItem>(`/api/tasks/${encodeURIComponent(taskId)}/approve-draft`, { method: "POST", body: formData }),
  retryAlignment: (taskId: string) => apiRequest<TaskItem>(`/api/tasks/${encodeURIComponent(taskId)}/retry-alignment`, { method: "POST" }),
  runtime: () => apiRequest<RuntimeStatus>("/api/runtime"),
  listWorkflowTemplates: () => apiRequest<{ items: WorkflowTemplate[] }>("/api/workflow-templates"),
  listVoiceProfiles: () => apiRequest<{ items: VoiceProfile[] }>("/api/voice-profiles"),
  createVoiceProfile: (formData: FormData) => apiRequest<VoiceProfile>("/api/voice-profiles", { method: "POST", body: formData }),
  listProjects: () => apiRequest<{ items: Project[] }>("/api/projects"),
  createProject: (payload: Partial<Project>) => apiRequest<Project>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  updateProject: (id: string, payload: Partial<Project>) => apiRequest<Project>(`/api/projects/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  deleteProject: (id: string) => apiRequest<ProjectDeleteResult>(`/api/projects/${encodeURIComponent(id)}`, {
    method: "DELETE",
  }),
  listKnowledge: (projectId = "") => apiRequest<{ items: ProjectKnowledge[] }>(
    `/api/project-knowledge${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
  ),
  createKnowledge: (payload: Pick<ProjectKnowledge, "title" | "content"> & { project_id?: string }) => apiRequest<ProjectKnowledge>("/api/project-knowledge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  importKnowledge: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append("project_id", projectId || "default");
    formData.append("file", file);
    return apiRequest<ProjectKnowledge>("/api/project-knowledge/import", {
      method: "POST",
      body: formData,
    });
  },
  updateKnowledge: (id: string, payload: Pick<ProjectKnowledge, "title" | "content"> & { project_id?: string }) => apiRequest<ProjectKnowledge>(`/api/project-knowledge/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  deleteKnowledge: (id: string, projectId = "") => apiRequest<ProjectKnowledgeDeleteResult>(
    `/api/project-knowledge/${encodeURIComponent(id)}${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
    { method: "DELETE" },
  ),
};
