<template>
  <q-page padding>
    <!-- Header -->
    <div v-if="group" class="row items-center q-mb-md q-gutter-sm">
      <q-btn flat round icon="arrow_back" @click="$router.push({ name: 'groups' })" />
      <div>
        <div class="text-h5 text-weight-bold">{{ group.name }}</div>
        <div class="text-caption text-grey-6">Code: {{ group.group_code }}</div>
      </div>
      <q-space />
      <q-badge :color="group.role === 'moderator' ? 'primary' : 'grey-6'" :label="group.role" />
    </div>

    <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>{{ error }}</q-banner>

    <div v-if="loading" class="row justify-center q-pa-xl">
      <q-spinner size="40px" color="primary" />
    </div>

    <template v-else-if="group">
      <q-tabs v-model="tab" align="left" narrow-indicator dense class="q-mb-md">
        <q-tab name="tasks" icon="task" label="Tasks" />
        <q-tab name="members" icon="people" label="Members" />
        <q-tab name="leaderboard" icon="leaderboard" label="Leaderboard" />
        <q-tab v-if="group.task_proposal_voting_required" name="proposals" icon="how_to_vote" label="Proposals" />
        <q-tab name="marketplace" icon="storefront" label="Marketplace" />
        <q-tab name="chat" icon="chat" label="Chat" />
        <q-tab v-if="group.role === 'moderator'" name="settings" icon="settings" label="Settings" />
      </q-tabs>

      <q-tab-panels v-model="tab" animated>

        <!-- ── TASKS ── -->
        <q-tab-panel name="tasks">
          <div class="row justify-end q-mb-sm">
            <q-btn v-if="!group.task_proposal_voting_required" color="secondary" icon="add_task" label="New task" size="sm" @click="showTemplateForm = true" />
          </div>
          <!-- Hidden file input for photo proof uploads -->
          <input
            ref="proofInputRef"
            type="file"
            accept="image/*"
            style="display:none"
            @change="handleProofFile"
          />

          <div v-if="tasks.length === 0" class="text-center text-grey-6 q-pa-xl">
            <q-icon name="task_alt" size="48px" /><div class="q-mt-sm">No tasks yet.</div>
          </div>
          <q-list v-else separator bordered class="rounded-borders">
            <q-item v-for="t in tasks" :key="t.id" class="q-py-md">
              <q-item-section>
                <q-item-label class="text-weight-medium">{{ t.template_name }}</q-item-label>
                <q-item-label caption>Due {{ formatDate(t.deadline) }} · {{ t.assigned_to_username ?? 'Unassigned' }}</q-item-label>
                <q-badge :color="statusColor(t.status)" :label="t.status" class="q-mt-xs" style="width:fit-content" />
                <!-- Proof thumbnail for completed tasks -->
                <div v-if="t.photo_proof" class="q-mt-xs">
                  <a :href="t.photo_proof" target="_blank" rel="noopener">
                    <img :src="t.photo_proof" alt="Proof" style="max-height:60px;border-radius:6px;cursor:pointer;" />
                  </a>
                </div>
                <!-- Upload needed indicator -->
                <div v-else-if="t.photo_proof_required && (t.status === 'pending' || t.status === 'snoozed')" class="q-mt-xs text-caption text-orange">
                  <q-icon name="camera_alt" size="xs" /> Photo proof required before completing
                </div>
              </q-item-section>
              <q-item-section side>
                <div class="column items-center q-gutter-xs">
                  <!-- Upload proof button (only when proof required and not yet uploaded) -->
                  <q-btn
                    v-if="t.photo_proof_required && !t.photo_proof && (t.status === 'pending' || t.status === 'snoozed')"
                    round flat icon="camera_alt" color="orange" size="sm"
                    :loading="proofUploading[t.id]"
                    @click="triggerProofUpload(t.id)">
                    <q-tooltip>Upload photo proof</q-tooltip>
                  </q-btn>
                  <!-- Complete button — disabled when proof required but not yet uploaded -->
                  <q-btn
                    v-if="t.status === 'pending' || t.status === 'snoozed'"
                    round flat icon="check_circle" color="positive" size="sm"
                    :disable="t.photo_proof_required && !t.photo_proof"
                    @click="completeTask(t.id)">
                    <q-tooltip>{{ t.photo_proof_required && !t.photo_proof ? 'Upload photo proof first' : 'Complete' }}</q-tooltip>
                  </q-btn>
                  <!-- List on Marketplace (only for assigned user, pending/snoozed, not already listed) -->
                  <q-btn
                    v-if="(t.status === 'pending' || t.status === 'snoozed') && t.assigned_to_id === myUserId && !t.on_marketplace"
                    round flat icon="storefront" color="deep-purple" size="sm"
                    @click="openListMarketplace(t)">
                    <q-tooltip>List on marketplace</q-tooltip>
                  </q-btn>
                  <q-badge v-if="t.on_marketplace" color="deep-purple" label="On marketplace" class="q-mt-xs" />
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-tab-panel>

        <!-- ── MEMBERS ── -->
        <q-tab-panel name="members">
          <div class="row q-gutter-md">
            <q-card v-for="m in members" :key="m.user_id" flat bordered style="width:220px">
              <q-card-section>
                <div class="text-weight-medium">{{ m.username }}</div>
                <div class="text-caption text-grey-6">{{ m.email }}</div>
                <q-badge :color="m.role === 'moderator' ? 'primary' : 'grey-6'" :label="m.role" class="q-mt-xs" />
              </q-card-section>
              <q-card-section v-if="m.stats" class="q-pt-none text-caption">
                <div>✅ {{ m.stats.total_tasks_completed }} tasks</div>
                <div>⭐ {{ m.stats.total_points }} pts</div>
                <div>🔥 {{ m.stats.current_streak_days }}-day streak</div>
              </q-card-section>
            </q-card>
          </div>

          <!-- Invite member (moderator only) -->
          <div v-if="group.role === 'moderator'" class="q-mt-lg">
            <div class="text-subtitle2 q-mb-sm">Invite member</div>
            <div class="row q-gutter-sm items-end" style="max-width:500px">
              <q-input v-model="invite.email" label="Email" outlined dense style="flex:1" />
              <q-select v-model="invite.role" :options="['member','moderator']" label="Role" outlined dense style="width:130px" />
              <q-btn color="primary" label="Invite" :loading="invite.loading" @click="inviteMember" />
            </div>
            <div v-if="invite.message" class="q-mt-xs text-caption" :class="invite.error ? 'text-negative' : 'text-positive'">
              {{ invite.message }}
            </div>
          </div>

          <!-- Leave group -->
          <div class="q-mt-lg">
            <q-btn
              flat color="negative" icon="logout" label="Leave group"
              :loading="leaveLoading" @click="leaveGroup"
            />
            <div v-if="leaveError" class="q-mt-xs text-caption text-negative">{{ leaveError }}</div>
          </div>
        </q-tab-panel>

        <!-- ── LEADERBOARD ── -->
        <q-tab-panel name="leaderboard">
          <q-table
            :rows="leaderboard"
            :columns="leaderboardColumns"
            row-key="user_id"
            flat
            bordered
            hide-bottom
          />
          <q-card flat bordered class="q-pa-md q-mt-md" v-if="leaderboard.length > 0">
            <FairnessChart :distribution="leaderboard" />
          </q-card>
        </q-tab-panel>

        <!-- ── PROPOSALS ── -->
        <q-tab-panel name="proposals">
          <div class="row items-center justify-between q-mb-md">
            <div class="text-subtitle1">Proposals</div>
            <q-btn color="primary" icon="how_to_vote" label="New proposal" size="sm" @click="showProposalForm = true" />
          </div>

          <div v-if="proposals.length === 0" class="text-grey-6 text-center q-pa-xl">
            <q-icon name="how_to_vote" size="48px" /><div class="q-mt-sm">No proposals yet.</div>
          </div>

          <q-card v-for="p in proposals" :key="p.id" flat bordered class="q-mb-sm">
            <q-card-section>
              <div class="row items-center q-gutter-sm">
                <div class="text-weight-medium">{{ p.task_template_name ?? `Template #${p.task_template_id}` }}</div>
                <q-badge :color="proposalColor(p.state)" :label="p.state" />
              </div>
              <div class="text-caption text-grey-6">By {{ p.proposed_by }} · Deadline {{ formatDate(p.voting_deadline) }}</div>
              <div v-if="p.reason" class="text-body2 q-mt-xs">{{ p.reason }}</div>
              <div class="row q-gutter-sm q-mt-sm">
                <q-chip icon="thumb_up" color="positive" text-color="white" size="sm" :label="`${p.votes.support} support`" />
                <q-chip icon="thumb_down" color="negative" text-color="white" size="sm" :label="`${p.votes.reject} reject`" />
                <q-chip icon="remove" color="grey" text-color="white" size="sm" :label="`${p.votes.abstain} abstain`" />
              </div>
            </q-card-section>
            <q-card-actions v-if="p.state === 'pending'" align="right">
              <q-btn flat color="positive" label="Support" @click="castVote(p.id, 'support')" />
              <q-btn flat color="negative" label="Reject" @click="castVote(p.id, 'reject')" />
              <q-btn flat color="grey" label="Abstain" @click="castVote(p.id, 'abstain')" />
            </q-card-actions>
          </q-card>

          <!-- New proposal dialog -->
          <q-dialog v-model="showProposalForm">
            <q-card style="min-width:360px">
              <q-card-section><div class="text-h6">New proposal</div></q-card-section>
              <q-card-section class="q-gutter-sm">
                <q-select
                  v-model="proposalForm.task_template_id"
                  :options="templateOptions"
                  label="Task template"
                  outlined
                  emit-value
                  map-options
                />
                <q-input v-model="proposalForm.reason" label="Reason (optional)" outlined type="textarea" rows="2" />
              </q-card-section>
              <q-card-actions align="right">
                <q-btn flat label="Cancel" v-close-popup />
                <q-btn color="primary" label="Submit" :loading="proposalForm.loading" @click="submitProposal" />
              </q-card-actions>
            </q-card>
          </q-dialog>
        </q-tab-panel>

        <!-- ── MARKETPLACE ── -->
        <q-tab-panel name="marketplace">
          <div class="row items-center justify-between q-mb-md">
            <div class="text-subtitle1">Task Marketplace</div>
            <q-btn flat icon="refresh" size="sm" @click="loadMarketplace" />
          </div>

          <div v-if="marketplaceLoading" class="row justify-center q-pa-xl">
            <q-spinner size="32px" color="primary" />
          </div>

          <div v-else-if="marketplaceListings.length === 0" class="text-center text-grey-6 q-pa-xl">
            <q-icon name="storefront" size="48px" />
            <div class="q-mt-sm">No tasks listed on the marketplace.</div>
            <div class="text-caption q-mt-xs">List one of your pending tasks to let others pick it up!</div>
          </div>

          <q-card v-for="listing in marketplaceListings" :key="listing.id" flat bordered class="q-mb-sm">
            <q-card-section>
              <div class="row items-center q-gutter-sm">
                <div class="text-weight-medium">{{ listing.task_name }}</div>
                <q-badge v-if="listing.bonus_points > 0" color="amber-7" :label="`+${listing.bonus_points} pts bonus`" />
              </div>
              <div class="text-caption text-grey-6">
                Listed by {{ listing.listed_by_username }} ·
                Due {{ formatDate(listing.deadline) }} ·
                Expires {{ formatDate(listing.expires_at) }}
              </div>
            </q-card-section>
            <q-card-actions align="right">
              <q-btn
                v-if="listing.listed_by_id !== myUserId"
                color="deep-purple" label="Claim this task" size="sm"
                :loading="claimingListing[listing.id]"
                @click="claimListing(listing.id)"
              />
              <q-chip v-else color="grey-4" text-color="grey-8" size="sm" label="Your listing" />
            </q-card-actions>
          </q-card>
        </q-tab-panel>

        <!-- ── CHAT ── -->
        <q-tab-panel name="chat" class="q-pa-none">
          <div class="chat-container column">
            <div class="chat-messages col q-pa-md" ref="chatBox">
              <div v-for="(msg, i) in chatMessages" :key="i"
                :class="['chat-bubble q-mb-sm', msg.sender_id === myUserId ? 'self' : 'other']">
                <div class="text-caption text-grey-6">{{ msg.username }} · {{ formatDate(msg.sent_at) }}</div>
                <div class="bubble-text">{{ msg.body }}</div>
              </div>
              <div v-if="chatMessages.length === 0" class="text-center text-grey-6 q-mt-xl">
                No messages yet. Say hello!
              </div>
            </div>
            <div class="row q-pa-sm q-gutter-sm chat-input-row">
              <q-input
                v-model="chatInput"
                placeholder="Type a message…"
                outlined
                dense
                class="col"
                @keyup.enter="sendMessage"
              />
              <q-btn round color="primary" icon="send" @click="sendMessage" />
            </div>
          </div>
        </q-tab-panel>

        <!-- ── SETTINGS (moderator only) ── -->
        <q-tab-panel v-if="group.role === 'moderator'" name="settings">
          <div class="text-subtitle1 q-mb-md">Group Settings</div>
          <div class="column q-gutter-md" style="max-width:400px">
            <q-select
              v-model="settings.fairness_algorithm"
              :options="fairnessOptions"
              label="Fairness algorithm"
              outlined
              emit-value map-options
            />
            <q-toggle v-model="settings.photo_proof_required" label="Require photo proof on task completion" />
            <q-toggle v-model="settings.task_proposal_voting_required" label="Require voting on new task proposals" />
            <q-btn color="primary" label="Save settings" :loading="settings.loading" @click="saveSettings" />
            <div v-if="settings.message" class="text-caption" :class="settings.error ? 'text-negative' : 'text-positive'">
              {{ settings.message }}
            </div>
          </div>

          <q-separator class="q-my-lg" />
          <div class="row items-center justify-between q-mb-sm">
            <div class="text-subtitle1">Task Templates</div>
            <q-btn color="primary" icon="add" label="New template" size="sm" @click="showTemplateForm = true" />
          </div>
          <div v-if="templates.length === 0" class="text-caption text-grey-6">No templates yet.</div>
          <q-list v-else separator bordered class="rounded-borders" style="max-width:560px">
            <q-item v-for="tmpl in templates" :key="tmpl.id">
              <q-item-section>
                <q-item-label>{{ tmpl.name }}</q-item-label>
                <q-item-label caption>{{ tmpl.category }} · {{ tmpl.recurring_choice }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round icon="delete" color="negative" size="sm" @click="deleteTemplate(tmpl.id)" />
              </q-item-section>
            </q-item>
          </q-list>
        </q-tab-panel>

      </q-tab-panels>

      <!-- List on Marketplace dialog -->
      <q-dialog v-model="listMarketplaceDialog.show">
        <q-card style="min-width:340px">
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

      <!-- New task dialog (triggered from Proposals tab) -->
      <q-dialog v-model="showTemplateForm">
        <q-card style="min-width:400px">
          <q-card-section><div class="text-h6">New task</div></q-card-section>
          <q-card-section class="q-gutter-sm">
            <q-input v-model="templateForm.name" label="Name" outlined />
            <q-select
              v-model="templateForm.category"
              :options="categoryOptions"
              label="Category"
              outlined emit-value map-options
            />
            <q-select
              v-model="templateForm.recurring_choice"
              :options="recurrenceOptions"
              label="Recurrence"
              outlined emit-value map-options
            />
            <q-select
              v-model="templateForm.importance"
              :options="importanceOptions"
              label="Importance"
              outlined emit-value map-options
            />
            <q-input v-model.number="templateForm.difficulty" type="number" label="Difficulty (1-5)" outlined min="1" max="5" />
            <q-input
              v-model="templateForm.due_datetime"
              type="datetime-local"
              :label="templateForm.recurring_choice === 'none' ? 'Due date & time' : 'First due date & time'"
              outlined
            />
            <q-input
              v-if="templateForm.recurring_choice === 'every_n_days'"
              v-model.number="templateForm.recur_value"
              type="number" label="Repeat every N days" outlined min="1"
            />
            <q-select
              v-if="templateForm.recurring_choice === 'custom'"
              v-model="templateForm.days_of_week"
              :options="[
                { label: 'Mon', value: 'mon' }, { label: 'Tue', value: 'tue' },
                { label: 'Wed', value: 'wed' }, { label: 'Thu', value: 'thu' },
                { label: 'Fri', value: 'fri' }, { label: 'Sat', value: 'sat' },
                { label: 'Sun', value: 'sun' },
              ]"
              label="Days of week" outlined multiple emit-value map-options
            />
            <q-toggle v-model="templateForm.photo_proof_required" label="Photo proof required" />
          </q-card-section>
          <q-card-actions align="right">
            <q-btn flat label="Cancel" v-close-popup />
            <q-btn color="primary" label="Create" :loading="templateForm.loading" @click="submitTemplate" />
          </q-card-actions>
        </q-card>
      </q-dialog>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { groupApi, taskApi, marketplaceApi, api } from '../services/api';
