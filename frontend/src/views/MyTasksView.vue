<template>
  <q-page padding>
    <div class="text-h5 text-weight-bold q-mb-md">My Tasks</div>

    <!-- Filters -->
    <div class="row q-gutter-sm q-mb-md">
      <q-btn-toggle
        v-model="statusFilter"
        :options="filterOptions"
        unelevated
        rounded
        color="grey-3"
        text-color="grey-8"
        toggle-color="primary"
        @update:model-value="loadTasks"
      />
    </div>

    <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
      {{ error }}
    </q-banner>

    <div v-if="loading" class="row justify-center q-pa-xl">
      <q-spinner size="40px" color="primary" />
    </div>

    <div v-else-if="tasks.length === 0" class="text-center q-pa-xl text-grey-6">
      <q-icon name="task_alt" size="64px" />
      <div class="text-h6 q-mt-md">No tasks here</div>
      <div class="q-mt-sm">You're all caught up!</div>
    </div>

    <q-list v-else separator bordered class="rounded-borders">
      <q-item v-for="task in tasks" :key="task.id" class="q-py-md">
        <q-item-section>
          <q-item-label class="text-weight-medium">{{ task.template_name }}</q-item-label>
          <q-item-label caption>
            {{ task.group_name }} ·
            Due {{ formatDeadline(task.deadline) }}
          </q-item-label>
          <div class="row q-gutter-xs q-mt-xs">
            <q-badge :color="statusColor(task.status)" :label="task.status" />
            <q-badge v-if="task.points_earned" color="amber-7" :label="`${task.points_earned} pts`" />
            <q-badge v-if="task.snooze_count" color="grey-6" :label="`Snoozed ×${task.snooze_count}`" />
          </div>
        </q-item-section>

        <q-item-section side>
          <div class="row q-gutter-xs">
            <!-- Complete -->
            <q-btn
              v-if="task.status === 'pending' || task.status === 'snoozed'"
              round flat
              icon="check_circle"
              color="positive"
              size="sm"
              @click="completeTask(task.id)"
            >
              <q-tooltip>Mark complete</q-tooltip>
            </q-btn>

            <!-- Snooze -->
            <q-btn
              v-if="task.status === 'pending'"
              round flat
              icon="snooze"
              color="warning"
              size="sm"
              @click="openSnooze(task)"
            >
              <q-tooltip>Snooze</q-tooltip>
            </q-btn>

            <!-- Swap -->
            <q-btn
              v-if="task.status === 'pending' || task.status === 'snoozed'"
              round flat
              icon="swap_horiz"
              color="info"
              size="sm"
              @click="openSwap(task)"
            >
              <q-tooltip>Request swap</q-tooltip>
            </q-btn>

            <!-- Emergency reassign -->
            <q-btn
              v-if="task.status === 'pending'"
              round flat
              icon="emergency"
              color="negative"
              size="sm"
              @click="emergencyReassign(task.id)"
            >
              <q-tooltip>Emergency reassign</q-tooltip>
            </q-btn>

            <!-- List on Marketplace -->
            <q-btn
              v-if="(task.status === 'pending' || task.status === 'snoozed') && !task.on_marketplace"
              round flat
              icon="storefront"
              color="deep-purple"
              size="sm"
              @click="openListMarketplace(task)"
            >
              <q-tooltip>List on marketplace</q-tooltip>
            </q-btn>
            <q-badge v-if="task.on_marketplace" color="deep-purple" label="On marketplace" />
          </div>
        </q-item-section>
      </q-item>
    </q-list>

    <!-- Snooze dialog -->
    <q-dialog v-model="snoozeDialog.show">
      <q-card style="min-width: 320px">
        <q-card-section>
          <div class="text-h6">Snooze task</div>
          <div class="text-caption text-grey-6">{{ snoozeDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section>
          <q-input
            v-model="snoozeDialog.until"
            type="datetime-local"
            label="Snooze until"
            outlined
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="warning" label="Snooze" :loading="snoozeDialog.loading" @click="submitSnooze" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Swap dialog -->
    <q-dialog v-model="swapDialog.show">
      <q-card style="min-width: 340px">
        <q-card-section>
          <div class="text-h6">Request swap</div>
          <div class="text-caption text-grey-6">{{ swapDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input
            v-model="swapDialog.targetUserId"
            label="Target user ID (leave blank to broadcast)"
            outlined
          />
          <q-input v-model="swapDialog.reason" label="Reason (optional)" outlined />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="info" label="Request" :loading="swapDialog.loading" @click="submitSwap" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- List on Marketplace dialog -->
    <q-dialog v-model="listMarketplaceDialog.show">
      <q-card style="min-width: 340px">
        <q-card-section>
          <div class="text-h6">List on Marketplace</div>
          <div class="text-caption text-grey-6">{{ listMarketplaceDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
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
          <q-btn color="deep-purple" label="List task" :loading="listMarketplaceDialog.loading" @click="submitListMarketplace" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Incoming Swap Requests section -->
    <template v-if="incomingSwaps.length > 0">
      <div class="text-h6 text-weight-bold q-mt-xl q-mb-sm">Incoming Swap Requests</div>
      <q-list separator bordered class="rounded-borders">
        <q-item v-for="swap in incomingSwaps" :key="swap.id" class="q-py-md">
          <q-item-section>
            <q-item-label class="text-weight-medium">{{ swap.task_name ?? `Task #${swap.task_id}` }}</q-item-label>
            <q-item-label caption>
              {{ swap.group_name }} ·
              From {{ swap.from_username ?? swap.from_user_id }} ·
              <span :class="swap.swap_type === 'open_request' ? 'text-blue-6' : 'text-purple'">
                {{ swap.swap_type === 'open_request' ? 'Open request' : 'Direct to you' }}
              </span>
            </q-item-label>
            <div v-if="swap.reason" class="text-caption text-grey-6 q-mt-xs">{{ swap.reason }}</div>
          </q-item-section>
          <q-item-section side>
            <div class="row q-gutter-xs">
              <q-btn
                round flat icon="check" color="positive" size="sm"
                :loading="swapRespondLoading[swap.id] === 'accept'"
                @click="respondSwap(swap.id, true)">
                <q-tooltip>Accept swap</q-tooltip>
              </q-btn>
              <q-btn
                round flat icon="close" color="negative" size="sm"
                :loading="swapRespondLoading[swap.id] === 'reject'"
                @click="respondSwap(swap.id, false)">
                <q-tooltip>Decline swap</q-tooltip>
              </q-btn>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { taskApi, marketplaceApi } from '../services/api';

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
const loading = ref(false);
const error = ref<string | null>(null);
const statusFilter = ref('');

const filterOptions = [
  { label: 'All', value: '' },
  { label: 'Pending', value: 'pending' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Snoozed', value: 'snoozed' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Reassigned', value: 'reassigned' },
  { label: 'Completed', value: 'completed' },
];

const snoozeDialog = ref<{ show: boolean; task: Task | null; until: string; loading: boolean }>({
  show: false, task: null, until: '', loading: false,
});
const swapDialog = ref<{ show: boolean; task: Task | null; targetUserId: string; reason: string; loading: boolean }>({
  show: false, task: null, targetUserId: '', reason: '', loading: false,
});
const listMarketplaceDialog = ref<{ show: boolean; task: Task | null; bonusPoints: number; loading: boolean }>({
  show: false, task: null, bonusPoints: 0, loading: false,
});
const incomingSwaps = ref<IncomingSwap[]>([]);
const swapRespondLoading = ref<Record<number, 'accept' | 'reject' | null>>({});

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
  } catch {
    // Non-critical; ignore errors silently
  }
}

async function completeTask(id: number) {
  try {
    await taskApi.complete(id);
    await loadTasks();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to complete task.';
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

async function emergencyReassign(id: number) {
  try {
    await taskApi.emergencyReassign(id, {});
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

function formatDeadline(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'blue-6', in_progress: 'blue-8', snoozed: 'orange',
    overdue: 'negative', reassigned: 'purple', completed: 'positive',
  };
  return map[status] ?? 'grey';
}

onMounted(() => {
  loadTasks();
  loadIncomingSwaps();
});
</script>
