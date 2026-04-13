import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

// Notification type → group detail tab mapping.
// Used to compute per-tab badge counts in GroupDetailView and
// per-group badge counts in GroupsView.
export const NOTIF_TAB: Record<string, string> = {
  message:                'chat',
  task_assigned:          'tasks',
  deadline_reminder:      'tasks',
  emergency_reassignment: 'tasks',
  marketplace_claim:      'tasks',
  task_swap:              'tasks',
  task_proposal:          'discover',
  task_suggestion:        'discover',
  suggestion_pattern:     'discover',
  suggestion_availability:'discover',
  suggestion_preference:  'discover',
  suggestion_streak:      'discover',
  group_invite:           'people',
};

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref<any[]>([]);

  const unreadCount = computed(() =>
    notifications.value.filter((n) => !n.read).length,
  );

  // Total unread for the Tasks sidebar badge
  const TASK_TYPES = new Set([
    'task_assigned', 'deadline_reminder', 'emergency_reassignment',
    'marketplace_claim', 'suggestion_pattern', 'suggestion_availability',
    'suggestion_preference', 'suggestion_streak', 'badge_earned',
  ]);
  const tasksBadge = computed(() =>
    notifications.value.filter((n) => !n.read && TASK_TYPES.has(n.type)).length,
  );

  // Total unread across all groups for the Groups sidebar badge
  const GROUP_TYPES = new Set(Object.keys(NOTIF_TAB));
  const groupsBadge = computed(() =>
    notifications.value.filter((n) => !n.read && GROUP_TYPES.has(n.type)).length,
  );

  // Unread count for a specific group
  function groupBadge(groupId: string): number {
    return notifications.value.filter(
      (n) => !n.read && n.group_id === groupId && GROUP_TYPES.has(n.type),
    ).length;
  }

  // Unread count for a specific group + tab combination
  function tabBadge(groupId: string, tab: string): number {
    return notifications.value.filter(
      (n) => !n.read && n.group_id === groupId && NOTIF_TAB[n.type] === tab,
    ).length;
  }

  function setNotifications(list: any[]) {
    notifications.value = list;
  }

  function prepend(n: any) {
    notifications.value.unshift(n);
  }

  function markRead(id: number) {
    const n = notifications.value.find((x) => x.id === id);
    if (n) n.read = true;
  }

  function remove(id: number) {
    notifications.value = notifications.value.filter((n) => n.id !== id);
  }

  return {
    notifications,
    unreadCount,
    tasksBadge,
    groupsBadge,
    groupBadge,
    tabBadge,
    setNotifications,
    prepend,
    markRead,
    remove,
  };
});
