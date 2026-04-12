import { api } from './api';

export const chatbotService = {
  send: (message: string, session_id: string | null) =>
    api.post('/api/assistant/', { message, session_id }),

  loadSession: (session_id: string) =>
    api.get('/api/assistant/', { params: { session_id } }),

  clearSession: (session_id: string) =>
    api.delete('/api/assistant/', { data: { session_id } }),
};
