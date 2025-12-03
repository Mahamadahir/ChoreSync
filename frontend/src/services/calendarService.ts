import { api } from './api';

export const calendarService = {
  getGoogleAuthUrl() {
    return api.get<{ auth_url: string }>('/api/calendar/google/auth-url/');
  },
  syncGoogle() {
    return api.post<{ detail: string }>('/api/calendar/google/sync/');
  },
};
