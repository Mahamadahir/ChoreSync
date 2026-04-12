/**
 * If mounted, reloads notifications whenever the app returns to the foreground.
 *
 * This hook listens to AppState changes and re-fetches /api/notifications/
 * on every background → active transition. It must be explicitly mounted in
 * a component to have any effect; it does not run automatically app-wide.
 */
import { useEffect, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { notificationService } from '../services/notificationService';
import { useNotificationStore } from '../stores/notificationStore';

export function useAppForegroundRefresh() {
  const setNotifications = useNotificationStore((s) => s.setNotifications);
  const appState = useRef<AppStateStatus>(AppState.currentState);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState) => {
      // Only trigger on background → foreground transitions
      if (appState.current !== 'active' && nextState === 'active') {
        notificationService
          .list()
          .then((res) => {
            const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
            setNotifications(data);
          })
          .catch(() => {
            // Best-effort — ignore network errors on resume
          });
      }
      appState.current = nextState;
    });

    return () => subscription.remove();
  }, [setNotifications]);
}
