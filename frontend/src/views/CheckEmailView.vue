<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 520px; width: 100%;">
      <div class="text-h5 q-mb-xs">Check your inbox</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        <span v-if="email">We sent a verification link to {{ email }} (if the account exists).</span>
        <span v-else>Enter your email to resend a verification link.</span>
      </div>

      <q-form @submit="handleResend" class="q-gutter-md">
        <q-input v-model="email" type="email" label="Email" outlined dense required />
        <q-btn
          type="submit"
          :label="cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend verification email'"
          color="primary"
          class="full-width"
          :loading="isSending"
          :disable="cooldown > 0"
        />
      </q-form>

      <q-banner v-if="message" class="q-mt-md" type="positive" dense>{{ message }}</q-banner>
      <q-banner v-if="error" class="q-mt-md" type="warning" dense>{{ error }}</q-banner>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { authService } from '../services/authService';

const route = useRoute();
const initialEmail = (route.query.email as string) || '';
// Only prefill if it looks like an email; avoid showing usernames here.
const email = ref<string>(initialEmail.includes('@') ? initialEmail : '');
const message = ref('');
const error = ref('');
const isSending = ref(false);
const cooldown = ref(0);
let timer: number | null = null;

function startCooldown(seconds: number) {
  cooldown.value = seconds;
  if (timer) {
    clearInterval(timer);
  }
  timer = window.setInterval(() => {
    cooldown.value -= 1;
    if (cooldown.value <= 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  }, 1000);
}

async function sendEmail() {
  if (!email.value) return;
  isSending.value = true;
  error.value = '';
  message.value = '';
  try {
    await authService.resendVerification(email.value);
    message.value = 'If this account exists, a verification email has been sent.';
    startCooldown(60);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to send verification email.';
  } finally {
    isSending.value = false;
  }
}

async function handleResend() {
  if (cooldown.value > 0) return;
  await sendEmail();
}

onMounted(() => {
  // Send once on page load if email is present
  if (email.value) {
    sendEmail();
  }
});
</script>
