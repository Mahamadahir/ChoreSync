<template>
  <div class="dash-page">

    <!-- ── Header ─────────────────────────────────────────── -->
    <div class="dash-header">
      <div>
        <div class="dash-greeting">Good {{ timeOfDay }}, {{ authStore.displayName || 'there' }} 👋</div>
        <div class="dash-date">{{ todayLabel }}</div>
      </div>
      <div v-if="calMessage" class="dash-cal-alert">{{ calMessage }}</div>
    </div>

    <!-- ── Stat cards ─────────────────────────────────────── -->
    <div class="dash-stats">
      <div class="dash-stat-card">
        <div class="dash-stat-icon">🔥</div>
        <div class="dash-stat-value">{{ statsLoading ? '—' : totalStreak }}</div>
        <div class="dash-stat-label">Day Streak</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-icon">⭐</div>
        <div class="dash-stat-value">{{ statsLoading ? '—' : totalPoints.toLocaleString() }}</div>
        <div class="dash-stat-label">Total Points</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-icon">✅</div>
        <div class="dash-stat-value">{{ tasksLoading ? '—' : pendingTasks.length }}</div>
        <div class="dash-stat-label">Due Today</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-icon">📊</div>
        <div class="dash-stat-value">{{ statsLoading ? '—' : onTimeRate }}</div>
        <div class="dash-stat-label">On-time Rate</div>
      </div>
    </div>

    <!-- ── Body ───────────────────────────────────────────── -->
    <div class="dash-body">

      <!-- Today's tasks -->
      <div class="cs-card dash-tasks-panel">
        <div class="dash-panel-title">
          Today's Tasks
          <span v-if="!tasksLoading" class="dash-panel-count">{{ pendingTasks.length }}</span>
        </div>

        <!-- Loading -->
        <div v-if="tasksLoading" style="display:flex;flex-direction:column;gap:10px">
          <div v-for="i in 3" :key="i" class="cs-skeleton" style="height:64px;border-radius:var(--cs-radius-md)" />
        </div>

        <!-- Empty -->
        <div v-else-if="pendingTasks.length === 0" class="dash-empty">
          <span class="material-symbols-outlined" style="font-size:36px;color:var(--cs-secondary)">task_alt</span>
          <div style="font-weight:600;font-size:14px">All caught up!</div>
          <div style="font-size:12px;color:var(--cs-muted)">No tasks due today.</div>
        </div>

        <!-- Task rows -->
        <div v-else class="dash-task-list">
          <div v-for="task in pendingTasks" :key="task.id" class="dash-task-row">
            <div class="dash-task-body">
              <div class="dash-task-name">{{ task.template_name }}</div>
              <div class="dash-task-meta">
                <span>{{ task.group_name }}</span>
                <span>·</span>
                <span :style="isOverdue(task.deadline) ? 'color:var(--cs-overdue)' : ''">
                  {{ formatDeadline(task.deadline) }}
                </span>
              </div>
            </div>
            <div class="dash-task-actions">
              <span :class="['cs-chip', statusChip(task.status)]">{{ task.status }}</span>
              <button
                class="dash-complete-btn"
                :disabled="completing.has(task.id)"
                @click="completeTask(task.id)"
              >
                <span class="material-symbols-outlined">{{ completing.has(task.id) ? 'hourglass_empty' : 'check' }}</span>
              </button>
            </div>
          </div>
        </div>

        <button class="dash-see-all-btn" @click="router.push({ name: 'tasks' })">
          See all tasks
          <span class="material-symbols-outlined">arrow_forward</span>
        </button>
      </div>

      <!-- Right panel -->
      <div class="dash-right">

        <!-- Smart suggestion -->
        <div v-if="suggestion" class="cs-card dash-suggestion">
          <div class="dash-suggestion-header">
            <span class="material-symbols-outlined dash-suggestion-icon">lightbulb</span>
            <span class="dash-suggestion-label">Smart Suggestion</span>
          </div>
          <div class="dash-suggestion-title">{{ suggestion.title }}</div>
          <div class="dash-suggestion-body">{{ suggestion.content }}</div>
          <div class="dash-suggestion-actions">
            <button class="dash-yes-btn" @click="dismissSuggestion">Got it</button>
            <button class="dash-no-btn" @click="dismissSuggestion">Dismiss</button>
          </div>
        </div>

        <!-- Calendar integrations -->
        <div class="cs-card dash-integrations">
          <div class="dash-panel-title" style="margin-bottom:14px">Calendar</div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <div style="display:flex;align-items:center;gap:8px">
              <button class="cs-btn-outline dash-cal-btn" style="flex:1" :disabled="connectingGoogle" @click="handleGoogleConnect">
                <span class="material-symbols-outlined" style="font-size:16px">{{ googleConnected ? 'check_circle' : 'add_link' }}</span>
                {{ connectingGoogle ? 'Redirecting…' : googleConnected ? 'Google Connected' : 'Connect Google Calendar' }}
              </button>
              <button v-if="googleConnected" class="cs-btn-outline dash-cal-btn" :disabled="syncingGoogle" @click="handleGoogleSync" title="Sync now" style="flex-shrink:0;padding:8px 12px">
                <span class="material-symbols-outlined" style="font-size:16px">sync</span>
              </button>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <button class="cs-btn-outline dash-cal-btn" style="flex:1" :disabled="connectingOutlook" @click="handleOutlookConnect">
                <span class="material-symbols-outlined" style="font-size:16px">{{ outlookConnected ? 'check_circle' : 'add_link' }}</span>
                {{ connectingOutlook ? 'Redirecting…' : outlookConnected ? 'Outlook Connected' : 'Connect Outlook' }}
              </button>
              <button v-if="outlookConnected" class="cs-btn-outline dash-cal-btn" :disabled="syncingOutlook" @click="handleOutlookSync" title="Sync now" style="flex-shrink:0;padding:8px 12px">
                <span class="material-symbols-outlined" style="font-size:16px">sync</span>
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { calendarService } from '../services/calendarService';
import { statsApi, taskApi, notificationApi } from '../services/api';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

