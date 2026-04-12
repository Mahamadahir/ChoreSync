import { api } from './api';

export const taskService = {
  myTasks: (params?: { status?: string; group_id?: string }) =>
    api.get('/api/users/me/tasks/', { params }),

  getTask: (id: number) =>
    api.get(`/api/tasks/${id}/`),

  complete: (id: number) =>
    api.post(`/api/tasks/${id}/complete/`, {}),

  snooze: (id: number, snooze_until: string) =>
    api.post(`/api/tasks/${id}/snooze/`, { snooze_until }),

  acceptSuggestion: (id: number) =>
    api.post(`/api/tasks/${id}/accept-suggestion/`),

  declineSuggestion: (id: number) =>
    api.post(`/api/tasks/${id}/decline-suggestion/`),

  emergencyReassign: (id: number, reason?: string) =>
    api.post(`/api/tasks/${id}/emergency-reassign/`, { reason }),

  acceptEmergency: (id: number) =>
    api.post(`/api/tasks/${id}/accept-emergency/`),

  createSwap: (id: number, payload: { to_user_id?: string; reason?: string }) =>
    api.post(`/api/tasks/${id}/swap/`, payload),

  respondSwap: (swapId: number, accept: boolean) =>
    api.post(`/api/task-swaps/${swapId}/respond/`, { accept }),

  listMarketplace: (id: number, bonus_points?: number) =>
    api.post(`/api/tasks/${id}/list-marketplace/`, { bonus_points }),

  // The backend accepts the file under the field name "photo" (not "photo_proof").
  // Callers must append the file with: formData.append('photo', { uri, name, type })
  uploadProof: (id: number, formData: FormData) =>
    api.post(`/api/tasks/${id}/upload-proof/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  pendingSwaps: () =>
    api.get('/api/users/me/pending-swaps/'),

  assignmentBreakdown: (id: number) =>
    api.get(`/api/tasks/${id}/assignment-breakdown/`),
};
