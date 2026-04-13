import { api } from './api';

export const notificationService = {
  list: () => api.get('/api/notifications/'),

  markRead: (id: string | number) => api.post(`/api/notifications/${id}/read/`),

  dismiss: (id: string | number) => api.post(`/api/notifications/${id}/dismiss/`),

  getPrefs: () => api.get('/api/users/me/notification-preferences/'),

  updatePrefs: (payload: object) =>
    api.patch('/api/users/me/notification-preferences/', payload),

  listSince: (sinceId: string) =>
    api.get('/api/notifications/', { params: { since_id: sinceId } }),

  // Expo push token registration
  registerPushToken: (token: string, platform: string) =>
    api.post('/api/push-token/', { token, platform }),

  deregisterPushToken: (token: string) =>
    api.delete('/api/push-token/', { data: { token } }),
};
