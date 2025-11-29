<template>
  <div class="container py-5">
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow-sm">
          <div class="card-body">
            <h1 class="h4 mb-3">Verifying email…</h1>
            <div v-if="loading" class="text-muted">Please wait…</div>
            <div v-if="message" class="alert alert-success">
              {{ message }} <router-link to="/login">Log in</router-link>
            </div>
            <div v-if="error" class="alert alert-danger">
              {{ error }}
              <router-link :to="{ name: 'check-email', query: { email: email } }">Resend link</router-link>
            </div>
            <div class="mt-4">
              <h2 class="h6 mb-2">Update your email</h2>
              <p class="text-muted small">If you entered the wrong email, update it and we will send a new link.</p>
              <form class="d-grid gap-3" @submit.prevent="handleUpdateEmail">
                <div>
                  <label class="form-label" for="newEmail">New email</label>
                  <input
                    id="newEmail"
                    type="email"
                    class="form-control"
                    v-model="newEmail"
                    required
                  />
                </div>
                <button class="btn btn-secondary" type="submit" :disabled="updating">
                  {{ updating ? 'Updating…' : 'Update email & resend link' }}
                </button>
              </form>
              <div v-if="updateMessage" class="alert alert-success mt-3">{{ updateMessage }}</div>
              <div v-if="updateError" class="alert alert-danger mt-3">{{ updateError }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authService } from '../services/authService';
import { useAuthStore } from '../stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const message = ref('Submitting verification token...');
const error = ref('');
const loading = ref(true);
const email = ref<string | undefined>(route.query.email as string | undefined);
const newEmail = ref('');
const updateMessage = ref('');
const updateError = ref('');
const updating = ref(false);

async function verify() {
  const token = (route.query.token as string) || '';
  if (!token) {
    error.value = 'Missing verification token.';
    message.value = '';
    loading.value = false;
    return;
  }
  try {
    const response = await authService.verifyEmail(token);
    authStore.setUser(response.data);
    message.value = 'Email verified. You can now log in.';
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Verification failed.';
    message.value = '';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  verify().then(() => {
    // optional: redirect after a delay
  });
});

async function handleUpdateEmail() {
  const token = (route.query.token as string) || '';
  if (!token) {
    updateError.value = 'Missing verification token.';
    return;
  }
  updateError.value = '';
  updateMessage.value = '';
  updating.value = true;
  try {
    const response = await authService.updateEmail(token, newEmail.value);
    authStore.setUser(response.data);
    updateMessage.value = 'Email updated. Check your inbox for a new verification link.';
    email.value = response.data.email;
  } catch (err: any) {
    updateError.value = err?.response?.data?.detail || 'Unable to update email.';
  } finally {
    updating.value = false;
  }
}
</script>
