<template>
  <div class="cs-auth-wrap">
    <div class="cs-auth-card">
      <div class="cs-auth-logo">
        <span class="material-symbols-outlined">home_work</span>
        <span class="cs-auth-logo-text">ChoreSync</span>
      </div>

      <div class="cs-auth-title">Reset your password</div>
      <div class="cs-auth-sub" style="margin-bottom:24px">Enter your email and we'll send a reset link.</div>

      <form @submit.prevent="handleSubmit">
        <div class="cs-form-field">
          <label class="cs-form-label">Email</label>
          <input
            v-model="email"
            type="email"
            class="cs-form-input"
            placeholder="you@example.com"
            :disabled="isSubmitting"
            required
            autocomplete="email"
          />
        </div>
        <button
          type="submit"
          class="cs-btn-primary"
          style="width:100%;justify-content:center;padding:14px;border-radius:50px;margin-top:8px;font-size:15px"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Sending…' : 'Send reset link' }}
        </button>
      </form>

      <div
        v-if="message"
        style="margin-top:16px;padding:12px 14px;background:var(--cs-primary-container);color:var(--cs-primary);border-radius:var(--cs-radius-md);font-size:13px"
      >
        {{ message }}
      </div>
      <div
        v-if="errorMsg"
        style="margin-top:16px;padding:12px 14px;background:var(--cs-error-container);color:var(--cs-error);border-radius:var(--cs-radius-md);font-size:13px"
      >
        {{ errorMsg }}
      </div>

      <div style="text-align:center;margin-top:24px;font-size:13px;color:var(--cs-muted)">
        <router-link to="/login" style="color:var(--cs-primary);text-decoration:none;font-weight:600">Back to sign in</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { authService } from '../services/authService';

const email = ref('');
const message = ref('');
const errorMsg = ref('');
const isSubmitting = ref(false);

async function handleSubmit() {
  message.value = '';
  errorMsg.value = '';
  isSubmitting.value = true;
  try {
    await authService.forgotPassword(email.value);
    message.value = 'If this account exists, a reset link was sent.';
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || 'Unable to process request.';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
