<template>
  <div class="cs-auth-wrap">
    <div class="cs-auth-card">
      <!-- Logo -->
      <div class="cs-auth-logo">
        <span class="material-symbols-outlined">home_work</span>
        <span class="cs-auth-logo-text">ChoreSync</span>
      </div>

      <div class="cs-auth-title">Create account</div>
      <div class="cs-auth-sub">Join your household — you'll verify your email after signup</div>

      <form @submit.prevent="handleSignup">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="cs-form-field">
            <label class="cs-form-label">First Name</label>
            <input
              v-model="firstName"
              type="text"
              class="cs-form-input"
              placeholder="Alex"
              :disabled="isSubmitting"
              required
              autocomplete="given-name"
            />
          </div>
          <div class="cs-form-field">
            <label class="cs-form-label">Last Name</label>
            <input
              v-model="lastName"
              type="text"
              class="cs-form-input"
              placeholder="Smith"
              :disabled="isSubmitting"
              required
              autocomplete="family-name"
            />
          </div>
        </div>

        <div class="cs-form-field">
          <label class="cs-form-label">Username</label>
          <input
            v-model="username"
            type="text"
            class="cs-form-input"
            placeholder="yourname"
            :disabled="isSubmitting"
            required
            autocomplete="username"
          />
        </div>

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

        <div class="cs-form-field">
          <label class="cs-form-label">Password</label>
          <div class="cs-input-wrap">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="cs-form-input"
              placeholder="Create a strong password"
              :disabled="isSubmitting"
              required
              autocomplete="new-password"
              @input="computeStrength"
            />
            <button type="button" class="cs-input-icon-btn" @click="showPassword = !showPassword">
              <span class="material-symbols-outlined" style="font-size:18px">
                {{ showPassword ? 'visibility_off' : 'visibility' }}
              </span>
            </button>
          </div>
          <div class="cs-strength-bar">
            <div
              class="cs-strength-fill"
              :style="`width:${strengthValue * 100}%;background:${strengthColorHex}`"
            />
          </div>
          <div class="cs-strength-label">{{ strengthLabel }}</div>
        </div>

        <div class="cs-form-field">
          <label class="cs-form-label">Confirm Password</label>
          <div class="cs-input-wrap">
            <input
              v-model="confirmPassword"
              :type="showConfirm ? 'text' : 'password'"
              class="cs-form-input"
              placeholder="Repeat your password"
              :disabled="isSubmitting"
              required
              autocomplete="new-password"
            />
            <button type="button" class="cs-input-icon-btn" @click="showConfirm = !showConfirm">
              <span class="material-symbols-outlined" style="font-size:18px">
                {{ showConfirm ? 'visibility_off' : 'visibility' }}
              </span>
            </button>
          </div>
        </div>

        <button type="submit" class="cs-auth-submit-btn" :disabled="isSubmitting">
          {{ isSubmitting ? 'Creating account…' : 'Create account' }}
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
        Sign up with Google
      </button>

      <button class="cs-oauth-btn" :disabled="isSubmitting" @click="router.push({ name: 'login-microsoft' })">
        <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
          <rect x="0" y="0" width="10" height="10" fill="#f25022"/>
          <rect x="11" y="0" width="10" height="10" fill="#7fba00"/>
          <rect x="0" y="11" width="10" height="10" fill="#00a4ef"/>
          <rect x="11" y="11" width="10" height="10" fill="#ffb900"/>
        </svg>
        Sign up with Microsoft
      </button>

      <div class="cs-auth-link-row">
        Already have an account?
        <router-link to="/login">Sign in</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { authService } from '../services/authService';
import { evaluatePassword } from '../utils/passwordStrength';

const firstName = ref('');
const lastName = ref('');
const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const error = ref('');
const isSubmitting = ref(false);
const timezone = ref('');
const router = useRouter();
const showPassword = ref(false);
const showConfirm = ref(false);
const strengthValue = ref(0);
const strengthLabel = ref('Enter a password');
const strengthColorHex = ref('#d5c6c0');

function detectBrowserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function computeStrength() {
  const { score, label, color } = evaluatePassword(password.value);
  strengthValue.value = score;
  strengthLabel.value = label;
  const colorMap: Record<string, string> = {
    negative: '#ba1a1a',
    warning: '#e8a020',
    positive: '#496640',
    grey: '#d5c6c0',
  };
  strengthColorHex.value = colorMap[color] ?? '#d5c6c0';
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
      first_name: firstName.value,
      last_name: lastName.value,
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
</script>
