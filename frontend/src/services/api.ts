import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Attach the Django CSRF token on every state-mutating request.
// Django sets the `csrftoken` cookie on login (via rotate_token); we read it
// here and forward it as X-CSRFToken so SessionAuthentication.enforce_csrf()
// passes for cookie-authenticated Vue web requests.
function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

api.interceptors.request.use((config) => {
  if (['post', 'put', 'patch', 'delete'].includes((config.method ?? '').toLowerCase())) {
    const token = getCsrfToken();
    if (token) {
      config.headers['X-CSRFToken'] = token;
    }
  }
  return config;
});

const AUTH_ENDPOINTS = ['/api/auth/login/', '/api/auth/change-password/'];

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error?.config?.url ?? '';
    const isAuthEndpoint = AUTH_ENDPOINTS.some((e) => url.includes(e));
    if (error?.response?.status === 401 && !isAuthEndpoint) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ------------------------------------------------------------------ //
//  Groups
// ------------------------------------------------------------------ //
export const groupApi = {
  list: () => api.get('/api/groups/'),
  create: (payload: { name: string; reassignment_rule?: string; group_type?: string }) =>
    api.post('/api/groups/', payload),
  get: (id: string) => api.get(`/api/groups/${id}/`),
  members: (id: string) => api.get(`/api/groups/${id}/members/`),
  invite: (id: string, payload: { email: string; role: string }) =>
    api.post(`/api/groups/${id}/invite/`, payload),
  settings: (id: string, payload: object) => api.patch(`/api/groups/${id}/settings/`, payload),
  leaderboard: (id: string) => api.get(`/api/groups/${id}/leaderboard/`),
  stats: (id: string) => api.get(`/api/groups/${id}/stats/`),
  assignmentMatrix: (id: string) => api.get(`/api/groups/${id}/assignment-matrix/`),
  proposals: (id: string) => api.get(`/api/groups/${id}/proposals/`),
  createProposal: (id: string, payload: { payload: Record<string, unknown>; reason?: string; vote_mode?: boolean }) =>
    api.post(`/api/groups/${id}/proposals/`, payload),
  approveProposal: (id: number, body: { edited_payload?: Record<string, unknown> | null; approval_note?: string }) =>
    api.post(`/api/proposals/${id}/approve/`, body),
  rejectProposal: (id: number, body: { note?: string }) =>
    api.post(`/api/proposals/${id}/reject/`, body),
  voteOnProposal: (id: number, choice: string) =>
    api.post(`/api/proposals/${id}/vote/`, { choice }),

};

// ------------------------------------------------------------------ //
//  Tasks
// ------------------------------------------------------------------ //
export const taskApi = {
  myTasks: (params?: { status?: string; group_id?: string }) =>
    api.get('/api/users/me/tasks/', { params }),
  groupTasks: (groupId: string, params?: { status?: string }) =>
    api.get(`/api/groups/${groupId}/tasks/`, { params }),
  get: (id: number) => api.get(`/api/tasks/${id}/`),
  complete: (id: number, completed = true, payload?: { photo_proof_url?: string }) =>
    api.post(`/api/tasks/${id}/complete/`, { completed, ...payload }),
  snooze: (id: number, payload: { snooze_until: string }) =>
    api.post(`/api/tasks/${id}/snooze/`, payload),
  createSwap: (id: number, payload: { to_user_id?: string; reason?: string }) =>
    api.post(`/api/tasks/${id}/swap/`, payload),
  respondSwap: (swapId: number, accept: boolean) =>
    api.post(`/api/task-swaps/${swapId}/respond/`, { accept }),
  emergencyReassign: (id: number, payload: { reason?: string }) =>
    api.post(`/api/tasks/${id}/emergency-reassign/`, payload),
  acceptEmergency: (id: number) => api.post(`/api/tasks/${id}/accept-emergency/`),
  listMarketplace: (id: number, payload: { bonus_points?: number }) =>
    api.post(`/api/tasks/${id}/list-marketplace/`, payload),
  pendingSwaps: () => api.get('/api/users/me/pending-swaps/'),
  acceptSuggestion: (id: number) => api.post(`/api/tasks/${id}/accept-suggestion/`),
  declineSuggestion: (id: number) => api.post(`/api/tasks/${id}/decline-suggestion/`),
  createPersonal: (payload: {
    name: string;
    deadline?: string;
    estimated_mins?: number;
    category?: string;
    details?: string;
  }) => api.post('/api/tasks/personal/', payload),
  deletePersonal: (id: number) => api.delete(`/api/tasks/${id}/delete/`),
};

// ------------------------------------------------------------------ //
//  Marketplace
// ------------------------------------------------------------------ //
export const marketplaceApi = {
  groupListings: (groupId: string) => api.get(`/api/groups/${groupId}/marketplace/`),
  claim: (listingId: number) => api.post(`/api/marketplace/${listingId}/claim/`),
  cancel: (listingId: number) => api.delete(`/api/marketplace/${listingId}/cancel/`),
};

// ------------------------------------------------------------------ //
//  Notifications
// ------------------------------------------------------------------ //
export const notificationApi = {
  list: () => api.get('/api/notifications/'),
  history: (params?: { limit?: number; offset?: number }) =>
    api.get('/api/notifications/history/', { params }),
  markRead: (id: number) => api.post(`/api/notifications/${id}/read/`),
  markAllRead: () => api.post('/api/notifications/read-all/'),
  dismiss: (id: number) => api.post(`/api/notifications/${id}/dismiss/`),
  getPrefs: () => api.get('/api/users/me/notification-preferences/'),
  patchPrefs: (payload: object) => api.patch('/api/users/me/notification-preferences/', payload),
};

// ------------------------------------------------------------------ //
//  Stats & badges
// ------------------------------------------------------------------ //
export const statsApi = {
  myStats: () => api.get('/api/users/me/stats/'),
  myBadges: () => api.get('/api/users/me/badges/'),
};

// ------------------------------------------------------------------ //
//  Messages
// ------------------------------------------------------------------ //
export const messageApi = {
  list: (groupId: string, params?: { limit?: number; before?: number }) =>
    api.get(`/api/groups/${groupId}/messages/`, { params }),
  markRead: (groupId: string, messageIds: number[]) =>
    api.post(`/api/groups/${groupId}/messages/read/`, { message_ids: messageIds }),
};

// ------------------------------------------------------------------ //
//  Chatbot / AI Assistant
// ------------------------------------------------------------------ //
export const chatbotApi = {
  listSessions: () =>
    api.get<{ id: number; preview: string; message_count: number; last_active: string }[]>('/api/assistant/sessions/'),
  loadSession: (sessionId?: number | null) =>
    api.get<{ session_id: number | null; messages: { role: 'user' | 'bot'; content: string }[] }>(
      '/api/assistant/',
      sessionId ? { params: { session_id: sessionId } } : undefined,
    ),
  send: (message: string, sessionId?: number | null) =>
    api.post('/api/assistant/', { message, ...(sessionId ? { session_id: sessionId } : {}) }),
  clearSession: (sessionId: number) =>
    api.delete('/api/assistant/', { data: { session_id: sessionId } }),
};
