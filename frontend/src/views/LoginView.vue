<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 420px; width: 100%;">
      <div class="text-h5 q-mb-sm">Log In</div>
      <div class="text-body2 text-grey-7 q-mb-md">{{ helperText }}</div>
      <q-form @submit="handleLogin" class="q-gutter-md">
        <q-input
          v-model="identifier"
          label="Email or Username"
          type="text"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-input
          v-model="password"
          label="Password"
          type="password"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-btn
          type="submit"
          label="Log In"
          color="primary"
          class="full-width"
          :loading="isSubmitting"
        />
      </q-form>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>
        {{ error }}
      </q-banner>
      <div class="q-mt-md">
        <router-link class="text-primary" to="/forgot-password">Forgot your password?</router-link>
      </div>
      <q-separator class="q-my-md" />
      <q-btn
        outline
        color="secondary"
        icon="login"
        class="full-width"
        :disable="isSubmitting"
        @click="router.push({ name: 'login-google' })"
        label="Continue with Google"
      />
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { authService } from '../services/authService';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';

const identifier = ref('');
const password = ref('');
const error = ref('');
const helperText = ref('Login will authenticate against the Django API.');
const isSubmitting = ref(false);
const authStore = useAuthStore();
const router = useRouter();

async function handleLogin() {
  error.value = '';
  isSubmitting.value = true;
  try {
    const response = await authService.login({
      identifier: identifier.value,
      password: password.value,
    });
    authStore.setAuthenticated(true);
    helperText.value = 'Login successful.';
    // If backend returns inactive email, route to verify flow
    if (!response.data.email_verified) {
      router.push({ name: 'verify-email', query: { email: identifier.value } });
      return;
    }
    router.push({ name: 'home' });
  } catch (err: any) {
    const detail = err?.response?.data?.detail || 'Login failed. Please try again.';
    error.value = detail;
    // If backend indicates inactive account, route to check email
    if (err?.response?.status === 403) {
      router.push({ name: 'check-email', query: { email: identifier.value } });
    }
  } finally {
    isSubmitting.value = false;
  }
}
</script>
