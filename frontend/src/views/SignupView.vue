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
          :type="showPassword ? 'text' : 'password'"
          label="Password"
          outlined
          dense
          :disable="isSubmitting"
          @update:model-value="computeStrength"
          stack-label
          required
        >
          <template #append>
            <q-icon
              :name="showPassword ? 'visibility_off' : 'visibility'"
              class="cursor-pointer"
              @click="showPassword = !showPassword"
            />
          </template>
        </q-input>
        <q-input
          v-model="confirmPassword"
          :type="showConfirm ? 'text' : 'password'"
          label="Confirm Password"
          outlined
          dense
          :disable="isSubmitting"
          stack-label
          required
        >
          <template #append>
            <q-icon
              :name="showConfirm ? 'visibility_off' : 'visibility'"
              class="cursor-pointer"
              @click="showConfirm = !showConfirm"
            />
          </template>
        </q-input>
        <q-linear-progress
          :value="strengthValue"
          :color="strengthColor"
          track-color="grey-4"
          size="12px"
          class="q-mt-sm"
        />
        <div class="text-caption text-grey-7 q-mt-xs">{{ strengthLabel }}</div>
        <q-input
          v-model="timezone"
          label="Timezone (auto-detected; you can override)"
          outlined
          dense
          readonly
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
      <q-separator class="q-my-md" />
      <q-btn
        outline
        color="secondary"
        icon="login"
        class="full-width"
        :disable="isSubmitting"
        @click="router.push({ name: 'login-google' })"
        label="Sign up with Google"
      />
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { authService } from '../services/authService';

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const error = ref('');
const helperText = ref('You will be asked to check your inbox after signup.');
const isSubmitting = ref(false);
const timezone = ref('');
const router = useRouter();
const showPassword = ref(false);
const showConfirm = ref(false);
const strengthValue = ref(0);
const strengthLabel = ref('Password strength');
const strengthColor = ref('grey');

function detectBrowserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

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
      timezone: timezone.value,
    });
    router.push({ name: 'check-email', query: { email: email.value } });
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Signup failed. Please try again.';
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(() => {
  timezone.value = detectBrowserTimeZone();
});

function computeStrength(value: string) {
  const pwd = value || password.value;
  let score = 0;
  if (pwd.length >= 8) score += 0.25;
  if (/[A-Z]/.test(pwd)) score += 0.2;
  if (/[a-z]/.test(pwd)) score += 0.2;
  if (/[0-9]/.test(pwd)) score += 0.15;
  if (/[^A-Za-z0-9]/.test(pwd)) score += 0.2;
  if (pwd.length >= 12) score += 0.1;
  strengthValue.value = Math.min(score, 1);
  if (score >= 0.8) {
    strengthLabel.value = 'Strong';
    strengthColor.value = 'green';
  } else if (score >= 0.5) {
    strengthLabel.value = 'Medium';
    strengthColor.value = 'orange';
  } else {
    strengthLabel.value = 'Weak';
    strengthColor.value = 'red';
  }
}
</script>
