<template>
  <div class="cs-page" style="max-width:900px">
    <div class="cs-page-title">Profile & Settings</div>

    <!-- Avatar -->
    <div class="cs-card" style="margin-bottom:20px;display:flex;align-items:center;gap:24px">
      <div style="position:relative;flex-shrink:0">
        <div
          style="width:96px;height:96px;border-radius:50%;overflow:hidden;
                 background:var(--cs-surface-container-high);
                 display:flex;align-items:center;justify-content:center;
                 border:3px solid var(--cs-surface-container-highest)"
        >
          <img
            v-if="profileAvatarUrl"
            :src="profileAvatarUrl"
            alt="Avatar"
            style="width:100%;height:100%;object-fit:cover"
          />
          <span
            v-else
            style="font-size:32px;font-weight:700;color:var(--cs-primary);letter-spacing:1px"
          >{{ authStore.initials }}</span>
        </div>
        <label
          style="position:absolute;bottom:0;right:0;width:28px;height:28px;border-radius:50%;
                 background:var(--cs-primary);display:flex;align-items:center;justify-content:center;
                 cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,0.2)"
          title="Upload photo"
        >
          <span v-if="uploadingAvatar" class="material-symbols-outlined" style="font-size:14px;color:#fff;animation:spin 1s linear infinite">progress_activity</span>
          <span v-else class="material-symbols-outlined" style="font-size:14px;color:#fff">edit</span>
          <input type="file" accept="image/*" style="display:none" @change="uploadAvatar" :disabled="uploadingAvatar" />
        </label>
      </div>
      <div>
        <div style="font-size:18px;font-weight:700;color:var(--cs-on-surface)">{{ authStore.fullName || authStore.username }}</div>
        <div style="font-size:13px;color:var(--cs-muted);margin-top:2px">{{ authStore.email }}</div>
        <div v-if="avatarUploadMsg" style="font-size:12px;color:var(--cs-secondary);margin-top:6px">{{ avatarUploadMsg }}</div>
        <div v-if="avatarUploadError" style="font-size:12px;color:var(--cs-error);margin-top:6px">{{ avatarUploadError }}</div>
      </div>
    </div>

    <!-- Profile form -->
    <div class="cs-card" style="margin-bottom:20px">
      <div class="cs-card-title">Account details</div>
      <div class="cs-card-sub">Update your name, username, email or timezone</div>

      <form @submit.prevent="handleSave">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
          <div class="cs-form-field" style="margin:0">
            <label class="cs-form-label">First Name</label>
            <input v-model="firstName" class="cs-form-input" type="text" />
          </div>
          <div class="cs-form-field" style="margin:0">
            <label class="cs-form-label">Last Name</label>
            <input v-model="lastName" class="cs-form-input" type="text" />
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
          <div class="cs-form-field" style="margin:0">
            <label class="cs-form-label">Username</label>
            <input v-model="username" class="cs-form-input" type="text" />
          </div>
          <div class="cs-form-field" style="margin:0">
            <label class="cs-form-label">Email</label>
            <input v-model="email" class="cs-form-input" type="email" />
          </div>
        </div>
        <div class="cs-form-field">
          <label class="cs-form-label">Timezone</label>
          <q-select
            v-model="timezone"
            :options="filteredTimezones"
            option-label="label"
            option-value="value"
            outlined
            dense
            clearable
            use-input
            fill-input
            input-debounce="0"
            @filter="filterTimezones"
            emit-value
            map-options
          />
        </div>

        <div style="border-top:1px solid var(--cs-outline-variant);padding-top:16px;margin-bottom:16px">
          <div style="font-size:14px;font-weight:700;margin-bottom:12px">Change Password</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div class="cs-form-field" style="margin:0">
              <label class="cs-form-label">New Password</label>
              <div class="cs-input-wrap">
                <input
                  v-model="newPassword"
                  :type="showNewPassword ? 'text' : 'password'"
                  class="cs-form-input"
                  autocomplete="new-password"
                  @input="computeStrength"
                />
                <button type="button" class="cs-input-icon-btn" @click="showNewPassword = !showNewPassword">
                  <span class="material-symbols-outlined" style="font-size:18px">{{ showNewPassword ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
              <div class="cs-strength-bar">
                <div class="cs-strength-fill" :style="`width:${strengthValue * 100}%;background:${strengthColorHex}`" />
              </div>
              <div class="cs-strength-label">{{ strengthLabel }}</div>
            </div>
            <div class="cs-form-field" style="margin:0">
              <label class="cs-form-label">Confirm Password</label>
              <div class="cs-input-wrap">
                <input
                  v-model="confirmPassword"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  class="cs-form-input"
                  autocomplete="new-password"
                />
                <button type="button" class="cs-input-icon-btn" @click="showConfirmPassword = !showConfirmPassword">
                  <span class="material-symbols-outlined" style="font-size:18px">{{ showConfirmPassword ? 'visibility_off' : 'visibility' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <button type="submit" class="cs-btn-primary" style="padding:12px 28px" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
      </form>

      <div v-if="message" style="margin-top:12px;padding:10px 14px;background:var(--cs-secondary-container);color:var(--cs-secondary);border-radius:var(--cs-radius-sm);font-size:13px">
        {{ message }}
      </div>
      <div v-if="error" class="cs-error-msg" style="margin-top:12px">{{ error }}</div>
    </div>

    <!-- Stats -->
    <div class="cs-card" style="margin-bottom:20px">
      <div class="cs-card-title">Your Stats</div>
      <div v-if="statsLoading" style="height:80px;display:flex;align-items:center;justify-content:center">
        <q-spinner color="primary" size="32px" />
      </div>
      <div v-else-if="stats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        <div class="cs-stat-card">
          <div class="cs-stat-value">{{ stats.total_tasks_completed }}</div>
          <div class="cs-stat-label">Tasks done</div>
        </div>
        <div class="cs-stat-card">
          <div class="cs-stat-value" style="color:var(--cs-tertiary)">{{ stats.total_points }}</div>
          <div class="cs-stat-label">Points</div>
        </div>
        <div class="cs-stat-card">
          <div class="cs-stat-value" style="color:var(--cs-secondary)">{{ stats.current_streak_days }}</div>
          <div class="cs-stat-label">Day streak</div>
        </div>
        <div class="cs-stat-card">
          <div class="cs-stat-value">{{ Math.round((stats.on_time_completion_rate ?? 0) * 100) }}%</div>
          <div class="cs-stat-label">On-time rate</div>
        </div>
      </div>
      <div v-else style="font-size:13px;color:var(--cs-muted)">No stats yet — complete some tasks first.</div>
    </div>

    <!-- Charts -->
    <div v-if="statsRaw.length > 0" class="cs-card" style="margin-bottom:20px">
      <div class="cs-card-title">Progress Charts</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px">
        <div class="cs-card" style="background:var(--cs-surface)">
          <TasksOverTimeChart :data="weeklyCompletions" />
        </div>
        <div class="cs-card" style="background:var(--cs-surface)">
          <CategoryBreakdownChart :data="categoryBreakdown" />
        </div>
      </div>
    </div>

    <!-- Badges -->
    <div class="cs-card" style="margin-bottom:20px">
      <div class="cs-card-title">Badges</div>
      <div v-if="badges.length === 0" style="font-size:13px;color:var(--cs-muted);margin-top:8px">No badges earned yet.</div>
      <div v-else style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
        <div
          v-for="b in badges"
          :key="b.badge_id"
          class="cs-chip"
          style="background:var(--cs-tertiary-container);color:var(--cs-tertiary);gap:4px;font-size:12px;cursor:pointer"
          @click="openBadge(b)"
        >
          <span v-if="b.emoji" style="font-size:14px">{{ b.emoji }}</span>
          <span v-else class="material-symbols-outlined" style="font-size:14px;font-variation-settings:'FILL' 1">emoji_events</span>
          {{ b.name }}
        </div>
      </div>
    </div>

    <!-- Badge detail dialog -->
    <q-dialog v-model="badgeDialogOpen">
      <q-card style="min-width:320px;max-width:400px;padding:24px;border-radius:16px">
        <div style="text-align:center;margin-bottom:16px">
          <div v-if="selectedBadge?.emoji" style="font-size:52px;line-height:1.1;margin-bottom:8px">{{ selectedBadge.emoji }}</div>
          <span v-else class="material-symbols-outlined" style="font-size:52px;color:var(--cs-tertiary);font-variation-settings:'FILL' 1">emoji_events</span>
          <div style="font-size:18px;font-weight:700;margin-top:8px">{{ selectedBadge?.name }}</div>
          <div
            style="display:inline-block;background:var(--cs-tertiary-container);color:var(--cs-tertiary);
                   padding:2px 12px;border-radius:12px;font-size:12px;font-weight:600;margin-top:8px"
          >
            +{{ selectedBadge?.points_value }} pts
          </div>
        </div>
        <div style="font-size:14px;color:var(--cs-muted);text-align:center;margin-bottom:20px;line-height:1.5">
          {{ selectedBadge?.description }}
        </div>
        <div style="font-size:12px;color:var(--cs-outline);text-align:center;margin-bottom:20px">
          Earned {{ selectedBadge ? formatDateTime(selectedBadge.awarded_at) : '' }}
          <span v-if="selectedBadge?.household_name" style="display:block;margin-top:2px">
            in {{ selectedBadge.household_name }}
          </span>
        </div>
        <div style="display:flex;justify-content:center">
          <button class="cs-btn cs-btn-secondary" @click="badgeDialogOpen = false">Close</button>
        </div>
      </q-card>
    </q-dialog>

    <!-- Notification preferences -->
    <div class="cs-card" style="margin-bottom:20px">
      <div class="cs-card-title">Notification Settings</div>
      <div class="cs-card-sub">Choose which notifications you receive</div>

      <div v-if="prefsLoading" style="height:60px;display:flex;align-items:center;justify-content:center">
        <q-spinner color="primary" size="28px" />
      </div>
      <template v-else-if="prefs">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin-bottom:16px">
          <q-toggle v-model="prefs.deadline_reminders"   label="Deadline reminders"     @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.task_assigned"        label="Task assigned to me"    @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.task_swap"            label="Swap requests"          @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.emergency_reassign"   label="Emergency reassignments" @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.badge_earned"         label="Badge earned"           @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.marketplace_activity" label="Marketplace activity"   @update:model-value="savePrefs" />
          <q-toggle v-model="prefs.smart_suggestions"    label="Smart suggestions"      @update:model-value="savePrefs" />
        </div>

        <div style="border-top:1px solid var(--cs-outline-variant);padding-top:14px">
          <div style="font-size:14px;font-weight:700;margin-bottom:8px">Quiet Hours</div>
          <q-toggle v-model="prefs.quiet_hours_enabled" label="Suppress notifications during quiet window" @update:model-value="savePrefs" />
          <div v-if="prefs.quiet_hours_enabled" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;max-width:360px">
            <q-input v-model="prefs.quiet_start" label="Start (HH:MM)" outlined dense mask="##:##" hint="e.g. 22:00" @blur="savePrefs" />
            <q-input v-model="prefs.quiet_end"   label="End (HH:MM)"   outlined dense mask="##:##" hint="e.g. 08:00" @blur="savePrefs" />
          </div>
        </div>
        <div v-if="prefsSaveMsg" style="font-size:12px;color:var(--cs-secondary);margin-top:8px">{{ prefsSaveMsg }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { authService } from '../services/authService';
import { statsApi, notificationApi, api } from '../services/api';
import { useAuthStore } from '../stores/auth';
import { evaluatePassword } from '../utils/passwordStrength';
import TasksOverTimeChart from '../components/charts/TasksOverTimeChart.vue';
import CategoryBreakdownChart from '../components/charts/CategoryBreakdownChart.vue';

const authStore = useAuthStore();
const profileAvatarUrl = ref<string | null>(authStore.avatarUrl);
const uploadingAvatar = ref(false);
const avatarUploadMsg = ref('');
const avatarUploadError = ref('');

async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploadingAvatar.value = true;
  avatarUploadMsg.value = '';
  avatarUploadError.value = '';
  try {
    const form = new FormData();
    form.append('avatar', file);
    const res = await api.post('/api/users/me/avatar/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    profileAvatarUrl.value = res.data.avatar_url;
    authStore.setAvatarUrl(res.data.avatar_url);
    avatarUploadMsg.value = 'Photo updated.';
    setTimeout(() => { avatarUploadMsg.value = ''; }, 3000);
  } catch {
    avatarUploadError.value = 'Upload failed. Please try again.';
    setTimeout(() => { avatarUploadError.value = ''; }, 4000);
  } finally {
    uploadingAvatar.value = false;
    (event.target as HTMLInputElement).value = '';
  }
}

const firstName = ref('');
const lastName = ref('');
const username = ref('');
const email = ref('');
const timezone = ref('');
const saving = ref(false);
const message = ref('');
const error = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
type TzOption = { label: string; value: string };
const timezoneOptions = ref<TzOption[]>([]);
const filteredTimezones = ref<TzOption[]>([]);
const strengthValue = ref(0);
const strengthLabel = ref('Password strength');
const strengthColorHex = ref('#d5c6c0');
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);
const stats = ref<any>(null);
const statsLoading = ref(false);
const statsRaw = ref<any[]>([]);
const badges = ref<any[]>([]);
const badgesLoading = ref(false);
const badgeDialogOpen = ref(false);
const selectedBadge = ref<any>(null);

const weeklyCompletions = computed<{ week: string; count: number }[]>(() => {
  const map = new Map<string, number>();
  for (const s of statsRaw.value) {
    for (const wc of (s.weekly_completions || [])) {
      map.set(wc.week, (map.get(wc.week) || 0) + wc.count);
    }
  }
  return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0])).map(([week, count]) => ({ week, count }));
});

const categoryBreakdown = computed<{ category: string; count: number }[]>(() => {
  const map = new Map<string, number>();
  for (const s of statsRaw.value) {
    for (const cb of (s.category_breakdown || [])) {
      map.set(cb.category, (map.get(cb.category) || 0) + cb.count);
    }
  }
  return Array.from(map.entries()).sort((a, b) => b[1] - a[1]).map(([category, count]) => ({ category, count }));
});

async function loadStats() {
  statsLoading.value = true;
  try {
    const res = await statsApi.myStats();
    const data = res.data;
    if (Array.isArray(data) && data.length > 0) {
      statsRaw.value = data;
      stats.value = data.reduce((acc: any, s: any) => ({
        total_tasks_completed: (acc.total_tasks_completed || 0) + (s.total_tasks_completed || 0),
        total_points: (acc.total_points || 0) + (s.total_points || 0),
        current_streak_days: Math.max(acc.current_streak_days || 0, s.current_streak_days || 0),
        on_time_completion_rate: ((acc.on_time_completion_rate || 0) + (s.on_time_completion_rate || 0)) / 2,
      }), {});
    } else if (data && !Array.isArray(data)) {
      stats.value = data;
    }
  } catch {} finally {
    statsLoading.value = false;
  }
}

async function loadBadges() {
  badgesLoading.value = true;
  try {
    const res = await statsApi.myBadges();
    badges.value = res.data;
  } catch {} finally {
    badgesLoading.value = false;
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function openBadge(b: any) {
  selectedBadge.value = b;
  badgeDialogOpen.value = true;
}

function loadTimezones() {
  const offsets: TzOption[] = [
    { value: 'UTC-12', label: 'UTC-12 — Baker Island' },
    { value: 'UTC-11', label: 'UTC-11 — Midway' },
    { value: 'UTC-10', label: 'UTC-10 — Hawaii' },
    { value: 'UTC-09', label: 'UTC-9 — Alaska' },
    { value: 'UTC-08', label: 'UTC-8 — Pacific (Los Angeles)' },
    { value: 'UTC-07', label: 'UTC-7 — Mountain (Denver)' },
    { value: 'UTC-06', label: 'UTC-6 — Central (Chicago)' },
    { value: 'UTC-05', label: 'UTC-5 — Eastern (New York)' },
    { value: 'UTC-04', label: 'UTC-4 — Atlantic (Caribbean)' },
    { value: 'UTC-03', label: 'UTC-3 — Buenos Aires' },
    { value: 'UTC-02', label: 'UTC-2 — South Georgia' },
    { value: 'UTC-01', label: 'UTC-1 — Azores' },
    { value: 'UTC+00', label: 'UTC+0 — London' },
    { value: 'UTC+01', label: 'UTC+1 — Berlin/Paris/Rome' },
    { value: 'UTC+02', label: 'UTC+2 — Athens/Cairo/Johannesburg' },
    { value: 'UTC+03', label: 'UTC+3 — Moscow/Nairobi/Riyadh' },
    { value: 'UTC+04', label: 'UTC+4 — Dubai' },
    { value: 'UTC+05', label: 'UTC+5 — Karachi/Tashkent' },
    { value: 'UTC+05:30', label: 'UTC+5:30 — India (Kolkata)' },
    { value: 'UTC+06', label: 'UTC+6 — Dhaka' },
    { value: 'UTC+07', label: 'UTC+7 — Bangkok/Jakarta' },
    { value: 'UTC+08', label: 'UTC+8 — Beijing/Singapore/Perth' },
    { value: 'UTC+09', label: 'UTC+9 — Tokyo/Seoul' },
    { value: 'UTC+09:30', label: 'UTC+9:30 — Adelaide' },
    { value: 'UTC+10', label: 'UTC+10 — Sydney/Brisbane' },
    { value: 'UTC+11', label: 'UTC+11 — Magadan/Solomon Is.' },
    { value: 'UTC+12', label: 'UTC+12 — Auckland/Fiji' },
    { value: 'UTC+13', label: 'UTC+13 — Tonga' },
    { value: 'UTC+14', label: 'UTC+14 — Kiritimati' },
  ];
  timezoneOptions.value = offsets;
  filteredTimezones.value = offsets;
}

function filterTimezones(val: string, update: (cb: () => void) => void) {
  update(() => {
    if (!val) { filteredTimezones.value = timezoneOptions.value; return; }
    const needle = val.toLowerCase();
    filteredTimezones.value = timezoneOptions.value.filter(z => z.label.toLowerCase().includes(needle));
  });
}

async function loadProfile() {
  try {
    const resp = await authService.getProfile();
    firstName.value = resp.data.first_name || '';
    lastName.value = resp.data.last_name || '';
    username.value = resp.data.username || '';
    email.value = resp.data.email || '';
    timezone.value = resp.data.timezone || '';
    if (resp.data.avatar_url) {
      profileAvatarUrl.value = resp.data.avatar_url;
      authStore.setAvatarUrl(resp.data.avatar_url);
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to load profile.';
  }
}

async function handleSave() {
  message.value = '';
  error.value = '';
  saving.value = true;
  try {
    const resp = await authService.updateProfile({
      first_name: firstName.value,
      last_name: lastName.value,
      username: username.value,
      email: email.value,
      timezone: timezone.value,
    });
    message.value = 'Profile saved.';
    firstName.value = resp.data.first_name ?? firstName.value;
    lastName.value = resp.data.last_name ?? lastName.value;
    email.value = resp.data.email || email.value;
    username.value = resp.data.username || username.value;
    authStore.setName(resp.data.first_name ?? '', resp.data.last_name ?? '');
    if (newPassword.value || confirmPassword.value) await handlePasswordChange();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to save profile.';
  } finally {
    saving.value = false;
  }
}

async function handlePasswordChange() {
  if (newPassword.value !== confirmPassword.value) { error.value = 'New passwords do not match.'; return; }
  try {
    await authService.changePassword({ current_password: '', new_password: newPassword.value, confirm_password: confirmPassword.value });
    message.value = 'Password updated.';
    newPassword.value = '';
    confirmPassword.value = '';
    computeStrength();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to change password.';
  }
}

const prefs = ref<any>(null);
const prefsLoading = ref(false);
const prefsSaveMsg = ref('');
let prefsSaveTimer: ReturnType<typeof setTimeout> | null = null;

async function loadPrefs() {
  prefsLoading.value = true;
  try { const res = await notificationApi.getPrefs(); prefs.value = res.data; } catch {} finally { prefsLoading.value = false; }
}

async function savePrefs() {
  if (!prefs.value) return;
  try {
    await notificationApi.patchPrefs(prefs.value);
    prefsSaveMsg.value = 'Saved.';
    if (prefsSaveTimer) clearTimeout(prefsSaveTimer);
    prefsSaveTimer = setTimeout(() => { prefsSaveMsg.value = ''; }, 2000);
  } catch {}
}

onMounted(() => {
  loadTimezones();
  loadProfile();
  loadStats();
  loadBadges();
  loadPrefs();
});

function computeStrength() {
  const { score, label, color } = evaluatePassword(newPassword.value);
  strengthValue.value = score;
  strengthLabel.value = label;
  const colorMap: Record<string, string> = { negative: '#ba1a1a', warning: '#e8a020', positive: '#496640', grey: '#d5c6c0' };
  strengthColorHex.value = colorMap[color] ?? '#d5c6c0';
}
</script>
