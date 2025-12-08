<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 640px; width: 100%;">
      <div class="text-h5 q-mb-sm">Welcome to ChoreSync</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        You are signed in. Use the shortcuts below to manage your account or keep working.
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-card flat bordered class="q-pa-md">
            <div class="text-subtitle1 q-mb-xs">Profile</div>
            <div class="text-body2 text-grey-7 q-mb-sm">Update your email or password.</div>
            <q-btn to="/profile" color="primary" label="Go to Profile" unelevated />
          </q-card>
        </div>
        <div class="col-12 col-md-6">
          <q-card flat bordered class="q-pa-md">
            <div class="text-subtitle1 q-mb-xs">Calendar</div>
            <div class="text-body2 text-grey-7 q-mb-sm">View and manage your events/tasks.</div>
            <q-btn to="/calendar" color="secondary" label="Open Calendar" unelevated />
            <q-btn
              class="q-mt-sm"
              outline
              color="primary"
              label="Connect Google Calendar"
              :loading="connectingGoogle"
              @click="handleGoogleConnect"
            />
            <q-btn
              class="q-mt-sm"
              color="secondary"
              outline
              label="Sync Google Now"
              :loading="syncingGoogle"
              @click="handleGoogleSync"
            />
            <q-btn
              class="q-mt-sm"
              color="primary"
              flat
              label="Choose Google Calendars"
              @click="router.push({ name: 'google-calendar-select' })"
            />
          </q-card>
        </div>
      </div>
      <div v-if="googleMessage" class="q-mt-md">
        <q-banner type="positive" dense>{{ googleMessage }}</q-banner>
      </div>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from '../stores/auth';
import { calendarService } from '../services/calendarService';
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const authStore = useAuthStore();
const connectingGoogle = ref(false);
const googleMessage = ref<string | null>(null);
const route = useRoute();
const router = useRouter();
const syncingGoogle = ref(false);

async function handleGoogleConnect() {
  connectingGoogle.value = true;
  try {
    const resp = await calendarService.getGoogleAuthUrl();
    if (resp.data?.auth_url) {
      window.location.href = resp.data.auth_url;
    }
  } catch (err) {
    // ignore errors
  } finally {
    connectingGoogle.value = false;
  }
}

onMounted(() => {
  const syncStatus = route.query.google_sync as string | undefined;
  if (syncStatus === 'success') {
    const imported = route.query.imported as string | undefined;
    router.replace({
      name: 'google-calendar-select',
      query: { connected: '1', imported },
    });
    return;
  } else if (syncStatus === 'error') {
    googleMessage.value = 'Google calendar connection failed. Please try again.';
  }
  if (syncStatus) {
    const { google_sync, imported, ...rest } = route.query;
    router.replace({ query: rest });
  }
});

async function handleGoogleSync() {
  syncingGoogle.value = true;
  try {
    const resp = await calendarService.syncGoogle();
    googleMessage.value = resp.data?.detail || 'Synced Google calendar.';
  } catch (err) {
    googleMessage.value = 'Google sync failed. Please try again.';
  } finally {
    syncingGoogle.value = false;
  }
}
</script>
