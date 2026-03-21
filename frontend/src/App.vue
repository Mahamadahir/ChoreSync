<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-toolbar-title>ChoreSync</q-toolbar-title>
        <template v-if="authStore.isAuthenticated">
          <q-btn flat dense to="/groups">Groups</q-btn>
          <q-btn flat dense to="/tasks">My Tasks</q-btn>
          <q-btn flat dense to="/calendar">Calendar</q-btn>
          <q-btn flat dense to="/profile">Profile</q-btn>
        </template>
        <template v-else>
          <q-btn flat dense to="/signup">Sign Up</q-btn>
          <q-btn flat dense to="/login">Log In</q-btn>
        </template>
        <q-space />

        <!-- Dark mode toggle -->
        <q-btn flat dense round :icon="$q.dark.isActive ? 'light_mode' : 'dark_mode'" @click="toggleDark">
          <q-tooltip>{{ $q.dark.isActive ? 'Light mode' : 'Dark mode' }}</q-tooltip>
        </q-btn>

        <!-- Notification bell -->
        <template v-if="authStore.isAuthenticated">
          <q-btn flat dense round icon="notifications" @click="notifDrawer = true">
            <q-badge v-if="unreadCount > 0" color="red" :label="unreadCount" floating />
          </q-btn>
        </template>

        <q-btn v-if="authStore.isAuthenticated" flat dense icon="logout" label="Log Out" @click="handleLogout" />
      </q-toolbar>
    </q-header>

    <!-- Notification drawer -->
    <q-drawer v-model="notifDrawer" side="right" bordered :width="340">
      <q-toolbar class="bg-primary text-white">
        <q-toolbar-title>Notifications</q-toolbar-title>
        <q-btn flat round dense icon="close" @click="notifDrawer = false" />
      </q-toolbar>
      <div v-if="notifications.length === 0" class="text-center text-grey-6 q-pa-xl">
        <q-icon name="notifications_none" size="48px" />
        <div class="q-mt-sm">No notifications</div>
      </div>
      <q-list separator>
        <q-item v-for="n in notifications" :key="n.id" :class="{ 'bg-blue-1': !n.read }">
          <q-item-section>
            <q-item-label class="text-weight-medium">{{ n.title }}</q-item-label>
            <q-item-label caption>{{ n.content }}</q-item-label>
            <q-item-label caption class="text-grey-5">{{ formatDate(n.created_at) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="column q-gutter-xs">
              <q-btn v-if="!n.read" flat round dense icon="mark_email_read" size="xs" color="primary"
                @click="markRead(n.id)"><q-tooltip>Mark read</q-tooltip></q-btn>
              <q-btn flat round dense icon="close" size="xs" color="grey"
                @click="dismiss(n.id)"><q-tooltip>Dismiss</q-tooltip></q-btn>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useQuasar } from 'quasar';
import { authService } from './services/authService';
import { useAuthStore } from './stores/auth';
import { notificationApi } from './services/api';
import { NotificationSocketService } from './services/NotificationSocketService';

const $q = useQuasar();
const authStore = useAuthStore();
const notifDrawer = ref(false);

function toggleDark() {
  $q.dark.toggle();
  localStorage.setItem('choresync-dark', String($q.dark.isActive));
}
const notifications = ref<any[]>([]);
const socketSvc = new NotificationSocketService();

const unreadCount = computed(() => notifications.value.filter(n => !n.read).length);

async function loadNotifications() {
  if (!authStore.isAuthenticated) return;
  try {
    const res = await notificationApi.list();
    notifications.value = res.data;
  } catch {}
}

async function markRead(id: number) {
  try {
    await notificationApi.markRead(id);
    const n = notifications.value.find(n => n.id === id);
    if (n) n.read = true;
  } catch {}
}

async function dismiss(id: number) {
  try {
    await notificationApi.dismiss(id);
    notifications.value = notifications.value.filter(n => n.id !== id);
  } catch {}
}

async function handleLogout() {
  socketSvc.disconnect();
  try { await authService.logout(); } catch {}
  authStore.clear();
  window.history.pushState({}, '', '/login');
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

onMounted(() => {
  loadNotifications();
  socketSvc.onNotification((n) => {
    notifications.value.unshift(n);
  });
  if (authStore.isAuthenticated) socketSvc.connect();
});
onUnmounted(() => socketSvc.disconnect());
</script>
