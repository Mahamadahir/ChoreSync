<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 480px; width: 100%;">
      <div class="text-h5 q-mb-sm">Forgot Password</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        Enter your email for a reset link (active accounts only).
      </div>
      <q-form class="q-gutter-md" @submit="handleSubmit">
        <q-input
          v-model="email"
          label="Email"
          type="email"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-btn
          type="submit"
          label="Send reset link"
          color="primary"
          class="full-width"
          :loading="isSubmitting"
        />
      </q-form>
      <q-banner v-if="message" class="q-mt-md" type="positive" dense>{{ message }}</q-banner>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { authService } from '../services/authService';

const email = ref('');
const message = ref('');
const error = ref('');
const isSubmitting = ref(false);

async function handleSubmit() {
  message.value = '';
  error.value = '';
  isSubmitting.value = true;
  try {
    await authService.forgotPassword(email.value);
    message.value = 'If this account exists, a reset link was sent.';
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to process request.';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
