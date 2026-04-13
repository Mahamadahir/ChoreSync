import { create } from 'zustand';
import type { Notification } from '../types/notification';

// Notification type → group detail tab mapping
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

const GROUP_TYPES = new Set(Object.keys(NOTIF_TAB));

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  groupsBadge: number;
  tasksBadge: number;
  setNotifications: (notifications: Notification[]) => void;
  prependNotification: (n: Notification) => void;
  markRead: (id: string | number) => void;
  markUnread: (id: string | number) => void;
  dismiss: (id: string | number) => void;
  mergeNotifications: (incoming: Notification[]) => void;
  groupBadge: (groupId: string) => number;
  tabBadge: (groupId: string, tab: string) => number;
}

const TASK_TYPES = new Set([
  'task_assigned', 'deadline_reminder', 'emergency_reassignment',
  'marketplace_claim', 'suggestion_pattern', 'suggestion_availability',
  'suggestion_preference', 'suggestion_streak', 'badge_earned',
]);

function computeDerived(notifications: Notification[]) {
  return {
    unreadCount: notifications.filter((n) => !n.read).length,
    groupsBadge: notifications.filter((n) => !n.read && GROUP_TYPES.has(n.type)).length,
    tasksBadge: notifications.filter((n) => !n.read && TASK_TYPES.has(n.type)).length,
  };
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  groupsBadge: 0,
  tasksBadge: 0,

  setNotifications: (notifications) =>
    set({ notifications, ...computeDerived(notifications) }),

  prependNotification: (n) => {
    const updated = [n, ...get().notifications];
    set({ notifications: updated, ...computeDerived(updated) });
  },

  markRead: (id) => {
    const sid = String(id);
    const updated = get().notifications.map((n) =>
      String(n.id) === sid ? { ...n, read: true } : n,
    );
    set({ notifications: updated, ...computeDerived(updated) });
  },

  markUnread: (id) => {
    const sid = String(id);
    const updated = get().notifications.map((n) =>
      String(n.id) === sid ? { ...n, read: false } : n,
    );
    set({ notifications: updated, ...computeDerived(updated) });
  },

  dismiss: (id) => {
    const sid = String(id);
    const updated = get().notifications.filter((n) => String(n.id) !== sid);
    set({ notifications: updated, ...computeDerived(updated) });
  },

  mergeNotifications: (incoming) => {
    const existing = get().notifications;
    const existingIds = new Set(existing.map((n) => String(n.id)));
    const novel = incoming.filter((n) => !existingIds.has(String(n.id)));
    if (novel.length === 0) return;
    const updated = [...novel, ...existing];
    set({ notifications: updated, ...computeDerived(updated) });
  },

  groupBadge: (groupId) =>
    get().notifications.filter(
      (n) => !n.read && n.group_id === groupId && GROUP_TYPES.has(n.type),
    ).length,

  tabBadge: (groupId, tab) =>
    get().notifications.filter(
      (n) => !n.read && n.group_id === groupId && NOTIF_TAB[n.type] === tab,
    ).length,
}));
