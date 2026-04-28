<template>
  <!-- Guest layout (login, signup, etc.) -->
  <div v-if="!authStore.isAuthenticated" class="cs-guest-bg">
    <router-view />
  </div>

  <!-- Authenticated shell: sidebar + topbar + content -->
  <div v-else class="cs-app-shell">

    <!-- ── Sidebar ─────────────────────────────────────────── -->
    <nav class="cs-sidebar">
      <!-- Brand -->
      <div class="cs-sidebar-brand">
        <span class="material-symbols-outlined">home_work</span>
        <div>
          <div class="cs-brand-name">ChoreSync</div>
          <div class="cs-brand-sub">Household Harmony</div>
        </div>
      </div>

      <!-- Nav items -->
      <div class="cs-nav-items">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          custom
          v-slot="{ isActive, navigate }"
        >
          <button
            @click="navigate"
            :class="['cs-nav-item', { 'cs-nav-item--active': isActive }]"
          >
            <span class="material-symbols-outlined">{{ item.icon }}</span>
            <span class="cs-nav-label">{{ item.label }}</span>
            <span v-if="item.badge && item.badge > 0" class="cs-nav-badge">{{ item.badge }}</span>
          </button>
        </router-link>
      </div>

      <!-- Legal links -->
      <div class="cs-sidebar-legal">
        <router-link to="/privacy" class="cs-legal-link">Privacy</router-link>
        <span class="cs-legal-dot">·</span>
        <router-link to="/terms" class="cs-legal-link">Terms</router-link>
      </div>

      <!-- New task -->
      <button class="cs-new-task-btn" @click="newTaskModalOpen = true">
        <span class="material-symbols-outlined">add_task</span>
        New Task
      </button>

      <!-- User footer -->
      <div class="cs-sidebar-footer">
        <div class="cs-user-avatar">
          <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" :alt="userInitials" class="cs-user-avatar-img" />
          <span v-else>{{ userInitials }}</span>
        </div>
        <div class="cs-user-info" style="flex:1;min-width:0">
          <div class="cs-user-name">{{ authStore.username || 'User' }}</div>
          <div class="cs-user-email">{{ authStore.email || '' }}</div>
        </div>
        <button class="cs-icon-btn" @click="handleLogout" title="Log out">
          <span class="material-symbols-outlined">logout</span>
        </button>
      </div>
    </nav>

    <!-- ── Top bar ─────────────────────────────────────────── -->
    <header class="cs-topbar">
      <div class="cs-topbar-title">{{ currentPageTitle }}</div>
      <div class="cs-topbar-actions">
        <div class="cs-search-box">
          <span class="material-symbols-outlined">search</span>
          <input type="text" placeholder="Search tasks…" v-model="searchQuery" />
        </div>
        <button
          class="cs-icon-btn"
          style="position:relative"
          @click="notifPanelOpen = !notifPanelOpen"
          title="Notifications"
        >
          <span class="material-symbols-outlined">notifications</span>
          <span v-if="unreadCount > 0" class="cs-notif-dot">{{ unreadCount }}</span>
        </button>
      </div>
    </header>

    <!-- ── Main content ────────────────────────────────────── -->
    <main class="cs-content">
      <router-view />
    </main>

    <!-- ── Streak suggestion popup ───────────────────────────── -->
    <SuggestionPopup ref="suggestionPopupRef" />

    <!-- ── Notification backdrop ───────────────────────────── -->
    <div
      v-if="notifPanelOpen"
      class="cs-notif-backdrop"
      @click="notifPanelOpen = false"
    />

    <!-- ── Notification panel ──────────────────────────────── -->
    <aside class="cs-notif-panel" :class="{ 'cs-notif-panel--open': notifPanelOpen }">
      <div class="cs-notif-header">
        <div class="cs-notif-title">Notifications</div>
        <div style="display:flex;align-items:center;gap:4px">
          <button
            v-if="unreadCount > 0"
            class="cs-icon-btn"
            title="Mark all as read"
            @click="markAllRead"
          >
            <span class="material-symbols-outlined">done_all</span>
          </button>
          <button
            class="cs-icon-btn"
            @click="notifPanelOpen = false; $router.push({ name: 'profile' })"
            title="Notification preferences"
          >
            <span class="material-symbols-outlined">settings</span>
          </button>
          <button class="cs-icon-btn" @click="notifPanelOpen = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
      </div>

      <div v-if="notifications.length === 0" class="cs-empty-notifs">
        <span class="material-symbols-outlined cs-empty-icon">notifications_none</span>
        <div>All caught up!</div>
      </div>

      <div v-else class="cs-notif-list">
        <div
          v-for="n in notifications"
          :key="n.id"
          :class="['cs-notif-item', { 'cs-notif-item--unread': !n.read }]"
          @click="handleNotificationClick(n)"
        >
          <div class="cs-notif-body">
            <div class="cs-notif-item-title">{{ n.title }}</div>
            <div class="cs-notif-item-content">{{ n.content }}</div>
            <div class="cs-notif-item-time">{{ formatDate(n.created_at) }}</div>
          </div>
          <div class="cs-notif-item-actions">
            <button
              v-if="!n.read"
              class="cs-icon-btn-sm"
              @click.stop="markRead(n.id)"
              title="Mark read"
            >
              <span class="material-symbols-outlined">mark_email_read</span>
            </button>
            <button
              class="cs-icon-btn-sm"
              @click.stop="dismiss(n.id)"
              title="Dismiss"
            >
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- ── New Personal Task Modal ───────────────────────────── -->
    <div v-if="newTaskModalOpen" class="cs-modal-backdrop" @click.self="closeNewTaskModal">
      <div class="cs-modal">
        <div class="cs-modal-header">
          <span class="cs-modal-title">New Personal Task</span>
          <button class="cs-icon-btn" @click="closeNewTaskModal">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <form class="cs-modal-body" @submit.prevent="submitNewTask">
          <div class="cs-form-group">
            <label class="cs-form-label">Task name *</label>
            <input
              class="cs-form-input"
              v-model="newTask.name"
              placeholder="e.g. Buy groceries"
              required
              autofocus
            />
          </div>
          <div class="cs-form-group">
            <label class="cs-form-label">Deadline</label>
            <input
              class="cs-form-input"
              type="datetime-local"
              v-model="newTask.deadline"
            />
          </div>
          <div class="cs-form-group">
            <label class="cs-form-label">Estimated time (minutes)</label>
            <input
              class="cs-form-input"
              type="number"
              min="1"
              v-model.number="newTask.estimated_mins"
            />
          </div>
          <div class="cs-form-group">
            <label class="cs-form-label">Category</label>
            <select class="cs-form-input" v-model="newTask.category">
              <option value="other">Other</option>
              <option value="cleaning">Cleaning</option>
              <option value="cooking">Cooking</option>
              <option value="laundry">Laundry</option>
              <option value="maintenance">Maintenance</option>
            </select>
          </div>
          <div class="cs-form-group">
            <label class="cs-form-label">Notes</label>
            <textarea
              class="cs-form-input"
              rows="2"
              v-model="newTask.details"
              placeholder="Optional details…"
            />
          </div>
          <div v-if="newTaskError" class="cs-form-error">{{ newTaskError }}</div>
          <div class="cs-modal-actions">
            <button type="button" class="cs-btn cs-btn--ghost" @click="closeNewTaskModal">Cancel</button>
            <button type="submit" class="cs-btn cs-btn--primary" :disabled="newTaskSubmitting">
              {{ newTaskSubmitting ? 'Creating…' : 'Create Task' }}
            </button>
          </div>
        </form>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { authService } from './services/authService';
