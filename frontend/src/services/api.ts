import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// ------------------------------------------------------------------ //
//  Groups
// ------------------------------------------------------------------ //
export const groupApi = {
  list: () => api.get('/api/groups/'),
  create: (payload: { name: string; reassignment_rule?: string; fairness_algorithm?: string }) =>
    api.post('/api/groups/', payload),
  get: (id: string) => api.get(`/api/groups/${id}/`),
  members: (id: string) => api.get(`/api/groups/${id}/members/`),
  invite: (id: string, payload: { email: string; role: string }) =>
    api.post(`/api/groups/${id}/invite/`, payload),
  settings: (id: string, payload: object) => api.patch(`/api/groups/${id}/settings/`, payload),
  leaderboard: (id: string) => api.get(`/api/groups/${id}/leaderboard/`),
  stats: (id: string) => api.get(`/api/groups/${id}/stats/`),
  proposals: (id: string) => api.get(`/api/groups/${id}/proposals/`),
  createProposal: (id: string, payload: { task_template_id: number; reason?: string }) =>
    api.post(`/api/groups/${id}/proposals/`, payload),
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
  complete: (id: number, payload?: { photo_proof_url?: string }) =>
    api.post(`/api/tasks/${id}/complete/`, payload ?? {}),
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
};

// ------------------------------------------------------------------ //
//  Marketplace
// ------------------------------------------------------------------ //
export const marketplaceApi = {
  groupListings: (groupId: string) => api.get(`/api/groups/${groupId}/marketplace/`),
  claim: (listingId: number) => api.post(`/api/marketplace/${listingId}/claim/`),
};

// ------------------------------------------------------------------ //
//  Notifications
// ------------------------------------------------------------------ //
export const notificationApi = {
  list: () => api.get('/api/notifications/'),
  history: (params?: { limit?: number; offset?: number }) =>
    api.get('/api/notifications/history/', { params }),
  markRead: (id: number) => api.post(`/api/notifications/${id}/read/`),
  dismiss: (id: number) => api.post(`/api/notifications/${id}/dismiss/`),
};

// ------------------------------------------------------------------ //
//  Stats & badges
// ------------------------------------------------------------------ //
export const statsApi = {
  myStats: () => api.get('/api/users/me/stats/'),
  myBadges: () => api.get('/api/users/me/badges/'),
};
