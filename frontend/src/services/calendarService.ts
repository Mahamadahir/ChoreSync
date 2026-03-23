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

  // Outlook / Microsoft Graph
  getOutlookAuthUrl() {
    return api.get<{ auth_url: string }>('/api/calendar/outlook/auth-url/');
  },
  listOutlookCalendars() {
    return api.get<{
      id: string;
      name: string;
      color: string;
      is_default: boolean;
      can_edit: boolean;
    }[]>('/api/calendar/outlook/list/');
  },
  selectOutlookCalendars(payload: Array<{
    id: string;
    name: string;
    include_in_availability: boolean;
    writable: boolean;
    color?: string | null;
    timezone?: string | null;
  }>) {
    return api.post<{ detail: string; selected: string[] }>('/api/calendar/outlook/select/', payload);
  },
  syncOutlook() {
    return api.post<{ detail: string }>('/api/calendar/outlook/sync/');
  },
};
