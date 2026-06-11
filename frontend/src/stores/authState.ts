import { computed, ref } from "vue";
import { api } from "../api/client";
import type { CurrentUser } from "../types";

const currentUser = ref<CurrentUser | null>(null);
const authChecked = ref(false);
const authLoading = ref(false);
const authStatus = ref("");

const isAuthenticated = computed(() => Boolean(currentUser.value?.id));

function applySession(user: CurrentUser | null) {
  currentUser.value = user && user.id ? user : null;
}

async function initAuth() {
  if (authChecked.value || authLoading.value) return isAuthenticated.value;
  authLoading.value = true;
  try {
    const session = await api.authMe();
    applySession(session.authenticated ? session.user : null);
    authStatus.value = currentUser.value ? "已登录" : "请先登录";
  } catch {
    applySession(null);
    authStatus.value = "请先登录";
  } finally {
    authChecked.value = true;
    authLoading.value = false;
  }
  return isAuthenticated.value;
}

async function login(username: string, password: string) {
  authLoading.value = true;
  authStatus.value = "正在登录...";
  try {
    const session = await api.login({ username, password });
    applySession(session.user);
    authChecked.value = true;
    authStatus.value = "已登录";
    return currentUser.value;
  } catch (error) {
    authStatus.value = `登录失败：${(error as Error).message}`;
    throw error;
  } finally {
    authLoading.value = false;
  }
}

async function register(username: string, password: string, displayName = "") {
  authLoading.value = true;
  authStatus.value = "正在注册...";
  try {
    const session = await api.register({ username, password, display_name: displayName });
    applySession(session.user);
    authChecked.value = true;
    authStatus.value = "已注册并登录";
    return currentUser.value;
  } catch (error) {
    authStatus.value = `注册失败：${(error as Error).message}`;
    throw error;
  } finally {
    authLoading.value = false;
  }
}

async function logout() {
  authLoading.value = true;
  try {
    await api.logout();
  } catch {
    // Local logout should still clear client state if the backend is unreachable.
  } finally {
    applySession(null);
    authChecked.value = true;
    authStatus.value = "已退出登录";
    authLoading.value = false;
  }
}

function resetAuthCheck() {
  authChecked.value = false;
}

export function useAuthState() {
  return {
    currentUser,
    isAuthenticated,
    authChecked,
    authLoading,
    authStatus,
    initAuth,
    login,
    register,
    logout,
    resetAuthCheck,
  };
}
