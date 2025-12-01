<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 420px; width: 100%;">
      <div class="text-h5 q-mb-sm">Continue with Microsoft</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        Sign in with your Microsoft account. We'll use your verified email to create or log in to your account.
      </div>
      <q-btn
        color="primary"
        unelevated
        class="full-width q-mb-md"
        :loading="loading"
        @click="startLogin"
        label="Sign in with Microsoft"
      />
      <q-banner v-if="error" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { authService } from '../services/authService';
import { useAuthStore } from '../stores/auth';

const router = useRouter();
const authStore = useAuthStore();
const loading = ref(false);
const error = ref('');
const clientId = import.meta.env.VITE_MSAL_CLIENT_ID;
const authority = import.meta.env.VITE_MSAL_AUTHORITY || 'https://login.microsoftonline.com/common';

async function startLogin() {
  error.value = '';
  if (!(window as any).msal) {
    error.value = 'Microsoft auth script not loaded.';
    return;
  }
  if (!clientId) {
    error.value = 'Microsoft client ID missing. Check your .env.';
    return;
  }
  loading.value = true;
  try {
    const msalInstance = new (window as any).msal.PublicClientApplication({
      auth: { clientId, authority },
      cache: { cacheLocation: 'sessionStorage' },
    });
    const resp = await msalInstance.loginPopup({
      redirectUri: window.location.origin + '/login/microsoft',
      scopes: ['openid', 'profile', 'email'],
    });
    const idToken = resp.idToken;
    await authService.loginWithMicrosoft(idToken);
    authStore.setAuthenticated(true);
    authStore.markBootstrapped();
    router.push({ name: 'home' });
  } catch (err: any) {
    error.value = err?.message || 'Microsoft Sign-In failed.';
  } finally {
    loading.value = false;
  }
}
</script>
