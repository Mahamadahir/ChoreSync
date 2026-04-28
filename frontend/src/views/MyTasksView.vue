<template>
  <div class="cs-page">
    <div class="cs-page-header">
      <div class="cs-page-title">My Tasks</div>
    </div>

    <!-- Filter tabs -->
    <div class="cs-filter-tabs">
      <button
        v-for="opt in filterOptions"
        :key="opt.value"
        :class="['cs-filter-tab', { 'cs-filter-tab--active': statusFilter === opt.value }]"
        @click="setFilter(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="cs-error-msg" style="margin-bottom:16px">{{ error }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading" style="display:flex;flex-direction:column;gap:12px">
      <div v-for="i in 4" :key="i" class="cs-skeleton" style="height:72px;border-radius:var(--cs-radius-md)" />
    </div>

    <!-- Empty state -->
    <div v-else-if="tasks.length === 0" class="cs-empty">
      <span class="material-symbols-outlined">task_alt</span>
      <div class="cs-empty-title">No tasks here</div>
      <div class="cs-empty-sub">You're all caught up!</div>
    </div>

    <!-- Two-panel layout -->
    <div v-else class="cs-tasks-layout">
      <!-- Left: task list -->
      <div class="cs-tasks-list cs-card" style="padding:0;overflow:hidden">
        <div
          v-for="task in tasks"
          :key="task.id"
          :class="['cs-task-item', { 'cs-task-item--active': selectedTask?.id === task.id }]"
          @click="selectedTask = task"
        >
          <div class="cs-task-body">
            <div class="cs-task-name">{{ task.template_name }}</div>
            <div class="cs-task-meta">
              <span>{{ task.group_name }}</span>
              <span>·</span>
              <span>Due {{ formatDeadline(task.deadline) }}</span>
            </div>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
              <span :class="['cs-chip', statusChipClass(task.status)]">{{ task.status }}</span>
              <span v-if="task.snooze_count" class="cs-chip cs-chip--snoozed">Snoozed ×{{ task.snooze_count }}</span>
              <span v-if="task.on_marketplace" class="cs-chip" style="background:var(--cs-tertiary-container);color:var(--cs-tertiary)">Marketplace</span>
            </div>
          </div>
          <span class="material-symbols-outlined" style="color:var(--cs-outline);font-size:18px">chevron_right</span>
        </div>
      </div>

      <!-- Right: task detail -->
      <div class="cs-task-detail cs-card" v-if="selectedTask">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px">
          <div>
            <div style="font-size:18px;font-weight:700;color:var(--cs-on-surface);margin-bottom:4px">
              {{ selectedTask.template_name }}
            </div>
            <div style="font-size:13px;color:var(--cs-muted)">{{ selectedTask.group_name }}</div>
          </div>
          <span :class="['cs-chip', statusChipClass(selectedTask.status)]">{{ selectedTask.status }}</span>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
          <div class="cs-card" style="padding:14px;background:var(--cs-surface)">
            <div class="cs-section-title" style="margin-bottom:4px">Due</div>
            <div style="font-size:14px;font-weight:600">{{ formatDeadline(selectedTask.deadline) }}</div>
          </div>
          <div v-if="selectedTask.points_earned" class="cs-card" style="padding:14px;background:var(--cs-surface)">
            <div class="cs-section-title" style="margin-bottom:4px">Points</div>
            <div style="font-size:14px;font-weight:600;color:var(--cs-tertiary)">⭐ {{ selectedTask.points_earned }}</div>
          </div>
        </div>

        <!-- Primary action -->
        <button
          v-if="selectedTask.status === 'pending' || selectedTask.status === 'snoozed'"
          class="cs-btn-primary"
          style="width:100%;justify-content:center;padding:14px;margin-bottom:12px"
          @click="completeTask(selectedTask.id)"
        >
          <span class="material-symbols-outlined">check_circle</span>
          Mark Complete
        </button>
        <button
          v-if="selectedTask.status === 'completed'"
          class="cs-btn-outline"
          style="width:100%;justify-content:center;padding:14px;margin-bottom:12px;border-color:var(--cs-warning,#f59e0b);color:var(--cs-warning,#f59e0b)"
          @click="uncompleteTask(selectedTask.id)"
        >
          <span class="material-symbols-outlined">undo</span>
          Reopen Task
        </button>

        <!-- Secondary actions -->
        <div
          v-if="selectedTask.status === 'pending' || selectedTask.status === 'snoozed'"
          style="display:grid;grid-template-columns:1fr 1fr;gap:8px"
        >
          <button class="cs-btn-outline" style="justify-content:center" @click="openSnooze(selectedTask)">
            <span class="material-symbols-outlined" style="font-size:18px">snooze</span>
            Snooze
          </button>
          <button class="cs-btn-outline" style="justify-content:center" @click="openSwap(selectedTask)">
            <span class="material-symbols-outlined" style="font-size:18px">swap_horiz</span>
            Swap
          </button>
          <button
            v-if="selectedTask.status === 'pending'"
            class="cs-btn-outline"
            style="justify-content:center;border-color:var(--cs-error);color:var(--cs-error)"
            @click="openEmergencyConfirm"
          >
            <span class="material-symbols-outlined" style="font-size:18px">emergency</span>
            Emergency
          </button>
          <button
            v-if="!selectedTask.on_marketplace"
            class="cs-btn-outline"
            style="justify-content:center"
            @click="openListMarketplace(selectedTask)"
          >
            <span class="material-symbols-outlined" style="font-size:18px">storefront</span>
            Marketplace
          </button>
          <button
            v-if="selectedTask.on_marketplace"
            class="cs-btn-outline"
            style="justify-content:center;border-color:var(--cs-error);color:var(--cs-error)"
            :disabled="cancellingMarketplace"
            @click="cancelMarketplace(selectedTask.id)"
          >
            <span class="material-symbols-outlined" style="font-size:18px">remove_shopping_cart</span>
            {{ cancellingMarketplace ? 'Removing…' : 'Remove Listing' }}
          </button>
        </div>
      </div>

      <div v-else class="cs-task-detail cs-empty" style="border:1px solid var(--cs-outline-variant);border-radius:var(--cs-radius-lg)">
        <span class="material-symbols-outlined">touch_app</span>
        <div class="cs-empty-sub">Select a task to see details</div>
      </div>
    </div>

    <!-- Incoming swaps section -->
    <template v-if="incomingSwaps.length > 0">
      <div class="cs-section-title" style="margin-top:32px;margin-bottom:12px">Incoming Swap Requests</div>
      <div class="cs-card" style="padding:0;overflow:hidden;max-width:720px">
        <div
          v-for="swap in incomingSwaps"
          :key="swap.id"
          style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:16px 20px;border-bottom:1px solid var(--cs-outline-variant)"
        >
          <div>
            <div style="font-size:14px;font-weight:600;margin-bottom:3px">{{ swap.task_name ?? `Task #${swap.task_id}` }}</div>
            <div style="font-size:12px;color:var(--cs-muted)">
              {{ swap.group_name }} · From {{ swap.from_username ?? swap.from_user_id }}
              <span style="margin-left:4px;padding:2px 8px;border-radius:4px;font-weight:600;font-size:11px"
                :style="swap.swap_type === 'open_request' ? 'background:#dbeafe;color:#1d4ed8' : 'background:var(--cs-primary-container);color:var(--cs-primary)'">
                {{ swap.swap_type === 'open_request' ? 'Open' : 'Direct' }}
              </span>
            </div>
            <div v-if="swap.reason" style="font-size:12px;color:var(--cs-on-surface-variant);margin-top:4px">{{ swap.reason }}</div>
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0">
            <button
              class="cs-btn-primary"
              style="padding:7px 14px;font-size:13px;gap:4px"
              :disabled="swapRespondLoading[swap.id] === 'accept'"
              @click="respondSwap(swap.id, true)"
            >
              <span class="material-symbols-outlined" style="font-size:16px">check</span>
              Accept
            </button>
            <button
              class="cs-btn-outline"
              style="padding:7px 14px;font-size:13px;gap:4px;border-color:var(--cs-error);color:var(--cs-error)"
              :disabled="swapRespondLoading[swap.id] === 'reject'"
              @click="respondSwap(swap.id, false)"
            >
              <span class="material-symbols-outlined" style="font-size:16px">close</span>
              Decline
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- Snooze dialog -->
    <q-dialog v-model="snoozeDialog.show">
      <q-card style="min-width:340px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Snooze Task</div>
          <div style="font-size:13px;color:var(--cs-muted)">{{ snoozeDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="snoozeDialog.until" type="datetime-local" label="Snooze until" outlined />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="warning" label="Snooze" :loading="snoozeDialog.loading" @click="submitSnooze" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Swap dialog -->
    <q-dialog v-model="swapDialog.show">
      <q-card style="min-width:360px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Request Swap</div>
          <div style="font-size:13px;color:var(--cs-muted)">{{ swapDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model="swapDialog.targetUserId" label="Target user ID (leave blank to broadcast)" outlined />
          <q-input v-model="swapDialog.reason" label="Reason (optional)" outlined />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Send Request" :loading="swapDialog.loading" @click="submitSwap" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Emergency confirm dialog -->
    <q-dialog v-model="emergencyDialog">
      <q-card style="min-width:340px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Emergency Reassign</div>
          <div style="font-size:13px;color:var(--cs-muted);margin-top:6px">
            This will immediately reassign the task to another member. Are you sure?
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="negative" label="Reassign" @click="submitEmergency" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Marketplace listing dialog -->
    <q-dialog v-model="listMarketplaceDialog.show">
      <q-card style="min-width:360px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">List on Marketplace</div>
          <div style="font-size:13px;color:var(--cs-muted)">{{ listMarketplaceDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section>
          <q-input
            v-model.number="listMarketplaceDialog.bonusPoints"
            type="number"
            label="Bonus points (optional)"
            hint="Offer bonus points to incentivise someone to take this task"
            outlined
            min="0"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="List Task" :loading="listMarketplaceDialog.loading" @click="submitListMarketplace" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { taskApi, marketplaceApi } from '../services/api';
import { NotificationSocketService } from '../services/NotificationSocketService';

const socketSvc = new NotificationSocketService();

type Task = {
  id: number;
  template_name: string;
  group_id: string;
  group_name: string;
  status: string;
  deadline: string;
  points_earned: number;
  snooze_count: number;
  swap_id: number | null;
  on_marketplace?: boolean;
  marketplace_listing_id?: number | null;
};

type IncomingSwap = {
  id: number;
  task_id: number;
  task_name: string | null;
  group_name: string | null;
  from_user_id: string | null;
  from_username: string | null;
  swap_type: string;
  status: string;
  reason: string | null;
  expires_at: string;
};

const tasks = ref<Task[]>([]);
const selectedTask = ref<Task | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const statusFilter = ref('');
const emergencyDialog = ref(false);

const filterOptions = [
  { label: 'All',     value: '' },
  { label: 'Active',  value: 'pending' },
  { label: 'Done',    value: 'completed' },
  { label: 'Overdue', value: 'overdue' },
];

const snoozeDialog = ref({ show: false, task: null as Task | null, until: '', loading: false });
const swapDialog = ref({ show: false, task: null as Task | null, targetUserId: '', reason: '', loading: false });
const listMarketplaceDialog = ref({ show: false, task: null as Task | null, bonusPoints: 0, loading: false });
const cancellingMarketplace = ref(false);
const incomingSwaps = ref<IncomingSwap[]>([]);
const swapRespondLoading = ref<Record<number, 'accept' | 'reject' | null>>({});

function setFilter(val: string) {
  statusFilter.value = val;
  selectedTask.value = null;
  loadTasks();
}

async function loadTasks() {
  loading.value = true;
  error.value = null;
  try {
    const params = statusFilter.value ? { status: statusFilter.value } : {};
    const res = await taskApi.myTasks(params);
    tasks.value = res.data;
  } catch {
    error.value = 'Failed to load tasks.';
  } finally {
    loading.value = false;
  }
}

async function loadIncomingSwaps() {
  try {
    const res = await taskApi.pendingSwaps();
    incomingSwaps.value = res.data;
  } catch {}
}

async function completeTask(id: number) {
  try {
    await taskApi.complete(id, true);
    selectedTask.value = null;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to complete task.';
  }
}

async function uncompleteTask(id: number) {
  try {
    await taskApi.complete(id, false);
    selectedTask.value = null;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to reopen task.';
  }
}

function openSnooze(task: Task) {
  snoozeDialog.value = { show: true, task, until: '', loading: false };
}

async function submitSnooze() {
  if (!snoozeDialog.value.until || !snoozeDialog.value.task) return;
  snoozeDialog.value.loading = true;
  try {
    await taskApi.snooze(snoozeDialog.value.task.id, {
      snooze_until: new Date(snoozeDialog.value.until).toISOString(),
    });
    snoozeDialog.value.show = false;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to snooze.';
  } finally {
    snoozeDialog.value.loading = false;
  }
}

function openSwap(task: Task) {
  swapDialog.value = { show: true, task, targetUserId: '', reason: '', loading: false };
}

async function submitSwap() {
  if (!swapDialog.value.task) return;
  swapDialog.value.loading = true;
  try {
    await taskApi.createSwap(swapDialog.value.task.id, {
      to_user_id: swapDialog.value.targetUserId || undefined,
      reason: swapDialog.value.reason,
    });
    swapDialog.value.show = false;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to request swap.';
  } finally {
    swapDialog.value.loading = false;
  }
}

function openEmergencyConfirm() {
  emergencyDialog.value = true;
}

async function submitEmergency() {
  if (!selectedTask.value) return;
  emergencyDialog.value = false;
  try {
    await taskApi.emergencyReassign(selectedTask.value.id, {});
    selectedTask.value = null;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to emergency reassign.';
  }
}

async function respondSwap(swapId: number, accept: boolean) {
  swapRespondLoading.value[swapId] = accept ? 'accept' : 'reject';
  try {
    await taskApi.respondSwap(swapId, accept);
    await Promise.all([loadTasks(), loadIncomingSwaps()]);
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to respond to swap.';
  } finally {
    swapRespondLoading.value[swapId] = null;
  }
}

function openListMarketplace(task: Task) {
  listMarketplaceDialog.value = { show: true, task, bonusPoints: 0, loading: false };
}

async function submitListMarketplace() {
  if (!listMarketplaceDialog.value.task) return;
  listMarketplaceDialog.value.loading = true;
  try {
    await taskApi.listMarketplace(listMarketplaceDialog.value.task.id, {
      bonus_points: listMarketplaceDialog.value.bonusPoints || 0,
    });
    listMarketplaceDialog.value.show = false;
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to list task on marketplace.';
  } finally {
    listMarketplaceDialog.value.loading = false;
  }
}

async function cancelMarketplace(taskId: number) {
  const task = tasks.value.find(t => t.id === taskId);
  if (!task?.marketplace_listing_id) return;
  cancellingMarketplace.value = true;
  try {
    await marketplaceApi.cancel(task.marketplace_listing_id);
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to remove listing.';
  } finally {
    cancellingMarketplace.value = false;
  }
}

function formatDeadline(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function statusChipClass(status: string) {
  const map: Record<string, string> = {
    pending: 'cs-chip--pending',
    snoozed: 'cs-chip--snoozed',
    overdue: 'cs-chip--overdue',
    completed: 'cs-chip--done',
    suggested: 'cs-chip--pending',
  };
  return map[status] ?? 'cs-chip--snoozed';
}

onMounted(() => {
  loadTasks();
  loadIncomingSwaps();
  socketSvc.connect();
  socketSvc.onTaskUpdate((data: any) => {
    if (data.subtype === 'task_updated') {
      loadTasks();
      loadIncomingSwaps();
    }
  });
});

onUnmounted(() => {
  socketSvc.disconnect();
});
</script>

<style scoped>
.cs-tasks-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
.cs-tasks-list { max-height: calc(100vh - 240px); overflow-y: auto; }
.cs-task-detail { position: sticky; top: 20px; }

@media (max-width: 900px) {
  .cs-tasks-layout { grid-template-columns: 1fr; }
}
</style>
