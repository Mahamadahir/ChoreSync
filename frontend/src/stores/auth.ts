import { defineStore } from 'pinia';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    isAuthenticated: false,
    hasBootstrapped: false,
    userId: null as string | null,
    householdIds: [] as string[],
    username: null as string | null,
    email: null as string | null,
    firstName: null as string | null,
    lastName: null as string | null,
    avatarUrl: null as string | null,
  }),
  getters: {
    displayName(state): string {
      if (state.firstName) return state.firstName;
      return state.username ?? '';
    },
    fullName(state): string {
      const parts = [state.firstName, state.lastName].filter(Boolean);
      return parts.join(' ') || state.username || '';
    },
    initials(state): string {
      if (state.firstName && state.lastName) {
        return (state.firstName[0] + state.lastName[0]).toUpperCase();
      }
      if (state.firstName) return state.firstName.slice(0, 2).toUpperCase();
      const name = state.username || state.email || 'U';
      return name.slice(0, 2).toUpperCase();
    },
  },
  actions: {
    setAuthenticated(
      value: boolean,
      userId?: string,
      householdIds?: string[],
      username?: string,
      email?: string,
      firstName?: string,
      lastName?: string,
    ) {
      this.isAuthenticated = value;
      this.hasBootstrapped = value;
      this.userId = userId ?? null;
      this.householdIds = householdIds ?? [];
      this.username = username ?? null;
      this.email = email ?? null;
      this.firstName = firstName ?? null;
      this.lastName = lastName ?? null;
    },
    setName(firstName: string, lastName: string) {
      this.firstName = firstName || null;
      this.lastName = lastName || null;
    },
    setAvatarUrl(url: string | null) {
      this.avatarUrl = url;
    },
    setHouseholdIds(ids: string[]) {
      this.householdIds = ids;
    },
    markBootstrapped() {
      this.hasBootstrapped = true;
    },
    clear() {
      this.isAuthenticated = false;
      this.hasBootstrapped = false;
      this.userId = null;
      this.householdIds = [];
      this.username = null;
      this.email = null;
      this.firstName = null;
      this.lastName = null;
      this.avatarUrl = null;
    },
  },
});
