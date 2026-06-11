import { createRouter, createWebHistory } from "vue-router";
import CreateTaskView from "../views/CreateTaskView.vue";
import DashboardView from "../views/DashboardView.vue";
import KnowledgeView from "../views/KnowledgeView.vue";
import ProjectSettingsView from "../views/ProjectSettingsView.vue";
import ProjectWorkspaceView from "../views/ProjectWorkspaceView.vue";
import RuntimeView from "../views/RuntimeView.vue";
import TaskDetailView from "../views/TaskDetailView.vue";
import TasksView from "../views/TasksView.vue";
import LoginView from "../views/LoginView.vue";
import { useAuthState } from "../stores/authState";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/projects/:projectId", name: "project-workspace", component: ProjectWorkspaceView, props: true },
    { path: "/projects/:projectId/settings", name: "project-settings", component: ProjectSettingsView, props: true },
    { path: "/projects/:projectId/create", name: "project-create", component: CreateTaskView, props: true },
    { path: "/projects/:projectId/tasks", name: "project-tasks", component: TasksView, props: true },
    { path: "/projects/:projectId/tasks/:id", name: "project-task-detail", component: TaskDetailView, props: true },
    { path: "/projects/:projectId/knowledge", name: "project-knowledge", component: KnowledgeView, props: true },
    { path: "/create", name: "create", component: CreateTaskView },
    { path: "/tasks", name: "tasks", component: TasksView },
    { path: "/tasks/:id", name: "task-detail", component: TaskDetailView, props: true },
    { path: "/knowledge", name: "knowledge", component: KnowledgeView },
    { path: "/runtime", name: "runtime", component: RuntimeView },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthState();
  const authenticated = await auth.initAuth();
  if (!authenticated && !to.meta.public) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (authenticated && to.name === "login") {
    return { name: "dashboard" };
  }
  return true;
});
