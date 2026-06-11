import { ref } from "vue";
import { api } from "../api/client";
import type { RuntimeStatus, VoiceProfile, WorkflowTemplate } from "../types";

const runtime = ref<RuntimeStatus | null>(null);
const runtimeLoading = ref(false);
const voiceProfiles = ref<VoiceProfile[]>([]);
const workflowTemplates = ref<WorkflowTemplate[]>([]);

async function loadRuntime() {
  runtimeLoading.value = true;
  try {
    runtime.value = await api.runtime();
  } catch {
    runtime.value = null;
  } finally {
    runtimeLoading.value = false;
  }
}

async function loadVoiceProfiles() {
  try {
    const data = await api.listVoiceProfiles();
    voiceProfiles.value = data.items || [];
  } catch {
    voiceProfiles.value = [];
  }
}

async function loadWorkflowTemplates() {
  try {
    const data = await api.listWorkflowTemplates();
    workflowTemplates.value = data.items || [];
  } catch {
    workflowTemplates.value = [];
  }
}

function resetRuntimeState() {
  runtime.value = null;
  runtimeLoading.value = false;
  voiceProfiles.value = [];
  workflowTemplates.value = [];
}

export function useRuntimeState() {
  return {
    runtime,
    runtimeLoading,
    voiceProfiles,
    workflowTemplates,
    loadRuntime,
    loadVoiceProfiles,
    loadWorkflowTemplates,
    resetRuntimeState,
  };
}
