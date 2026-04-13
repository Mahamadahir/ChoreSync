<template>
  <div class="cs-auth-wrap">
    <div class="cs-auth-card">
      <!-- Logo -->
      <div class="cs-auth-logo">
        <span class="material-symbols-outlined">home_work</span>
        <span class="cs-auth-logo-text">ChoreSync</span>
      </div>

      <div class="cs-auth-title">Welcome back</div>
      <div class="cs-auth-sub">Sign in to your household account</div>

      <form @submit.prevent="handleLogin">
        <div class="cs-form-field">
          <label class="cs-form-label">Email or Username</label>
          <input
            v-model="identifier"
            type="text"
            class="cs-form-input"
            placeholder="you@example.com"
            :disabled="isSubmitting"
            required
            autocomplete="username"
          />
        </div>

        <div class="cs-form-field">
          <label class="cs-form-label">Password</label>
          <div class="cs-input-wrap">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="cs-form-input"
              placeholder="Your password"
              :disabled="isSubmitting"
              required
              autocomplete="current-password"
            />
            <button type="button" class="cs-input-icon-btn" @click="showPassword = !showPassword">
              <span class="material-symbols-outlined" style="font-size:18px">
                {{ showPassword ? 'visibility_off' : 'visibility' }}
              </span>
            </button>
          </div>
        </div>

        <div style="margin-bottom:16px">
          <router-link to="/forgot-password" style="font-size:13px;color:var(--cs-primary);text-decoration:none;font-weight:600">
            Forgot password?
          </router-link>
        </div>

        <button type="submit" class="cs-auth-submit-btn" :disabled="isSubmitting">
          {{ isSubmitting ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>

      <div v-if="error" class="cs-error-msg">{{ error }}</div>

      <div class="cs-auth-divider">or</div>

      <button class="cs-oauth-btn" :disabled="isSubmitting" @click="router.push({ name: 'login-google' })">
        <svg width="18" height="18" viewBox="0 0 48 48" fill="none">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        Continue with Google
      </button>

      <button class="cs-oauth-btn" :disabled="isSubmitting" @click="router.push({ name: 'login-microsoft' })">
        <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
          <rect x="0" y="0" width="10" height="10" fill="#f25022"/>
          <rect x="11" y="0" width="10" height="10" fill="#7fba00"/>
          <rect x="0" y="11" width="10" height="10" fill="#00a4ef"/>
          <rect x="11" y="11" width="10" height="10" fill="#ffb900"/>
        </svg>
        Continue with Microsoft
      </button>

      <div class="cs-auth-link-row">
        Don't have an account?
        <router-link to="/signup">Sign up free</router-link>
      </div>
    </div>
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
const isSubmitting = ref(false);
const showPassword = ref(false);
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
    authStore.markBootstrapped();
    if (!response.data.email_verified) {
      router.push({ name: 'verify-email', query: { email: identifier.value } });
      return;
    }
    router.push({ name: 'home' });
  } catch (err: any) {
    const detail = err?.response?.data?.detail || 'Login failed. Please try again.';
    error.value = detail;
    if (err?.response?.status === 403) {
      router.push({ name: 'check-email', query: { email: identifier.value } });
    }
  } finally {
    isSubmitting.value = false;
  }
}
</script>