import { useAuthStore } from '../stores/auth';
import { NotificationSocketService } from '../services/NotificationSocketService';
import FairnessChart from '../components/charts/FairnessChart.vue';

const route = useRoute();
const router = useRouter();
const groupId = route.params.id as string;
const authStore = useAuthStore();
const myUserId = computed(() => authStore.userId);

const tab = ref('tasks');
const group = ref<any>(null);
const members = ref<any[]>([]);
const tasks = ref<any[]>([]);
const leaderboard = ref<any[]>([]);
const proposals = ref<any[]>([]);
const templates = ref<any[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Chat
const chatMessages = ref<any[]>([]);
const chatInput = ref('');
const chatBox = ref<HTMLElement | null>(null);
const socketSvc = new NotificationSocketService();

// Invite
const invite = ref({ email: '', role: 'member', loading: false, message: '', error: false });

// Leave group
const leaveLoading = ref(false);
const leaveError = ref('');

// Marketplace
const marketplaceListings = ref<any[]>([]);
const marketplaceLoading = ref(false);
const claimingListing = ref<Record<number, boolean>>({});
const listMarketplaceDialog = ref<{ show: boolean; task: any | null; bonusPoints: number; loading: boolean }>({
  show: false, task: null, bonusPoints: 0, loading: false,
});

// Photo proof
const proofInputRef = ref<HTMLInputElement | null>(null);
const proofUploading = ref<Record<number, boolean>>({});
let proofTargetTaskId: number | null = null;

function triggerProofUpload(taskId: number) {
  proofTargetTaskId = taskId;
  proofInputRef.value?.click();
}

async function handleProofFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || proofTargetTaskId === null) return;
  const taskId = proofTargetTaskId;
  proofTargetTaskId = null;
  input.value = '';

  proofUploading.value[taskId] = true;
  try {
    const form = new FormData();
    form.append('photo', file);
    const res = await api.post(`/api/tasks/${taskId}/upload-proof/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    // Update local task with returned photo_url so Complete button enables immediately
    const idx = tasks.value.findIndex(t => t.id === taskId);
    if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], photo_proof: res.data.photo_url };
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to upload photo proof.';
  } finally {
    proofUploading.value[taskId] = false;
  }
}

// Proposal form
const showProposalForm = ref(false);
const proposalForm = ref({ task_template_id: null as number | null, reason: '', loading: false });

// Template form
const showTemplateForm = ref(false);
const templateForm = ref({
  name: '', category: 'cleaning', recurring_choice: 'none', importance: 'core',
  difficulty: 3, due_datetime: '', photo_proof_required: false,
  recur_value: 7, days_of_week: [] as string[], loading: false,
});

// Settings
const settings = ref({
  fairness_algorithm: '', photo_proof_required: false,
  task_proposal_voting_required: false, loading: false, message: '', error: false,
});

const leaderboardColumns = [
  { name: 'rank', label: '#', field: 'rank', align: 'center' as const },
  { name: 'username', label: 'Member', field: 'username', align: 'left' as const },
  { name: 'total_points', label: 'Points', field: 'total_points', align: 'right' as const, sortable: true },
  { name: 'total_tasks_completed', label: 'Tasks', field: 'total_tasks_completed', align: 'right' as const },
  { name: 'current_streak_days', label: 'Streak', field: 'current_streak_days', align: 'right' as const },
  { name: 'on_time_completion_rate', label: 'On-time %', field: (r: any) => `${Math.round(r.on_time_completion_rate * 100)}%`, align: 'right' as const },
];

const fairnessOptions = [
  { label: 'Count-based (least tasks done)', value: 'count_based' },
  { label: 'Time-based (longest waiting)', value: 'time_based' },
  { label: 'Difficulty-based (preferences & difficulty)', value: 'difficulty_based' },
  { label: 'Weighted (tasks 60% + points 40%)', value: 'weighted' },
];

const recurrenceOptions = [
  { label: 'No repeat', value: 'none' },
  { label: 'Weekly', value: 'weekly' },
  { label: 'Monthly', value: 'monthly' },
  { label: 'Every N days', value: 'every_n_days' },
  { label: 'Custom (days of week)', value: 'custom' },
];

const categoryOptions = [
  { label: 'Cleaning', value: 'cleaning' },
  { label: 'Cooking', value: 'cooking' },
  { label: 'Laundry', value: 'laundry' },
  { label: 'Maintenance', value: 'maintenance' },
  { label: 'Other', value: 'other' },
];

const importanceOptions = [
  { label: 'Core', value: 'core' },
  { label: 'Additional', value: 'additional' },
];

const templateOptions = computed(() =>
  templates.value.map(t => ({ label: t.name, value: t.id }))
);

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    const [gRes, mRes, tRes] = await Promise.all([
      groupApi.get(groupId),
      groupApi.members(groupId),
      taskApi.groupTasks(groupId),
    ]);
    group.value = gRes.data;
    members.value = mRes.data;
    tasks.value = tRes.data;
    settings.value.fairness_algorithm = gRes.data.fairness_algorithm;
    settings.value.photo_proof_required = gRes.data.photo_proof_required;
    settings.value.task_proposal_voting_required = gRes.data.task_proposal_voting_required;
    // Load rest in background
    loadLeaderboard();
    loadProposals();
    loadTemplates();
    loadMarketplace();
  } catch {
    error.value = 'Failed to load group.';
  } finally {
    loading.value = false;
  }
}

async function loadLeaderboard() {
  try { leaderboard.value = (await groupApi.leaderboard(groupId)).data; } catch {}
}
async function loadProposals() {
  try { proposals.value = (await groupApi.proposals(groupId)).data; } catch {}
}
async function loadTemplates() {
  try {
    const { api } = await import('../services/api');
    const res = await api.get(`/api/groups/${groupId}/task-templates/`);
    templates.value = res.data;
  } catch {}
}

async function deleteTemplate(templateId: number) {
  try {
    const { api } = await import('../services/api');
    await api.delete(`/api/task-templates/${templateId}/`);
    await loadTemplates();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to delete template.';
  }
}

async function loadMarketplace() {
  marketplaceLoading.value = true;
  try {
    marketplaceListings.value = (await marketplaceApi.groupListings(groupId)).data;
  } catch {}
  finally {
    marketplaceLoading.value = false;
  }
}

async function claimListing(listingId: number) {
  claimingListing.value[listingId] = true;
  try {
    await marketplaceApi.claim(listingId);
    await Promise.all([loadMarketplace(), taskApi.groupTasks(groupId).then(r => { tasks.value = r.data; })]);
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to claim task.';
  } finally {
    claimingListing.value[listingId] = false;
  }
}

function openListMarketplace(task: any) {
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
    // Refresh tasks to update on_marketplace flag and reload marketplace listings
    tasks.value = (await taskApi.groupTasks(groupId)).data;
    await loadMarketplace();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to list task on marketplace.';
  } finally {
    listMarketplaceDialog.value.loading = false;
  }
}

async function completeTask(id: number) {
  try {
    await taskApi.complete(id);
    tasks.value = (await taskApi.groupTasks(groupId)).data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to complete task.';
  }
}

async function inviteMember() {
  invite.value.loading = true;
  invite.value.message = '';
  try {
    await groupApi.invite(groupId, { email: invite.value.email, role: invite.value.role });
    invite.value.message = 'Invitation sent.';
    invite.value.error = false;
    invite.value.email = '';
  } catch (e: any) {
    invite.value.message = e?.response?.data?.detail ?? 'Failed to invite.';
    invite.value.error = true;
  } finally {
    invite.value.loading = false;
  }
}

async function castVote(proposalId: number, choice: string) {
  try {
    const res = await (await import('../services/api')).api.post(`/api/proposals/${proposalId}/vote/`, { choice });
    const idx = proposals.value.findIndex(p => p.id === proposalId);
    if (idx !== -1) proposals.value[idx] = res.data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to cast vote.';
  }
}

async function submitProposal() {
  if (!proposalForm.value.task_template_id) return;
  proposalForm.value.loading = true;
  try {
    await groupApi.createProposal(groupId, {
      task_template_id: proposalForm.value.task_template_id,
      reason: proposalForm.value.reason,
    });
    showProposalForm.value = false;
    proposalForm.value = { task_template_id: null, reason: '', loading: false };
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to submit proposal.';
  } finally {
    proposalForm.value.loading = false;
  }
}

async function submitTemplate() {
  if (!templateForm.value.due_datetime) {
    error.value = 'Please select a due date and time.';
    return;
  }
  templateForm.value.loading = true;
  try {
    const { api } = await import('../services/api');
    const { loading: _loading, due_datetime, ...rest } = templateForm.value;
    // Convert local datetime-local value to ISO 8601 with UTC offset
    const next_due = new Date(due_datetime).toISOString();
    const payload = { ...rest, next_due };
    const res = await api.post(`/api/groups/${groupId}/task-templates/`, payload);
    showTemplateForm.value = false;
    templateForm.value = { name: '', category: 'cleaning', recurring_choice: 'none', importance: 'core', difficulty: 3, due_datetime: '', photo_proof_required: false, recur_value: 7, days_of_week: [], loading: false };
    const created = res.data.occurrences_created ?? 0;
    if (created > 0) {
      tasks.value = (await (await import('../services/api')).taskApi.groupTasks(groupId)).data;
    }
    await loadTemplates();
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to create task.';
  } finally {
    templateForm.value.loading = false;
  }
}

async function saveSettings() {
  settings.value.loading = true;
  settings.value.message = '';
  try {
    await groupApi.settings(groupId, {
      fairness_algorithm: settings.value.fairness_algorithm,
      photo_proof_required: settings.value.photo_proof_required,
      task_proposal_voting_required: settings.value.task_proposal_voting_required,
    });
    settings.value.message = 'Settings saved.';
    settings.value.error = false;
  } catch (e: any) {
    settings.value.message = e?.response?.data?.detail ?? 'Failed to save.';
    settings.value.error = true;
  } finally {
    settings.value.loading = false;
  }
}

async function leaveGroup() {
  if (!window.confirm('Are you sure you want to leave this group?')) return;
  leaveLoading.value = true;
  leaveError.value = '';
  try {
    const { api } = await import('../services/api');
    await api.post(`/api/groups/${groupId}/leave/`);
    router.push({ name: 'groups' });
  } catch (e: any) {
    leaveError.value = e?.response?.data?.detail ?? 'Failed to leave group.';
  } finally {
    leaveLoading.value = false;
  }
}

function sendMessage() {
  const body = chatInput.value.trim();
  if (!body) return;
  socketSvc.sendChatMessage(groupId, body);
  chatInput.value = '';
}

function formatDate(iso: string) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function statusColor(s: string) {
  return { pending: 'blue-6', snoozed: 'orange', overdue: 'negative', completed: 'positive' }[s] ?? 'grey';
}
function proposalColor(s: string) {
  return { pending: 'blue-6', approved: 'positive', rejected: 'negative', expired: 'grey' }[s] ?? 'grey';
}

onMounted(() => {
  loadAll();
  socketSvc.onChat((msg) => {
    if (msg.group_id === groupId) {
      chatMessages.value.push(msg);
      nextTick(() => {
        if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight;
      });
    }
  });
  socketSvc.connect();
});

onUnmounted(() => socketSvc.disconnect());
</script>

<style scoped>
.chat-container {
  height: calc(100vh - 280px);
  min-height: 300px;
}
.chat-messages {
  overflow-y: auto;
  flex: 1;
}
.chat-input-row {
  border-top: 1px solid #e0e0e0;
}
.chat-bubble { max-width: 70%; }
.chat-bubble.self { margin-left: auto; }
.chat-bubble.other { margin-right: auto; }
.bubble-text {
  background: #f0f0f0;
  border-radius: 12px;
  padding: 8px 12px;
  display: inline-block;
}
.chat-bubble.self .bubble-text {
  background: #1976D2;
  color: white;
}
</style>
