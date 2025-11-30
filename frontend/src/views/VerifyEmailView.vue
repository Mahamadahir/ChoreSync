<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 520px; width: 100%;">
      <div class="text-h5 q-mb-xs">Verify your email</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        We're confirming your link. If something went wrong, you can resend or update your email below.
      </div>

      <div v-if="loading" class="row items-center q-gutter-sm q-mb-md">
        <q-spinner color="primary" size="24px" />
        <span class="text-body2 text-grey-7">Please wait…</span>
      </div>

      <q-banner v-if="message" class="q-mb-md" type="positive" dense>
        {{ message }}
        <router-link class="text-weight-bold q-ml-xs" to="/login">Log in</router-link>
      </q-banner>
      <q-banner v-if="error" class="q-mb-md" type="warning" dense>
        {{ error }}
        <router-link
          class="text-weight-bold q-ml-xs"
          :to="{ name: 'check-email', query: { email: email } }"
        >
          Resend link
        </router-link>
      </q-banner>

      <q-separator spaced />

      <div class="text-subtitle1 q-mb-xs">Update your email</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        If you typed the wrong address, update it and we'll send a fresh verification link.
      </div>

      <q-form @submit="handleUpdateEmail" class="q-gutter-md">
        <q-input v-model="newEmail" type="email" label="New email" outlined dense required />
        <q-btn
          type="submit"
          label="Update email & resend link"
          color="primary"
          class="full-width"
          :loading="updating"
        />
      </q-form>

      <q-banner v-if="updateMessage" class="q-mt-md" type="positive" dense>{{ updateMessage }}</q-banner>
      <q-banner v-if="updateError" class="q-mt-md" type="warning" dense>{{ updateError }}</q-banner>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authService } from '../services/authService';

const route = useRoute();
const router = useRouter();
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
    await authService.verifyEmail(token);
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
    updateMessage.value = 'Email updated. Check your inbox for a new verification link.';
    email.value = response.data.email;
  } catch (err: any) {
    updateError.value = err?.response?.data?.detail || 'Unable to update email.';
  } finally {
    updating.value = false;
  }
}
</script>
