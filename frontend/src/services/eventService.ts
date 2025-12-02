import { api } from './api';

export type CalendarEvent = {
  id: number;
  title: string;
  start: string;
  end: string;
  is_all_day: boolean;
  blocks_availability: boolean;
  source: string;
  calendar_id: number;
  calendar_name: string;
  calendar_color?: string | null;
};

export const eventService = {
  list(params?: { start?: string; end?: string }) {
    return api.get<CalendarEvent[]>('/api/events/', { params });
  },
  create(payload: {
    title: string;
    description?: string;
    start: string;
    end: string;
    is_all_day?: boolean;
    blocks_availability?: boolean;
    calendar_id?: number;
  }) {
    return api.post<CalendarEvent>('/api/events/', payload);
  },
  update(id: number, payload: {
    title?: string;
    description?: string;
    start?: string;
    end?: string;
    is_all_day?: boolean;
    blocks_availability?: boolean;
    calendar_id?: number;
  }) {
    return api.patch<CalendarEvent>(`/api/events/${id}/`, payload);
  },
};
