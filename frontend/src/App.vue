<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-toolbar-title>ChoreSync</q-toolbar-title>
        <q-btn v-if="authStore.isAuthenticated" flat dense to="/">Home</q-btn>
        <q-btn v-if="authStore.isAuthenticated" flat dense to="/calendar">Calendar</q-btn>
        <q-btn v-if="!authStore.isAuthenticated" flat dense to="/signup">Sign Up</q-btn>
        <q-btn v-if="!authStore.isAuthenticated" flat dense to="/login">Log In</q-btn>
        <q-btn v-if="authStore.isAuthenticated" flat dense to="/profile">Profile</q-btn>
        <q-space />
        <q-btn
          v-if="authStore.isAuthenticated"
          flat
          dense
          icon="logout"
          label="Log Out"
          @click="handleLogout"
        />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { authService } from './services/authService';
import { useAuthStore } from './stores/auth';

const authStore = useAuthStore();

async function handleLogout() {
  try {
    await authService.logout();
  } catch (err) {
    // ignore errors on logout
  } finally {
    authStore.clear();
    // redirect to login after logout without full reload
    window.history.pushState({}, '', '/login');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
}
</script>
