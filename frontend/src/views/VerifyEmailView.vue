<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 520px; width: 100%;">
      <div class="text-h5 q-mb-xs">Verify your email</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        We're confirming your link, please wait…
      </div>

      <div v-if="loading" class="row items-center q-gutter-sm q-mb-md">
        <q-spinner color="primary" size="24px" />
        <span class="text-body2 text-grey-7">Please wait…</span>
      </div>

      <q-banner v-if="message" class="q-mb-md" type="positive" dense>
        {{ message }} Redirecting you to login…
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
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authService } from '../services/authService';

const route = useRoute();
const router = useRouter();
const message = ref('');
const error = ref('');
const loading = ref(true);
const email = ref<string | undefined>(route.query.email as string | undefined);

async function verify() {
  const token = (route.query.token as string) || '';
  if (!token) {
    error.value = 'Missing verification token.';
    loading.value = false;
    return;
  }
  try {
    await authService.verifyEmail(token);
    message.value = 'Email verified.';
    setTimeout(() => router.push('/login'), 2000);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Verification failed.';
  } finally {
    loading.value = false;
  }
}

onMounted(() => verify());
</script>