import { useAuthStore } from './stores/auth';
import { useNotificationStore } from './stores/notifications';
import { notificationApi, taskApi } from './services/api';
import { NotificationSocketService } from './services/NotificationSocketService';
import SuggestionPopup from './components/SuggestionPopup.vue';

const authStore = useAuthStore();
const notifStore = useNotificationStore();
const router = useRouter();
const route = useRoute();

const notifPanelOpen = ref(false);
const searchQuery = ref('');
const socketSvc = new NotificationSocketService();
const suggestionPopupRef = ref<InstanceType<typeof SuggestionPopup> | null>(null);

// ── Personal task modal ───────────────────────────────────────────────────
const newTaskModalOpen = ref(false);
const newTaskSubmitting = ref(false);
const newTaskError = ref('');
const newTask = ref({ name: '', deadline: '', estimated_mins: 30, category: 'other', details: '' });

function closeNewTaskModal() {
  newTaskModalOpen.value = false;
  newTaskError.value = '';
  newTask.value = { name: '', deadline: '', estimated_mins: 30, category: 'other', details: '' };
}

async function submitNewTask() {
  newTaskError.value = '';
  newTaskSubmitting.value = true;
  try {
    const payload: Record<string, any> = {
      name: newTask.value.name,
      estimated_mins: newTask.value.estimated_mins,
      category: newTask.value.category,
      details: newTask.value.details,
    };
    if (newTask.value.deadline) {
      payload.deadline = new Date(newTask.value.deadline).toISOString();
    }
    await taskApi.createPersonal(payload);
    closeNewTaskModal();
    router.push({ name: 'tasks' });
  } catch (err: any) {
    newTaskError.value = err?.response?.data?.detail ?? 'Failed to create task.';
  } finally {
    newTaskSubmitting.value = false;
  }
}

const notifications = computed(() => notifStore.notifications);
const unreadCount = computed(() => notifStore.unreadCount);
const tasksBadge = computed(() => notifStore.tasksBadge);
const groupsBadge = computed(() => notifStore.groupsBadge);

const userInitials = computed(() => {
  const name = authStore.username || authStore.email || 'U';
  return name.slice(0, 2).toUpperCase();
});

const pageTitles: Record<string, string> = {
  home: 'Dashboard',
  tasks: 'My Tasks',
  groups: 'My Groups',
  'group-detail': 'Group',
  profile: 'Profile & Settings',
  calendar: 'Calendar',
  'google-calendar-select': 'Calendar Setup',
  'outlook-calendar-select': 'Calendar Setup',
  'assistant': 'AI Assistant',
};

