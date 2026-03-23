<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 720px; width: 100%;">
      <div class="text-h5 q-mb-xs">Account & Profile</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        Update your contact info or change your password. Changes are saved via your authenticated session.
      </div>

      <q-form @submit="handleSave" class="q-gutter-md">
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-input v-model="username" label="Username" outlined dense />
          </div>
          <div class="col-12 col-md-6">
            <q-input v-model="email" type="email" label="Email" outlined dense />
          </div>
          <div class="col-12">
            <q-select
              v-model="timezone"
              :options="filteredTimezones"
              option-label="label"
              option-value="value"
              label="Timezone (UTC offset)"
              outlined
              dense
              clearable
              use-input
              fill-input
              input-debounce="0"
              @filter="filterTimezones"
              hint="Select by UTC offset; common cities shown for context"
            />
          </div>
        </div>

        <q-separator />

        <div class="text-subtitle1">Change Password</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-input
              v-model="newPassword"
              :type="showNewPassword ? 'text' : 'password'"
              label="New password"
              outlined
              dense
              autocomplete="new-password"
              @update:model-value="computeStrength"
              stack-label
            >
              <template #append>
                <q-icon
                  :name="showNewPassword ? 'visibility_off' : 'visibility'"
                  class="cursor-pointer"
                  @click="showNewPassword = !showNewPassword"
                />
              </template>
            </q-input>
          </div>
          <div class="col-12 col-md-6">
            <q-input
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              label="Confirm new password"
              outlined
              dense
              autocomplete="new-password"
              stack-label
            >
              <template #append>
                <q-icon
                  :name="showConfirmPassword ? 'visibility_off' : 'visibility'"
                  class="cursor-pointer"
                  @click="showConfirmPassword = !showConfirmPassword"
                />
              </template>
            </q-input>
          </div>
          <div class="col-12">
            <q-linear-progress
              :value="strengthValue"
              :color="strengthColor"
              track-color="grey-4"
              size="12px"
              class="q-mt-sm"
            />
            <div class="text-caption text-grey-7 q-mt-xs">{{ strengthLabel }}</div>
          </div>
        </div>

        <q-btn type="submit" label="Save changes" color="primary" class="full-width" :loading="saving" />
      </q-form>

      <q-banner v-if="message" class="q-mt-md" type="positive" dense>{{ message }}</q-banner>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>

      <!-- ── Stats ── -->
      <q-separator class="q-my-lg" />
      <div class="text-subtitle1 q-mb-sm">Your Stats</div>
      <div v-if="stats" class="row q-col-gutter-md q-mb-md">
        <div class="col-6 col-sm-3">
          <q-card flat bordered class="text-center q-pa-sm">
            <div class="text-h5 text-primary">{{ stats.total_tasks_completed }}</div>
            <div class="text-caption text-grey-6">Tasks done</div>
          </q-card>
        </div>
        <div class="col-6 col-sm-3">
          <q-card flat bordered class="text-center q-pa-sm">
            <div class="text-h5 text-amber-8">{{ stats.total_points }}</div>
            <div class="text-caption text-grey-6">Points</div>
          </q-card>
        </div>
        <div class="col-6 col-sm-3">
          <q-card flat bordered class="text-center q-pa-sm">
            <div class="text-h5 text-positive">{{ stats.current_streak_days }}</div>
            <div class="text-caption text-grey-6">Day streak</div>
          </q-card>
        </div>
        <div class="col-6 col-sm-3">
          <q-card flat bordered class="text-center q-pa-sm">
            <div class="text-h5 text-info">{{ Math.round((stats.on_time_completion_rate ?? 0) * 100) }}%</div>
            <div class="text-caption text-grey-6">On-time rate</div>
          </q-card>
        </div>
      </div>
      <div v-else-if="statsLoading" class="row justify-center q-pa-md">
        <q-spinner color="primary" size="32px" />
      </div>
      <div v-else class="text-caption text-grey-6 q-mb-md">No stats yet — complete some tasks to see your progress.</div>

      <!-- ── Charts ── -->
      <template v-if="statsRaw.length > 0">
        <q-separator class="q-my-lg" />
        <div class="text-subtitle1 q-mb-sm">Progress Charts</div>
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-12 col-md-6">
            <q-card flat bordered class="q-pa-md">
              <TasksOverTimeChart :data="weeklyCompletions" />
            </q-card>
          </div>
          <div class="col-12 col-md-6">
            <q-card flat bordered class="q-pa-md">
              <CategoryBreakdownChart :data="categoryBreakdown" />
            </q-card>
          </div>
        </div>
      </template>

      <!-- ── Badges ── -->
      <q-separator class="q-my-lg" />
      <div class="text-subtitle1 q-mb-sm">Badges</div>
      <div v-if="badges.length === 0 && !badgesLoading" class="text-caption text-grey-6 q-mb-md">
        No badges earned yet.
      </div>
      <div v-else class="row q-gutter-sm q-mb-md">
        <q-chip
          v-for="b in badges"
          :key="b.id"
          icon="emoji_events"
          color="amber-7"
          text-color="white"
          :label="b.badge_name"
        >
          <q-tooltip>{{ b.badge_description }} · Earned {{ formatDate(b.awarded_at) }}</q-tooltip>
        </q-chip>
      </div>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { authService } from '../services/authService';
