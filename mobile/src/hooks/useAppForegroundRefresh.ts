/**
 * If mounted, reloads notifications whenever the app returns to the foreground.
 *
 * Uses a delta fetch when a lastSeenId is available — only notifications newer
 * than the last known id are fetched and merged into the store. Falls back to
 * a full fetch on first launch (no stored id) so no notifications are missed.
 */
import { useEffect, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { notificationService } from '../services/notificationService';
import { tokenStorage } from '../services/tokenStorage';
import { useNotificationStore } from '../stores/notificationStore';
import type { Notification } from '../types/notification';

export function useAppForegroundRefresh() {
  const setNotifications = useNotificationStore((s) => s.setNotifications);
  const mergeNotifications = useNotificationStore((s) => s.mergeNotifications);
  const appState = useRef<AppStateStatus>(AppState.currentState);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', async (nextState) => {
      // Only trigger on background → foreground transitions
      if (appState.current !== 'active' && nextState === 'active') {
        try {
          const sinceId = await tokenStorage.getLastNotifId();
          const res = sinceId
            ? await notificationService.listSince(sinceId)
            : await notificationService.list();

          const data: Notification[] = Array.isArray(res.data)
            ? res.data
            : (res.data?.results ?? []);

          if (data.length > 0) {
            const maxId = String(Math.max(...data.map((n) => Number(n.id))));
            await tokenStorage.saveLastNotifId(maxId);
            sinceId ? mergeNotifications(data) : setNotifications(data);
          }
        } catch {
          // Best-effort — ignore network errors on resume
        }
      }
      appState.current = nextState;
    });

    return () => subscription.remove();
  }, [setNotifications, mergeNotifications]);
}
