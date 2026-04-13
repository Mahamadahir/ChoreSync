<template>
  <div class="cs-page">
    <div class="cs-page-header">
      <div class="cs-page-title">My Groups</div>
      <button class="cs-btn-primary" @click="showCreate = true">
        <span class="material-symbols-outlined">add</span>
        Create Group
      </button>
    </div>

    <div v-if="error" class="cs-error-msg" style="margin-bottom:16px">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px">
      <div v-for="i in 3" :key="i" class="cs-skeleton" style="height:140px;border-radius:var(--cs-radius-lg)" />
    </div>

    <!-- Empty -->
    <div v-else-if="groups.length === 0" class="cs-empty">
      <span class="material-symbols-outlined">group</span>
      <div class="cs-empty-title">No groups yet</div>
      <div class="cs-empty-sub">Create a group or ask someone to invite you with a join code.</div>
      <button class="cs-btn-primary" style="margin-top:8px" @click="showCreate = true">
        <span class="material-symbols-outlined">add</span>
        Create your first group
      </button>
    </div>

    <!-- Group cards -->
    <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px">
      <div
        v-for="g in groups"
        :key="g.id"
        class="cs-card cs-group-card"
        @click="$router.push({ name: 'group-detail', params: { id: g.id } })"
      >
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:8px">
          <div style="display:flex;align-items:center;gap:8px">
            <div style="font-size:17px;font-weight:700;color:var(--cs-on-surface)">{{ g.name }}</div>
            <span
              v-if="notifStore.groupBadge(g.id) > 0"
              style="min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:var(--cs-error,#b3261e);color:#fff;font-size:11px;font-weight:700;line-height:18px;text-align:center"
            >{{ notifStore.groupBadge(g.id) }}</span>
          </div>
          <span
            class="cs-chip"
            :style="g.role === 'moderator'
              ? 'background:var(--cs-primary-container);color:var(--cs-primary)'
              : 'background:var(--cs-surface-high);color:var(--cs-muted)'"
          >{{ g.role }}</span>
        </div>
        <div style="font-size:12px;color:var(--cs-muted);margin-bottom:12px">
          Code: <span style="font-family:monospace;font-weight:700;color:var(--cs-on-surface)">{{ g.group_code }}</span>
        </div>
        <!-- Stats row -->
        <div style="display:flex;gap:16px;margin-bottom:14px">
          <div>
            <div style="font-size:10px;font-weight:700;letter-spacing:.8px;color:var(--cs-muted)">MEMBERS</div>
            <div style="font-size:16px;font-weight:700;color:var(--cs-on-surface)">{{ g.member_count }}</div>
          </div>
          <div style="width:1px;background:var(--cs-outline-variant)"></div>
          <div>
            <div style="font-size:10px;font-weight:700;letter-spacing:.8px;color:var(--cs-muted)">OPEN TASKS</div>
            <div style="font-size:16px;font-weight:700;color:var(--cs-primary)">{{ g.open_task_count }}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <button
            class="cs-btn-outline"
            style="padding:6px 14px;font-size:12px;gap:4px"
            @click.stop="$router.push({ name: 'group-detail', params: { id: g.id } })"
          >
            Open
            <span class="material-symbols-outlined" style="font-size:16px">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Create group dialog -->
    <q-dialog v-model="showCreate" persistent>
      <q-card style="min-width:440px;max-width:520px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:18px;font-weight:700">Create a group</div>
          <div style="font-size:13px;color:var(--cs-muted);margin-top:4px">
            {{ createStep === 1 ? 'Give your group a name.' : 'Pick a preset — you can adjust these in settings later.' }}
          </div>
        </q-card-section>

        <!-- Step 1: name -->
        <q-card-section v-if="createStep === 1">
          <q-input
            v-model="form.name"
            label="Group name"
            outlined
            autofocus
            :error="!!formError"
            :error-message="formError"
            @keyup.enter="nextStep"
          />
        </q-card-section>

        <!-- Step 2: preset picker -->
        <q-card-section v-else style="display:flex;flex-direction:column;gap:10px">
          <div
            v-for="p in PRESETS"
            :key="p.id"
            @click="form.preset = p.id"
            :style="{
              border: form.preset === p.id ? '2px solid var(--cs-primary)' : '2px solid var(--cs-outline-variant)',
              borderRadius: '12px',
              padding: '14px 16px',
              cursor: 'pointer',
              background: form.preset === p.id ? 'var(--cs-primary-container)' : 'var(--cs-surface)',
              transition: 'all 0.15s',
            }"
          >
            <div style="display:flex;align-items:center;gap:10px">
              <span class="material-symbols-outlined" :style="{ color: form.preset === p.id ? 'var(--cs-primary)' : 'var(--cs-muted)', fontSize: '22px' }">
                {{ p.icon }}
              </span>
              <div>
                <div style="font-weight:700;font-size:15px">{{ p.label }}</div>
                <div style="font-size:12px;color:var(--cs-muted);margin-top:2px">{{ p.description }}</div>
              </div>
            </div>
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Cancel" @click="cancelCreate" />
          <q-btn v-if="createStep === 1" color="primary" label="Next" @click="nextStep" />
          <q-btn v-else flat label="Back" @click="createStep = 1" />
          <q-btn v-if="createStep === 2" color="primary" label="Create" :loading="creating" @click="createGroup" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { groupApi } from '../services/api';