const currentPageTitle = computed(() => {
  const name = route.name as string;
  return pageTitles[name] ?? 'ChoreSync';
});

const navItems = computed(() => [
  { to: '/home',      icon: 'home',             label: 'Dashboard', badge: 0 },
  { to: '/tasks',     icon: 'checklist',        label: 'My Tasks',  badge: tasksBadge.value },
  { to: '/groups',    icon: 'group',            label: 'Groups',    badge: groupsBadge.value },
  { to: '/calendar',  icon: 'calendar_month',   label: 'Calendar',  badge: 0 },
  { to: '/assistant', icon: 'smart_toy',        label: 'Assistant', badge: 0 },
  { to: '/profile',   icon: 'manage_accounts',  label: 'Profile',   badge: 0 },
]);

async function loadNotifications() {
  if (!authStore.isAuthenticated) return;
  try {
    const res = await notificationApi.list();
    notifStore.setNotifications(res.data);
  } catch {}
}

async function markRead(id: number) {
  try {
    await notificationApi.markRead(id);
    notifStore.markRead(id);
  } catch {}
}

async function markAllRead() {
  notifStore.markAllRead(); // optimistic
  try {
    await notificationApi.markAllRead();
  } catch {}
}

async function dismiss(id: number) {
  try {
    await notificationApi.dismiss(id);
    notifStore.remove(id);
  } catch {}
}

async function handleNotificationClick(n: any) {
  if (!n.read) await markRead(n.id);
  notifPanelOpen.value = false;

  // Translate backend action_url values to defined Vue routes.
  // The backend emits paths like /tasks/<id>, /groups/<id>?tab=chat — some
  // of which have no direct Vue route. Resolve to the nearest navigable destination.
  try {
    const url = n.action_url || '';

    // /tasks/<id> → tasks list (no dedicated task detail route in Vue)
    const taskMatch = url.match(/^\/tasks\/(\d+)$/);
    if (taskMatch) {
      await router.push({ name: 'tasks' });
      return;
    }

    // /groups/<id>?tab=<tab> → group detail with optional tab query
    const groupMatch = url.match(/^\/groups\/([^?]+)/);
    if (groupMatch) {
      const tabMatch = url.match(/[?&]tab=([^&]+)/);
      await router.push({
        name: 'group-detail',
        params: { id: groupMatch[1] },
        ...(tabMatch ? { query: { tab: tabMatch[1] } } : {}),
      });
      return;
    }

    // group_invite → invitation accept/decline screen
    const inviteMatch = url.match(/^\/invitations\/(\d+)$/);
    if (inviteMatch || n.type === 'group_invite') {
      if (inviteMatch) {
        await router.push({ name: 'invitation', params: { id: inviteMatch[1] } });
      } else if (n.group_id) {
        await router.push({ name: 'group-detail', params: { id: n.group_id } });
      }
      return;
    }

    // fallback: any notification with only group_id and no action_url
    if (!url && n.group_id) {
      await router.push({ name: 'group-detail', params: { id: n.group_id } });
      return;
    }

    // task_proposal — use group_id + proposals tab if available
    if (n.type === 'task_proposal' && n.group_id) {
      await router.push({ name: 'group-detail', params: { id: n.group_id }, query: { tab: 'discover' } });
      return;
    }

    // badge_earned → profile (user stats / achievements)
    if (n.type === 'badge_earned') {
      await router.push({ name: 'profile' });
      return;
    }

    // calendar_sync_complete → calendar tab
    if (n.type === 'calendar_sync_complete' || url === '/calendar') {
      await router.push({ name: 'calendar' });
      return;
    }

    // Fallback: push the raw url if it has a value
    if (url) {
      await router.push(url);
    }
  } catch {
    // Navigation failures (deleted entity, stale route) are silently ignored
    // to avoid surfacing a confusing error for an otherwise-read notification.
  }
}

async function handleLogout() {
  socketSvc.disconnect();
  try { await authService.logout(); } catch {}
  authStore.clear();
  notifStore.setNotifications([]);
  router.push({ name: 'login' });
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// Register handlers once — these survive reconnects
socketSvc.onNotification((n) => {
  notifStore.prepend(n);
  if (n.type === 'suggestion_streak' && suggestionPopupRef.value) {
    const parsed = suggestionPopupRef.value.parseNotification(n);
    if (parsed) suggestionPopupRef.value.push(parsed);
  }
});

// Connect/disconnect the socket whenever auth state changes.
// This handles: initial page load (auth may be async), login, and logout.
watch(
  () => authStore.isAuthenticated,
  (authed) => {
    if (authed) {
      loadNotifications();
      socketSvc.connect();
    } else {
      socketSvc.disconnect();
      notifStore.setNotifications([]);
    }
  },
  { immediate: true },
);

onMounted(() => {
  // Fallback: if auth was already true before the watcher ran (e.g. SSR hydration edge-case)
  if (authStore.isAuthenticated && !socketSvc.isConnected) {
    loadNotifications();
    socketSvc.connect();
  }
});
onUnmounted(() => socketSvc.disconnect());
</script>
