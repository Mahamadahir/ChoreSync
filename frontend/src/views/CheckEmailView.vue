<template>
  <div class="container py-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow-sm">
          <div class="card-body">
            <h1 class="h4 mb-3">Check your inbox</h1>
            <p v-if="email" class="text-muted">
              We sent a verification link to {{ email }} (if the account exists).
            </p>
            <p v-else class="text-muted">Enter your email to resend a verification link.</p>

            <form @submit.prevent="handleResend" class="d-grid gap-3">
              <div>
                <label class="form-label" for="email">Email</label>
                <input class="form-control" id="email" type="email" v-model="email" required />
              </div>
              <button class="btn btn-secondary" type="submit" :disabled="isSending || cooldown > 0">
                {{ cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend verification email' }}
              </button>
            </form>

            <div v-if="message" class="alert alert-success mt-3">{{ message }}</div>
            <div v-if="error" class="alert alert-danger mt-3">{{ error }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { authService } from '../services/authService';

const route = useRoute();
const email = ref<string>((route.query.email as string) || '');
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
