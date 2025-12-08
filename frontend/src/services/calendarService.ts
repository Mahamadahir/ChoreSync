import { api } from './api';

export const calendarService = {
  getGoogleAuthUrl() {
    return api.get<{ auth_url: string }>('/api/calendar/google/auth-url/');
  },
  syncGoogle() {
    return api.post<{ detail: string }>('/api/calendar/google/sync/');
  },
  listGoogleCalendars() {
    return api.get<{
      id: string;
      summary: string;
      accessRole: string;
      primary: boolean;
      color?: string;
      writable: boolean;
      timeZone?: string;
    }[]>('/api/calendar/google/list/');
  },
  selectGoogleCalendars(payload: Array<{
    id: string;
    name: string;
    include_in_availability: boolean;
    writable: boolean;
    color?: string | null;
    timezone?: string | null;
  }>) {
    return api.post<{ detail: string; selected: string[] }>('/api/calendar/google/select/', payload);
  },
};
