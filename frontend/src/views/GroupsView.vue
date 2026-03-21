<template>
  <q-page padding>
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5 text-weight-bold">My Groups</div>
      <q-btn color="primary" icon="add" label="Create Group" @click="showCreate = true" />
    </div>

    <!-- Error banner -->
    <q-banner v-if="error" class="bg-negative text-white q-mb-md" rounded>
      {{ error }}
    </q-banner>

    <!-- Loading -->
    <div v-if="loading" class="row justify-center q-pa-xl">
      <q-spinner size="40px" color="primary" />
    </div>

    <!-- Empty state -->
    <div v-else-if="groups.length === 0" class="text-center q-pa-xl text-grey-6">
      <q-icon name="group" size="64px" />
      <div class="text-h6 q-mt-md">No groups yet</div>
      <div class="q-mt-sm">Create a group or ask someone to invite you.</div>
    </div>

    <!-- Groups list -->
    <div v-else class="row q-gutter-md">
      <q-card
        v-for="g in groups"
        :key="g.id"
        class="group-card cursor-pointer"
        flat
        bordered
        @click="$router.push({ name: 'group-detail', params: { id: g.id } })"
      >
        <q-card-section>
          <div class="row items-center justify-between">
            <div class="text-h6">{{ g.name }}</div>
            <q-badge :color="g.role === 'moderator' ? 'primary' : 'grey-6'" :label="g.role" />
          </div>
          <div class="text-caption text-grey-6 q-mt-xs">Code: {{ g.group_code }}</div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-chip
            icon="auto_fix_high"
            :label="g.fairness_algorithm"
            size="sm"
            outline
            color="primary"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat color="primary" label="Open" icon-right="arrow_forward"
            @click.stop="$router.push({ name: 'group-detail', params: { id: g.id } })" />
        </q-card-actions>
      </q-card>
    </div>

    <!-- Create group dialog -->
    <q-dialog v-model="showCreate" persistent>
      <q-card style="min-width: 380px">
        <q-card-section>
          <div class="text-h6">Create a group</div>
        </q-card-section>

        <q-card-section class="q-gutter-md">
          <q-input
            v-model="form.name"
            label="Group name"
            outlined
            autofocus
            :error="!!formError"
            :error-message="formError"
          />
          <q-select
            v-model="form.fairness_algorithm"
            :options="fairnessOptions"
            label="Fairness algorithm"
            outlined
            emit-value
            map-options
          />
          <q-select
            v-model="form.reassignment_rule"
            :options="reassignOptions"
            label="Reassignment rule"
            outlined
            emit-value
            map-options
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn
            color="primary"
            label="Create"
            :loading="creating"
            @click="createGroup"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { groupApi } from '../services/api';

type Group = {
  id: string;
  name: string;
  group_code: string;
  role: string;
  fairness_algorithm: string;
};

const groups = ref<Group[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const showCreate = ref(false);
const creating = ref(false);
const formError = ref('');

const form = ref({
  name: '',
  fairness_algorithm: 'round_robin',
  reassignment_rule: 'auto',
});

const fairnessOptions = [
  { label: 'Round Robin', value: 'round_robin' },
  { label: 'Least Recently Done', value: 'least_recently_done' },
  { label: 'Weighted', value: 'weighted' },
  { label: 'Time Based', value: 'time_based' },
];

const reassignOptions = [
  { label: 'Auto', value: 'auto' },
  { label: 'Manual', value: 'manual' },
];

async function loadGroups() {
  loading.value = true;
  error.value = null;
  try {
    const res = await groupApi.list();
    groups.value = res.data;
  } catch {
    error.value = 'Failed to load groups.';
  } finally {
    loading.value = false;
  }
}

async function createGroup() {
  if (!form.value.name.trim()) {
    formError.value = 'Group name is required.';
    return;
  }
  formError.value = '';
  creating.value = true;
  try {
    await groupApi.create(form.value);
    showCreate.value = false;
    form.value = { name: '', fairness_algorithm: 'round_robin', reassignment_rule: 'auto' };
    await loadGroups();
  } catch (e: any) {
    formError.value = e?.response?.data?.detail ?? 'Failed to create group.';
  } finally {
    creating.value = false;
  }
}

onMounted(loadGroups);
</script>

<style scoped>
.group-card {
  width: 280px;
  transition: box-shadow 0.2s;
}
.group-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}
</style>
