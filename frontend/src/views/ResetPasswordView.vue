<template>
  <div class="q-pa-lg flex flex-center bg-grey-1" style="min-height: 100vh;">
    <q-card class="q-pa-lg" style="max-width: 480px; width: 100%;">
      <div class="text-h5 q-mb-sm">Reset Password</div>
      <div class="text-body2 text-grey-7 q-mb-md">Enter your new password below.</div>
      <q-form class="q-gutter-md" @submit="handleReset">
        <q-input
          v-model="newPassword"
          :type="showPassword ? 'text' : 'password'"
          label="New password"
          outlined
          dense
          :disable="isSubmitting"
          @update:model-value="computeStrength"
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
          label="Confirm new password"
          outlined
          dense
          :disable="isSubmitting"
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
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authService } from '../services/authService';
import { evaluatePassword } from '../utils/passwordStrength';

const route = useRoute();
const router = useRouter();
const newPassword = ref('');
const confirmPassword = ref('');
const isSubmitting = ref(false);
const message = ref('');
const error = ref('');
const token = ref('');
const showPassword = ref(false);
const showConfirm = ref(false);
const strengthValue = ref(0);
const strengthLabel = ref('Password strength');
const strengthColor = ref('grey');

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

function computeStrength(value: string) {
  const { score, label, color } = evaluatePassword(value || newPassword.value);
  strengthValue.value = score;
  strengthLabel.value = label;
  strengthColor.value = color;
}
</script>
