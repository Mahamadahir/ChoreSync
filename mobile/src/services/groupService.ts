import { api } from './api';

export const groupService = {
  list: () => api.get('/api/groups/'),

  get: (id: string) => api.get(`/api/groups/${id}/`),

  create: (payload: {
    name: string;
    reassignment_rule: string;
    group_type?: string;
  }) => api.post('/api/groups/', payload),

  joinByCode: (code: string) => api.post('/api/groups/join/', { code }),

  members: (id: string) => api.get(`/api/groups/${id}/members/`),

  invite: (id: string, email: string, role: string = 'member') =>
    api.post(`/api/groups/${id}/invite/`, { email, role }),

  leave: (id: string) => api.post(`/api/groups/${id}/leave/`),

  settings: (id: string, payload: object) =>
    api.patch(`/api/groups/${id}/settings/`, payload),

  leaderboard: (id: string) => api.get(`/api/groups/${id}/leaderboard/`),

  stats: (id: string) => api.get(`/api/groups/${id}/stats/`),

  tasks: (id: string) => api.get(`/api/groups/${id}/tasks/`),

  // Task templates
  templates: (id: string) => api.get(`/api/groups/${id}/task-templates/`),

  createTemplate: (groupId: string, payload: object) =>
    api.post(`/api/groups/${groupId}/task-templates/`, payload),

  updateTemplate: (templateId: number, payload: object) =>
    api.patch(`/api/task-templates/${templateId}/`, payload),

  deleteTemplate: (templateId: number) =>
    api.delete(`/api/task-templates/${templateId}/`),

  // Proposals
  proposals: (groupId: string) => api.get(`/api/groups/${groupId}/proposals/`),

  createProposal: (groupId: string, payload: { payload: Record<string, unknown>; reason?: string }) =>
    api.post(`/api/groups/${groupId}/proposals/`, payload),

  approveProposal: (proposalId: number, body: { edited_payload?: Record<string, unknown> | null; approval_note?: string }) =>
    api.post(`/api/proposals/${proposalId}/approve/`, body),

  rejectProposal: (proposalId: number, body: { note?: string }) =>
    api.post(`/api/proposals/${proposalId}/reject/`, body),

  // Marketplace
  marketplace: (groupId: string) => api.get(`/api/groups/${groupId}/marketplace/`),

  claimListing: (listingId: number) =>
    api.post(`/api/marketplace/${listingId}/claim/`),

  cancelListing: (listingId: number) =>
    api.delete(`/api/marketplace/${listingId}/cancel/`),

  // Messages
  messages: (groupId: string) => api.get(`/api/groups/${groupId}/messages/`),
  markRead: (groupId: string, messageIds: number[]) =>
    api.post(`/api/groups/${groupId}/messages/read/`, { message_ids: messageIds }),

  // Preferences
  myPreferences: (groupId: string) => api.get(`/api/groups/${groupId}/my-preferences/`),

  setPreference: (templateId: number, preference: 'prefer' | 'neutral' | 'avoid') =>
    api.put(`/api/task-templates/${templateId}/my-preference/`, { preference }),

  getTemplate: (templateId: number) =>
    api.get(`/api/task-templates/${templateId}/`),

  // Assignment matrix
  assignmentMatrix: (groupId: string) => api.get(`/api/groups/${groupId}/assignment-matrix/`),
};