// ── Calendar connect/sync ─────────────────────────────────
const connectingGoogle = ref(false);
const syncingGoogle = ref(false);
const connectingOutlook = ref(false);
const syncingOutlook = ref(false);
const calMessage = ref<string | null>(null);
const googleConnected = ref(false);
const outlookConnected = ref(false);

// ── Stats ─────────────────────────────────────────────────
const statsLoading = ref(true);
const statsList = ref<any[]>([]);

const totalPoints = computed(() =>
  statsList.value.reduce((s, x) => s + (x.total_points ?? 0), 0)
);
const totalStreak = computed(() =>
  statsList.value.reduce((s, x) => Math.max(s, x.current_streak_days ?? 0), 0)
);
const onTimeRate = computed(() => {
  const rates = statsList.value.map((x) => x.on_time_completion_rate ?? 0).filter((r) => r > 0);
  if (!rates.length) return '—';
  const avg = rates.reduce((s, r) => s + r, 0) / rates.length;
  return `${Math.round(avg * 100)}%`;
});

// ── Tasks ─────────────────────────────────────────────────
const tasksLoading = ref(true);
const pendingTasks = ref<any[]>([]);
const completing = ref<Set<number>>(new Set());

// ── Suggestion ────────────────────────────────────────────
const suggestion = ref<any | null>(null);

// ── Greeting ─────────────────────────────────────────────
const timeOfDay = computed(() => {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 18) return 'afternoon';
  return 'evening';
});

const todayLabel = computed(() =>
  new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
);

// ── Data loaders ──────────────────────────────────────────
async function loadStats() {
  statsLoading.value = true;
  try {
    const res = await statsApi.myStats();
    statsList.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    statsList.value = [];
  } finally {
    statsLoading.value = false;
  }
}

async function loadTasks() {
  tasksLoading.value = true;
  try {
    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];
    const res = await taskApi.myTasks({ status: 'pending' });
    const all: any[] = Array.isArray(res.data) ? res.data : [];
    // Show tasks due today or already overdue
    pendingTasks.value = all.filter((t) => {
      if (!t.deadline) return false;
      const due = t.deadline.split('T')[0];
      return due <= todayStr;
    }).slice(0, 8);
  } catch {
    pendingTasks.value = [];
  } finally {
    tasksLoading.value = false;
  }
}

