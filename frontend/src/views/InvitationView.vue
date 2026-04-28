<template>
  <div class="cs-page" style="max-width:480px;margin:0 auto">

    <!-- Loading -->
    <div v-if="loading" style="display:flex;justify-content:center;padding:64px 0">
      <q-spinner color="primary" size="36px" />
    </div>

    <!-- Error / not found -->
    <div v-else-if="error" class="cs-card" style="text-align:center;padding:48px 24px">
      <span class="material-symbols-outlined" style="font-size:48px;color:var(--cs-muted)">error_outline</span>
      <div style="font-size:18px;font-weight:700;margin:12px 0 8px">{{ error }}</div>
      <button class="cs-btn-secondary" @click="$router.push({ name: 'groups' })">Back to Groups</button>
    </div>

    <!-- Already resolved -->
    <div v-else-if="resolved" class="cs-card" style="text-align:center;padding:48px 24px">
      <span class="material-symbols-outlined" style="font-size:48px;color:var(--cs-success,#4caf50)">check_circle</span>
      <div style="font-size:18px;font-weight:700;margin:12px 0 8px">{{ resolvedMessage }}</div>
      <button v-if="joinedGroupId" class="cs-btn-primary" style="margin-top:4px" @click="$router.push({ name: 'group-detail', params: { id: joinedGroupId } })">
        <span class="material-symbols-outlined">arrow_forward</span>
        Go to group
      </button>
      <button v-else class="cs-btn-secondary" style="margin-top:4px" @click="$router.push({ name: 'groups' })">Back to Groups</button>
    </div>

    <!-- Invitation card -->
    <div v-else-if="invitation" class="cs-card" style="padding:32px 24px">
      <div style="text-align:center;margin-bottom:28px">
        <div style="width:72px;height:72px;border-radius:36px;background:var(--cs-primary-container);display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px">
          <span class="material-symbols-outlined" style="font-size:36px;color:var(--cs-primary)">group_add</span>
        </div>
        <div style="font-size:22px;font-weight:800;color:var(--cs-on-surface);margin-bottom:6px">You've been invited!</div>
        <div style="font-size:14px;color:var(--cs-muted)">
          <strong>{{ invitation.invited_by }}</strong> invited you to join
        </div>
      </div>

      <div style="background:var(--cs-surface-low);border-radius:var(--cs-radius-lg);padding:20px;margin-bottom:24px">
        <div style="font-size:20px;font-weight:700;color:var(--cs-on-surface);margin-bottom:8px">{{ invitation.group_name }}</div>
        <div style="display:flex;gap:8px;align-items:center">
          <span class="cs-chip" style="background:var(--cs-primary-container);color:var(--cs-primary)">
            {{ invitation.role }}
          </span>
          <span style="font-size:12px;color:var(--cs-muted)">{{ timeAgo(invitation.created_at) }}</span>
        </div>
      </div>

      <div v-if="actionError" class="cs-error-msg" style="margin-bottom:16px">{{ actionError }}</div>

      <div style="display:flex;gap:12px">
        <button
          class="cs-btn-secondary"
          style="flex:1"
          :disabled="acting"
          @click="respond('decline')"
        >
          <span class="material-symbols-outlined">close</span>
          Decline
        </button>
        <button
          class="cs-btn-primary"
          style="flex:1"
          :disabled="acting"
          @click="respond('accept')"
        >
          <q-spinner v-if="acting" size="16px" color="white" />
          <span v-else class="material-symbols-outlined">check</span>
          Accept
        </button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../services/api';

const route = useRoute();
const router = useRouter();

const invitationId = route.params.id as string;

interface Invitation {
  id: number;
  group_id: string;
  group_name: string;
  invited_by: string | null;
  role: string;
  created_at: string;
}

const loading      = ref(true);
const error        = ref('');
const acting       = ref(false);
const actionError  = ref('');
const resolved     = ref(false);
const resolvedMessage = ref('');
const joinedGroupId   = ref<string | null>(null);
const invitation   = ref<Invitation | null>(null);

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

onMounted(async () => {
  try {
    const res = await api.get('/api/invitations/');
    const match = res.data.find((inv: Invitation) => String(inv.id) === String(invitationId));
    if (!match) {
      error.value = 'This invitation has already been resolved or doesn\'t exist.';
    } else {
      invitation.value = match;
    }
  } catch {
    error.value = 'Could not load invitation.';
  } finally {
    loading.value = false;
  }
});

async function respond(action: 'accept' | 'decline') {
  acting.value = true;
  actionError.value = '';
  try {
    const res = await api.post(`/api/invitations/${invitationId}/${action}/`);
    resolvedMessage.value = res.data.detail;
    joinedGroupId.value = action === 'accept' ? (res.data.group_id ?? null) : null;
    resolved.value = true;
  } catch (e: any) {
    actionError.value = e?.response?.data?.detail ?? 'Something went wrong. Please try again.';
  } finally {
    acting.value = false;
  }
}
</script>
