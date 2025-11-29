<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 480px; width: 100%;">
      <div class="text-h5 q-mb-sm">Sign Up for ChoreSync</div>
      <div class="text-body2 text-grey-7 q-mb-md">{{ helperText }}</div>
      <q-form @submit="handleSignup" class="q-gutter-md">
        <q-input
          v-model="username"
          label="Username"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-input
          v-model="email"
          label="Email"
          type="email"
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
        <q-input
          v-model="confirmPassword"
          label="Confirm Password"
          type="password"
          outlined
          dense
          :disable="isSubmitting"
          required
        />
        <q-btn
          type="submit"
          label="Sign Up"
          color="primary"
          class="full-width"
          :loading="isSubmitting"
        />
      </q-form>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { authService } from '../services/authService';

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const error = ref('');
const helperText = ref('You will be asked to check your inbox after signup.');
const isSubmitting = ref(false);
const router = useRouter();

async function handleSignup() {
  error.value = '';
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.';
    return;
  }
  isSubmitting.value = true;
  try {
    await authService.signup({
      username: username.value,
      email: email.value,
      password: password.value,
    });
    router.push({ name: 'check-email', query: { email: email.value } });
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Signup failed. Please try again.';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