async function loadSuggestion() {
  try {
    const res = await notificationApi.list();
    const notifs: any[] = Array.isArray(res.data) ? res.data : [];
    const found = notifs.find(
      (n) => !n.read && (n.type?.includes('suggestion') || n.type?.includes('reassign'))
    );
    suggestion.value = found ?? null;
  } catch {
    suggestion.value = null;
  }
}

async function completeTask(id: number) {
  completing.value = new Set([...completing.value, id]);
  try {
    await taskApi.complete(id);
    pendingTasks.value = pendingTasks.value.filter((t) => t.id !== id);
  } catch {} finally {
    const next = new Set(completing.value);
    next.delete(id);
    completing.value = next;
  }
}

function dismissSuggestion() {
  if (suggestion.value) {
    notificationApi.dismiss(suggestion.value.id).catch(() => {});
    suggestion.value = null;
  }
}

// ── Calendar helpers ──────────────────────────────────────
async function loadCalendarStatus() {
  try {
    const resp = await calendarService.getStatus();
    googleConnected.value = resp.data.google.connected;
    outlookConnected.value = resp.data.outlook.connected;
  } catch {}
}

async function handleGoogleConnect() {
  connectingGoogle.value = true;
  try {
    const resp = await calendarService.getGoogleAuthUrl();
    if (resp.data?.auth_url) window.location.href = resp.data.auth_url;
  } catch {} finally { connectingGoogle.value = false; }
}
async function handleGoogleSync() {
  syncingGoogle.value = true;
  try {
    const resp = await calendarService.syncGoogle();
    calMessage.value = resp.data?.detail || 'Google synced.';
    setTimeout(() => { calMessage.value = null; }, 4000);
  } catch { calMessage.value = 'Google sync failed.'; }
  finally { syncingGoogle.value = false; }
}
async function handleOutlookConnect() {
  connectingOutlook.value = true;
  try {
    const resp = await calendarService.getOutlookAuthUrl();
    if (resp.data?.auth_url) window.location.href = resp.data.auth_url;
  } catch {} finally { connectingOutlook.value = false; }
}
async function handleOutlookSync() {
  syncingOutlook.value = true;
  try { await calendarService.syncOutlook(); }
  catch {} finally { syncingOutlook.value = false; }
}

// ── Formatting ────────────────────────────────────────────
function formatDeadline(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffH = (d.getTime() - now.getTime()) / 3600000;
  if (diffH < 0) return 'Overdue';
  if (diffH < 1) return 'Due in < 1h';
  if (diffH < 24) return `Due in ${Math.round(diffH)}h`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function isOverdue(iso: string) {
  return iso && new Date(iso) < new Date();
}

function statusChip(status: string): string {
  const map: Record<string, string> = {
    pending: 'cs-chip--pending',
    overdue: 'cs-chip--overdue',
    completed: 'cs-chip--done',
    snoozed: 'cs-chip--snoozed',
  };
  return map[status] ?? 'cs-chip--pending';
}

onMounted(() => {
  // Handle calendar OAuth redirect back
  const syncStatus = route.query.google_sync as string | undefined;
  if (syncStatus === 'success') {
    const imported = route.query.imported as string | undefined;
    router.replace({ name: 'google-calendar-select', query: { connected: '1', imported } });
    return;
  } else if (syncStatus === 'error') {
    calMessage.value = 'Google calendar connection failed. Please try again.';
  }
  if (syncStatus) {
    const { google_sync, imported, ...rest } = route.query;
    router.replace({ query: rest });
  }

  Promise.allSettled([loadStats(), loadTasks(), loadSuggestion(), loadCalendarStatus()]);
});
</script>

<style scoped>
.dash-page {
  padding: 28px 32px;
  max-width: 1400px;
}

/* ── Header ─────────────────────────────────────────────── */
.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}
.dash-greeting {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.3px;
  color: var(--cs-on-surface);
  margin-bottom: 4px;
}
.dash-date {
  font-size: 13px;
  color: var(--cs-muted);
  font-weight: 500;
}
.dash-cal-alert {
  padding: 10px 16px;
  background: var(--cs-secondary-container);
  color: var(--cs-secondary);
  border-radius: var(--cs-radius-md);
  font-size: 13px;
  font-weight: 600;
}

