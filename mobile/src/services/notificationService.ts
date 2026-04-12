import { api } from './api';

export const notificationService = {
  list: () => api.get('/api/notifications/'),

  history: (params?: { limit?: number; offset?: number }) =>
    api.get('/api/notifications/history/', { params }),

  markRead: (id: number) => api.post(`/api/notifications/${id}/read/`),

  dismiss: (id: number) => api.post(`/api/notifications/${id}/dismiss/`),

  getPrefs: () => api.get('/api/users/me/notification-preferences/'),

  updatePrefs: (payload: object) =>
    api.patch('/api/users/me/notification-preferences/', payload),

  // Expo push token registration
  registerPushToken: (token: string, platform: string) =>
    api.post('/api/push-token/', { token, platform }),

  deregisterPushToken: (token: string) =>
    api.delete('/api/push-token/', { data: { token } }),
};
