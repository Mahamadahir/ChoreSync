import { api } from './api';

// ── Types ─────────────────────────────────────────────────────────────────────

export type GoogleCalendarItem = {
  id: string;
  summary: string;
  color: string;
  writable: boolean;
  timeZone: string;
  primary: boolean;
  already_synced?: boolean;
};

export type GoogleCalendarSelectItem = {
  id: string;
  name: string;
  include_in_availability: boolean;
  writable: boolean;
  color?: string;
  timezone?: string;
};

export type OutlookCalendarItem = {
  id: string;
  name: string;
  color: string;
  is_default: boolean;
  can_edit: boolean;
};

export type OutlookCalendarSelectItem = {
  id: string;
  name: string;
  include_in_availability: boolean;
  writable: boolean;
  is_task_writeback: boolean;
  color?: string;
};

export type CalendarStatus = {
  google: { connected: boolean };
  outlook: { connected: boolean };
};

// ── Service ───────────────────────────────────────────────────────────────────

export const calendarService = {
  // ── Google ────────────────────────────────────────────────────
  googleAuthUrl: () =>
    api.get<{ auth_url: string }>('/api/calendar/google/auth-url/?mobile=true'),

  googleList: () =>
    api.get<GoogleCalendarItem[]>('/api/calendar/google/list/'),

  googleSelect: (calendars: GoogleCalendarSelectItem[]) =>
    api.post('/api/calendar/google/select/', calendars),

  googleSync: () =>
    api.post('/api/calendar/google/sync/'),

  // ── Outlook ───────────────────────────────────────────────────
  outlookAuthUrl: () =>
    api.get<{ auth_url: string }>('/api/calendar/outlook/auth-url/?mobile=true'),

  outlookList: () =>
    api.get<OutlookCalendarItem[]>('/api/calendar/outlook/list/'),

  outlookSelect: (calendars: OutlookCalendarSelectItem[]) =>
    api.post('/api/calendar/outlook/select/', calendars),

  outlookSync: () =>
    api.post('/api/calendar/outlook/sync/'),

  // ── Status ────────────────────────────────────────────────────
  status: () =>
    api.get<CalendarStatus>('/api/calendar/status/'),
};