/* ── Stat cards ─────────────────────────────────────────── */
.dash-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}
.dash-stat-card {
  background: var(--cs-surface-low);
  border: 1px solid var(--cs-outline-variant);
  border-radius: var(--cs-radius-lg);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: var(--cs-shadow-sm);
}
.dash-stat-icon { font-size: 22px; line-height: 1; margin-bottom: 4px; }
.dash-stat-value {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--cs-on-surface);
  line-height: 1.1;
}
.dash-stat-label {
  font-size: 12px;
  color: var(--cs-muted);
  font-weight: 500;
}

/* ── Body grid ──────────────────────────────────────────── */
.dash-body {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
  align-items: start;
}

/* ── Tasks panel ─────────────────────────────────────────── */
.dash-tasks-panel { padding: 20px; }
.dash-panel-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--cs-on-surface);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.dash-panel-count {
  background: var(--cs-primary-container);
  color: var(--cs-on-primary-container);
  font-size: 11px;
  font-weight: 700;
  border-radius: 10px;
  padding: 2px 8px;
  min-width: 20px;
  text-align: center;
}
.dash-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--cs-muted);
  text-align: center;
}
.dash-task-list { display: flex; flex-direction: column; }
.dash-task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--cs-outline-variant);
}
.dash-task-row:last-child { border-bottom: none; }
.dash-task-body { flex: 1; min-width: 0; }
.dash-task-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--cs-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}
.dash-task-meta {
  font-size: 12px;
  color: var(--cs-muted);
  display: flex;
  gap: 6px;
}
.dash-task-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.dash-complete-btn {
  width: 32px; height: 32px;
  border-radius: var(--cs-radius-sm);
  border: none;
  background: var(--cs-secondary-container);
  color: var(--cs-secondary);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}
.dash-complete-btn:hover { background: var(--cs-secondary); color: var(--cs-on-secondary); }
.dash-complete-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.dash-complete-btn .material-symbols-outlined { font-size: 16px; }
.dash-see-all-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  background: none;
  border: none;
  color: var(--cs-primary);
  font-size: 13px;
  font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  padding: 0;
  transition: gap 0.15s;
}
.dash-see-all-btn:hover { gap: 10px; }
.dash-see-all-btn .material-symbols-outlined { font-size: 16px; }

/* ── Right panel ─────────────────────────────────────────── */
.dash-right { display: flex; flex-direction: column; gap: 16px; }

/* ── Suggestion ──────────────────────────────────────────── */
.dash-suggestion { padding: 18px 20px; }
.dash-suggestion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.dash-suggestion-icon {
  font-size: 18px;
  color: var(--cs-tertiary);
  font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}
.dash-suggestion-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--cs-tertiary);
}
.dash-suggestion-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--cs-on-surface);
  margin-bottom: 6px;
}
.dash-suggestion-body {
  font-size: 13px;
  color: var(--cs-on-surface-variant);
  line-height: 1.5;
  margin-bottom: 14px;
}
.dash-suggestion-actions { display: flex; gap: 8px; }
.dash-yes-btn {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: var(--cs-radius-md);
  background: var(--cs-secondary-container);
  color: var(--cs-secondary);
  font-size: 13px; font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: background 0.15s;
}
.dash-yes-btn:hover { background: var(--cs-secondary); color: var(--cs-on-secondary); }
.dash-no-btn {
  flex: 1;
  padding: 8px;
  border: 1px solid var(--cs-outline-variant);
  border-radius: var(--cs-radius-md);
  background: transparent;
  color: var(--cs-muted);
  font-size: 13px; font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: background 0.15s;
}
.dash-no-btn:hover { background: var(--cs-surface); }

/* ── Integrations ────────────────────────────────────────── */
.dash-integrations { padding: 18px 20px; }
.dash-cal-btn { width: 100%; justify-content: flex-start; font-size: 13px; }

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width: 900px) {
  .dash-stats { grid-template-columns: repeat(2, 1fr); }
  .dash-body { grid-template-columns: 1fr; }
}
</style>
