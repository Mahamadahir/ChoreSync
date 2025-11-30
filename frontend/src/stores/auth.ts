import { defineStore } from 'pinia';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    isAuthenticated: false,
    hasBootstrapped: false,
  }),
  actions: {
    setAuthenticated(value: boolean) {
      this.isAuthenticated = value;
      this.hasBootstrapped = value;
    },
    markBootstrapped() {
      this.hasBootstrapped = true;
    },
    clear() {
      this.isAuthenticated = false;
      this.hasBootstrapped = false;
    },
  },
});
