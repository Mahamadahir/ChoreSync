import { defineStore } from 'pinia';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    isAuthenticated: false,
    hasBootstrapped: false,
    userId: null as string | null,
    householdIds: [] as string[],
  }),
  actions: {
    setAuthenticated(value: boolean, userId?: string, householdIds?: string[]) {
      this.isAuthenticated = value;
      this.hasBootstrapped = value;
      this.userId = userId ?? null;
      this.householdIds = householdIds ?? [];
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
    },
  },
});
