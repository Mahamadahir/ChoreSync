<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center px-4">
    <div class="w-full max-w-md bg-white shadow-md rounded-xl p-8 space-y-4">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900">Reset Password</h1>
        <p class="text-sm text-gray-500 mt-1">Enter your new password below.</p>
      </div>
      <q-form class="space-y-3" @submit="handleReset">
        <q-input
          v-model="newPassword"
          label="New password"
          type="password"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-input
          v-model="confirmPassword"
          label="Confirm new password"
          type="password"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-btn
          class="full-width"
          type="submit"
          color="primary"
          :loading="isSubmitting"
          label="Reset password"
        />
      </q-form>
      <q-banner v-if="message" class="q-mt-md" type="positive" dense>{{ message }}</q-banner>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authService } from '../services/authService';

const route = useRoute();
const router = useRouter();
const newPassword = ref('');
const confirmPassword = ref('');
const isSubmitting = ref(false);
const message = ref('');
const error = ref('');
const token = ref('');

onMounted(() => {
  token.value = (route.query.token as string) || '';
  if (!token.value) {
    error.value = 'Reset token missing.';
  }
});

async function handleReset() {
  error.value = '';
  message.value = '';
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.';
    return;
  }
  if (!token.value) {
    error.value = 'Reset token missing.';
    return;
  }
  isSubmitting.value = true;
  try {
    await authService.resetPassword(token.value, newPassword.value, confirmPassword.value);
    message.value = 'Password reset successful. You can now log in.';
    setTimeout(() => router.push({ name: 'login' }), 1200);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to reset password.';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
