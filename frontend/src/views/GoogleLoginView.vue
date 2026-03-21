<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 420px; width: 100%;">
      <div class="text-h5 q-mb-sm">Continue with Google</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        Choose your Google account to sign in. We’ll use your verified Google email to create or log in to your account.
      </div>
      <div class="q-mb-md">
        <div ref="googleBtn"></div>
      </div>
      <q-banner v-if="error" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { authService } from '../services/authService';
import { useAuthStore } from '../stores/auth';

const googleBtn = ref<HTMLElement | null>(null);
const error = ref('');
const router = useRouter();
const authStore = useAuthStore();
const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

function initGoogle() {
  const google = (window as any).google;
  if (!google || !google.accounts?.id) {
    error.value = 'Google Sign-In script not loaded.';
    return;
  }
  if (!googleClientId) {
    error.value = 'Google client ID missing. Check your .env.';
    return;
  }
  google.accounts.id.initialize({
    client_id: googleClientId,
    callback: handleCredential,
  });
  if (googleBtn.value) {
    google.accounts.id.renderButton(googleBtn.value, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      width: 320,
    });
  }
}

async function handleCredential(response: any) {
  error.value = '';
  if (!response?.credential) {
    error.value = 'No credential returned.';
    return;
  }
  try {
    await authService.loginWithGoogle(response.credential);
    authStore.setAuthenticated(true);
    router.push({ name: 'home' });
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Google Sign-In failed.';
  }
}

onMounted(() => {
  initGoogle();
});
</script>
