<script setup lang="ts">
import type { TaskEvent } from "../types";
import { eventDetailLabel, eventTypeLabel, formatDate, stageLabel } from "../utils/format";

defineProps<{
  events: TaskEvent[];
}>();
</script>

<template>
  <details class="task-section" open>
    <summary>
      <div><strong>执行事件</strong><small>ASR、写稿、配音、选片、渲染阶段日志</small></div>
      <span class="section-pill">{{ events.length }} 条</span>
    </summary>
    <div class="task-section-body task-events-body">
      <div class="event-timeline">
        <article v-for="event in events" :key="event.id || `${event.created_at}-${event.event_type}`" class="event-item">
          <div class="event-dot"></div>
          <div class="event-main">
            <div class="event-head">
              <strong>{{ eventTypeLabel(event.event_type) }}</strong>
              <span>{{ formatDate(event.created_at) }}</span>
            </div>
            <div class="event-meta">
              <span>{{ stageLabel(event.stage) }}</span>
              <span>{{ Number(event.progress || 0) }}%</span>
              <span>{{ event.status || "--" }}</span>
            </div>
            <p v-if="event.message">{{ event.message }}</p>
            <p v-if="eventDetailLabel(event.detail)" class="muted">{{ eventDetailLabel(event.detail) }}</p>
          </div>
        </article>
        <div v-if="!events.length" class="plan-empty">这个任务还没有阶段事件。</div>
      </div>
    </div>
  </details>
</template>
