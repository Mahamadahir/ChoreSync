/**
 * Registers the device for Expo push notifications, stores the token with
 * the backend, and wires up foreground + tap-response listeners.
 *
 * Mount this hook inside a component that already has navigation context
 * (i.e. inside NavigationContainer). It renders nothing — side effects only.
 */
import { useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { notificationService } from '../services/notificationService';
import { useNotificationStore } from '../stores/notificationStore';
import type { Notification } from '../types/notification';

// Show a banner + play sound when a push arrives while the app is foregrounded.
// This is module-level and idempotent — safe to call multiple times.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export function usePushNotifications() {
  const navigation = useNavigation<any>();
  const prependNotification = useNotificationStore((s) => s.prependNotification);
  const receivedSub = useRef<Notifications.Subscription | null>(null);
  const responseSub = useRef<Notifications.Subscription | null>(null);

  // Navigate to the correct screen based on notification metadata.
  // Mirrors the logic in NotificationsScreen.handleCardNavigate.
  function handleNavigate(data: Partial<Notification & { id?: number }>) {
    const type = data.type;
    const groupId = data.group_id;
    const taskId = data.task_occurrence_id;
    try {
      if (
        taskId &&
        (type === 'task_assigned' || type === 'deadline_reminder' ||
         type === 'emergency_reassignment' || type === 'marketplace_claim' ||
         type === 'task_swap')
      ) {
        navigation.navigate('TasksTab', {
          screen: 'TaskDetail',
          params: { taskId },
        });
      } else if (type === 'task_proposal' && groupId) {
        navigation.navigate('GroupsTab', {
          screen: 'Proposals',
          params: { groupId },
        });
      } else if (type === 'message' && groupId) {
        navigation.navigate('GroupsTab', {
          screen: 'GroupDetail',
          params: { groupId, initialTab: 'chat' },
        });
      } else if (type === 'group_invite' && groupId) {
        navigation.navigate('GroupsTab', {
          screen: 'GroupDetail',
          params: { groupId, initialTab: 'people' },
        });
      } else if (type?.startsWith('suggestion_')) {
        navigation.navigate('TasksTab', { screen: 'Tasks' });
      } else if (type === 'badge_earned') {
        navigation.navigate('Profile');
      } else if (type === 'calendar_sync_complete') {
        navigation.navigate('CalendarTab', { screen: 'CalendarMain' });
      }
    } catch {
      // Stale entity or navigation not ready — silently ignore.
    }
  }

  useEffect(() => {
    registerForPushAsync(prependNotification);

    // Foreground: add to store so the in-app badge updates immediately.
    // The WebSocket will also deliver it, but the push may arrive first on
    // a freshly-opened app before the WS handshake completes.
    receivedSub.current = Notifications.addNotificationReceivedListener(
      (notification) => {
        const data = notification.request.content.data as Partial<Notification>;
        if (data?.id) {
          prependNotification(data as Notification);
        }
      },
    );

    // Tap from background / notification centre: navigate.
    responseSub.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data as Partial<Notification>;
        handleNavigate(data);
      },
    );

    // Cold-start tap (app was killed): handle the response that launched the app.
    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response?.notification.request.content.data) {
        const data = response.notification.request.content.data as Partial<Notification>;
        // Delay slightly so navigation stack is fully mounted before we push.
        setTimeout(() => handleNavigate(data), 500);
      }
    });

    return () => {
      receivedSub.current?.remove();
      responseSub.current?.remove();
    };
  }, []);
}

// ── Token registration ────────────────────────────────────────────────

async function registerForPushAsync(
  prependNotification: (n: Notification) => void,
) {
  if (Platform.OS === 'web') return;

  // Request permission (iOS shows a native prompt; Android 13+ also requires it).
  const { status: existing } = await Notifications.getPermissionsAsync();
  const finalStatus =
    existing === 'granted'
      ? existing
      : (await Notifications.requestPermissionsAsync()).status;

  if (finalStatus !== 'granted') return;

  // Android requires a named notification channel.
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'ChoreSync',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#94433a',
      sound: 'default',
    });
  }

  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: 'f439146f-e3fe-4c46-98ca-4c612f97f692',
    });
    await notificationService.registerPushToken(tokenData.data, Platform.OS);
  } catch {
    // Best-effort — a failed registration just means no push until next launch.
  }
}
