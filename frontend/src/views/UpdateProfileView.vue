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
            <q-input v-model="displayName" label="Display name" outlined dense />
          </div>
          <div class="col-12 col-md-6">
            <q-input v-model="email" type="email" label="Email" outlined dense />
          </div>
          <div class="col-12">
            <q-select
              v-model="timezone"
              :options="filteredTimezones"
              label="Timezone"
              outlined
              dense
              clearable
              use-input
              fill-input
              input-debounce="0"
              @filter="filterTimezones"
              hint="Search and select your timezone"
            />
          </div>
        </div>

        <q-separator />

        <div class="text-subtitle1">Change Password</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-4">
            <q-input
              v-model="currentPassword"
              type="password"
              label="Current password"
              outlined
              dense
              autocomplete="current-password"
            />
          </div>
          <div class="col-12 col-md-4">
            <q-input
              v-model="newPassword"
              type="password"
              label="New password"
              outlined
              dense
              autocomplete="new-password"
            />
          </div>
          <div class="col-12 col-md-4">
            <q-input
              v-model="confirmPassword"
              type="password"
              label="Confirm new password"
              outlined
              dense
              autocomplete="new-password"
            />
          </div>
        </div>

        <q-btn type="submit" label="Save changes" color="primary" class="full-width" :loading="saving" />
      </q-form>

      <q-banner v-if="message" class="q-mt-md" type="positive" dense>{{ message }}</q-banner>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { authService } from '../services/authService';

const displayName = ref('');
const email = ref('');
const timezone = ref('');
const saving = ref(false);
const message = ref('');
const error = ref('');
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const timezoneOptions = ref<string[]>([]);
const filteredTimezones = ref<string[]>([]);

function detectBrowserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

function loadTimezones() {
  let zones: string[] = [];
  try {
    zones = (Intl as any).supportedValuesOf?.('timeZone') || [];
  } catch {
    zones = [];
  }
  if (!zones.length) {
    zones = [
      'UTC',
      'America/New_York',
      'America/Chicago',
      'America/Denver',
      'America/Los_Angeles',
      'Europe/London',
      'Europe/Berlin',
      'Europe/Paris',
      'Asia/Kolkata',
      'Asia/Tokyo',
      'Australia/Sydney',
    ];
  }
  timezoneOptions.value = zones;
  filteredTimezones.value = zones;
}

function filterTimezones(val: string, update: (cb: () => void) => void) {
  update(() => {
    if (!val) {
      filteredTimezones.value = timezoneOptions.value;
      return;
    }
    const needle = val.toLowerCase();
    filteredTimezones.value = timezoneOptions.value.filter((z) => z.toLowerCase().includes(needle));
  });
}

async function loadProfile() {
  try {
    const resp = await authService.getProfile();
    displayName.value = resp.data.display_name || '';
    email.value = resp.data.email || '';
    timezone.value = resp.data.timezone || detectBrowserTimeZone() || '';
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
      display_name: displayName.value,
      email: email.value,
      timezone: timezone.value,
    });
    message.value = 'Profile saved.';
    email.value = resp.data.email || email.value;
    displayName.value = resp.data.display_name || displayName.value;

    if (currentPassword.value || newPassword.value || confirmPassword.value) {
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
      current_password: currentPassword.value,
      new_password: newPassword.value,
      confirm_password: confirmPassword.value,
    });
    message.value = 'Password updated.';
    currentPassword.value = '';
    newPassword.value = '';
    confirmPassword.value = '';
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to change password.';
  }
}

onMounted(() => {
  loadTimezones();
  loadProfile();
});
</script>
