import { create } from 'zustand';
import { tokenStorage } from '../services/tokenStorage';
import { registerAuthExpiredCallback } from '../services/api';
import type { User } from '../types/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;

  // Actions
  setUser: (user: User) => void;
  login: (access: string, refresh: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Register callback so the axios interceptor can trigger logout on token expiry
  registerAuthExpiredCallback(() => get().logout());

  return {
    user: null,
    isAuthenticated: false,
    isBootstrapping: true,

    setUser: (user) => set({ user }),

    login: async (access, refresh, user) => {
      await tokenStorage.save(access, refresh);
      set({ user, isAuthenticated: true });
    },

    logout: async () => {
      // Deregister push token before clearing credentials so the request can auth
      try {
        import('expo-notifications').then(async (Notifications) => {
          const tokenData = await Notifications.getExpoPushTokenAsync({
            projectId: 'f439146f-e3fe-4c46-98ca-4c612f97f692',
          });
          const { notificationService } = await import('../services/notificationService');
          await notificationService.deregisterPushToken(tokenData.data);
        });
      } catch {
        // Best-effort — a failed deregister just means the token expires naturally
      }
      await tokenStorage.clear();
      set({ user: null, isAuthenticated: false });
    },

    bootstrap: async () => {
      try {
        const access = await tokenStorage.getAccess();
        if (!access) {
          set({ isBootstrapping: false });
          return;
        }
        // Lazily import to avoid circular dependency at module load time
        const { authService } = await import('../services/authService');
        const { data } = await authService.getProfile();
        set({ user: data, isAuthenticated: true });
      } catch (err: any) {
        // Only clear tokens for auth errors (401/403). Network errors, timeouts,
        // and server errors should not force a logout — the stored refresh token
        // is still valid and the interceptor will retry on the next request.
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          await tokenStorage.clear();
          set({ user: null, isAuthenticated: false });
        }
        // For non-auth errors (network down, 5xx): leave tokens intact so
        // the user is not silently logged out on a transient failure.
      } finally {
        set({ isBootstrapping: false });
      }
    },
  };
});