import { statsApi } from '../services/api';
import { evaluatePassword } from '../utils/passwordStrength';
import TasksOverTimeChart from '../components/charts/TasksOverTimeChart.vue';
import CategoryBreakdownChart from '../components/charts/CategoryBreakdownChart.vue';

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
const strengthColor = ref('grey');
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);

const stats = ref<any>(null);
const statsLoading = ref(false);
const statsRaw = ref<any[]>([]);
const badges = ref<any[]>([]);
const badgesLoading = ref(false);

const weeklyCompletions = computed<{ week: string; count: number }[]>(() => {
  // Merge weekly_completions across all households, summing counts per week
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
  } catch { /* no stats yet */ } finally {
    statsLoading.value = false;
  }
}

async function loadBadges() {
  badgesLoading.value = true;
  try {
    const res = await statsApi.myBadges();
    badges.value = res.data;
  } catch { /* no badges yet */ } finally {
    badgesLoading.value = false;
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function detectBrowserTimeZoneOffset(): string | null {
  try {
    const mins = new Date().getTimezoneOffset(); // minutes behind UTC
    const offsetHours = -mins / 60;
    const sign = offsetHours >= 0 ? '+' : '-';
    const padded = Math.abs(offsetHours).toString().padStart(2, '0');
    return `UTC${sign}${padded}`;
  } catch {
    return null;
  }
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
    if (!val) {
      filteredTimezones.value = timezoneOptions.value;
      return;
    }
    const needle = val.toLowerCase();
    filteredTimezones.value = timezoneOptions.value.filter((z) => z.label.toLowerCase().includes(needle));
  });
}

async function loadProfile() {
  try {
    const resp = await authService.getProfile();
    username.value = resp.data.username || '';
    email.value = resp.data.email || '';
    timezone.value = resp.data.timezone || detectBrowserTimeZoneOffset() || '';
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to load profile. Please log in again.';
  }
}

async function handleSave() {
  message.value = '';
  error.value = '';
  saving.value = true;
  try {
    const resp = await authService.updateProfile({
      username: username.value,
      email: email.value,
      timezone: timezone.value,
    });
    message.value = 'Profile saved.';
    email.value = resp.data.email || email.value;
    username.value = resp.data.username || username.value;

    if (newPassword.value || confirmPassword.value) {
      await handlePasswordChange();
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to save profile.';
  } finally {
    saving.value = false;
  }
}

async function handlePasswordChange() {
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'New passwords do not match.';
    return;
  }
  try {
    await authService.changePassword({
      current_password: '', // current password omitted per request
      new_password: newPassword.value,
      confirm_password: confirmPassword.value,
    });
    message.value = 'Password updated.';
    newPassword.value = '';
    confirmPassword.value = '';
    computeStrength('');
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to change password.';
  }
}

onMounted(() => {
  loadTimezones();
  loadProfile();
  loadStats();
  loadBadges();
});

function computeStrength(value: string) {
  const { score, label, color } = evaluatePassword(value || newPassword.value);
  strengthValue.value = score;
  strengthLabel.value = label;
  strengthColor.value = color;
}
</script>