import { useNotificationStore } from '../stores/notifications';

const notifStore = useNotificationStore();

type Group = {
  id: string;
  name: string;
  group_code: string;
  role: string;
  member_count: number;
  open_task_count: number;
};

type PresetId = 'flat_share' | 'family' | 'work_team';

const PRESETS: { id: PresetId; label: string; icon: string; description: string;
  reassignment_rule: string;
  task_proposal_voting_required: boolean; group_type: string }[] = [
  {
    id: 'flat_share',
    label: 'Flat Share',
    icon: 'apartment',
    description: 'Equal rotation — everyone can create tasks. New joiners become housemates automatically.',
    reassignment_rule: 'on_create',
    task_proposal_voting_required: false,
    group_type: 'flatshare',
  },
  {
    id: 'family',
    label: 'Family',
    icon: 'family_restroom',
    description: 'Parents approve tasks suggested by children. Invite as "Adult" or "Child".',
    reassignment_rule: 'on_create',
    task_proposal_voting_required: true,
    group_type: 'family',
  },
  {
    id: 'work_team',
    label: 'Work Team',
    icon: 'corporate_fare',
    description: 'Equal rotation. Invite members as "Team Lead" or "Member".',
    reassignment_rule: 'on_create',
    task_proposal_voting_required: false,
    group_type: 'work_team',
  },
];

const groups = ref<Group[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const showCreate = ref(false);
const creating = ref(false);
const formError = ref('');
const createStep = ref(1);
const form = ref({ name: '', preset: 'flat_share' as PresetId });

async function loadGroups() {
  loading.value = true;
  error.value = null;
  try {
    const res = await groupApi.list();
    groups.value = res.data;
  } catch {
    error.value = 'Failed to load groups.';
  } finally {
    loading.value = false;
  }
}

function nextStep() {
  if (!form.value.name.trim()) {
    formError.value = 'Group name is required.';
    return;
  }
  formError.value = '';
  createStep.value = 2;
}

function cancelCreate() {
  showCreate.value = false;
  createStep.value = 1;
  form.value = { name: '', preset: 'flat_share' };
  formError.value = '';
}

async function createGroup() {
  const preset = PRESETS.find((p) => p.id === form.value.preset)!;
  creating.value = true;
  try {
    await groupApi.create({
      name: form.value.name,
      reassignment_rule: preset.reassignment_rule,
      task_proposal_voting_required: preset.task_proposal_voting_required,
      group_type: preset.group_type,
    });
    cancelCreate();
    await loadGroups();
  } catch (e: any) {
    formError.value = e?.response?.data?.detail ?? 'Failed to create group.';
    createStep.value = 1;
  } finally {
    creating.value = false;
  }
}

onMounted(loadGroups);
</script>

<style scoped>
.cs-group-card {
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}
.cs-group-card:hover {
  box-shadow: var(--cs-shadow-md);
  transform: translateY(-2px);
}
</style>
