<template>
  <div class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 900px; width: 100%;">
      <div class="row items-center q-mb-md">
        <div class="col">
          <div class="text-h5">Choose Outlook Calendars</div>
          <div class="text-body2 text-grey-7">
            Select which Outlook calendars to import and whether they count toward availability.
          </div>
        </div>
        <div class="col-auto">
          <q-btn flat color="primary" label="Back to Home" @click="router.push({ name: 'home' })" />
        </div>
      </div>

      <div class="q-mb-md">
        <q-btn
          class="q-mr-sm"
          color="primary"
          outline
          dense
          label="Select All"
          @click="setAll(true)"
          :disable="loading || calendars.length === 0"
        />
        <q-btn
          color="primary"
          outline
          dense
          label="Clear All"
          @click="setAll(false)"
          :disable="loading || calendars.length === 0"
        />
      </div>

      <q-banner v-if="connectedMessage" dense class="q-mb-sm bg-positive text-white">
        {{ connectedMessage }}
      </q-banner>
      <q-banner v-if="errorMessage" dense class="q-mb-sm bg-negative text-white">
        {{ errorMessage }}
      </q-banner>
      <q-banner v-if="successMessage" dense class="q-mb-sm bg-positive text-white">
        {{ successMessage }}
      </q-banner>

      <div v-if="loading" class="q-pa-md flex flex-center">
        <q-spinner color="primary" size="32px" />
      </div>

      <div v-else>
        <div v-if="calendars.length === 0" class="text-body2 text-grey-7">
          No Outlook calendars found. Confirm access and try again.
        </div>
        <q-form v-else @submit.prevent="handleSave">
          <div class="column">
            <q-card
              v-for="cal in calendars"
              :key="cal.id"
              flat
              bordered
              class="q-pa-md q-mb-sm"
            >
              <div class="row items-center q-col-gutter-sm">
                <div class="col-12 col-md-6">
                  <div class="row items-center q-col-gutter-sm">
                    <div class="col-auto">
                      <q-checkbox v-model="cal.selected" />
                    </div>
                    <div class="col">
                      <div class="text-subtitle1">
                        {{ cal.name }}
                        <q-badge v-if="cal.is_default" color="primary" class="q-ml-xs">Default</q-badge>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="col-12 col-md-6">
                  <div class="column q-gutter-xs">
                    <q-toggle
                      v-model="cal.includeAvailability"
                      label="Affects availability"
                      color="primary"
                      :disable="!cal.selected"
                    />
                    <q-toggle
                      v-model="cal.writable"
                      label="Allow writeback"
                      color="secondary"
                      :disable="!cal.selected || !cal.can_edit"
                      :title="cal.can_edit ? 'Push updates to Outlook' : 'Read-only calendar'"
                    />
                    <q-toggle
                      v-model="cal.is_task_writeback"
                      label="Use for ChoreSync task events"
                      color="positive"
                      :disable="!cal.selected"
                      @update:model-value="(val) => val && setTaskWriteback(cal.id)"
                    />
                  </div>
                </div>
              </div>
            </q-card>
          </div>

          <div class="row q-mt-md items-center">
            <div class="col text-grey-7 text-caption">
              Selected {{ selectedCount }} / {{ calendars.length }}
            </div>
            <div class="col-auto">
              <q-btn
                color="primary"
                label="Save & Import"
                type="submit"
                :loading="saving"
                :disable="saving"
              />
            </div>
          </div>
        </q-form>
      </div>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { calendarService } from '../services/calendarService';

type CalendarItem = {
  id: string;
  name: string;
  color: string;
  is_default: boolean;
  can_edit: boolean;
  selected: boolean;
  includeAvailability: boolean;
  writable: boolean;
  is_task_writeback: boolean;
};

const calendars = ref<CalendarItem[]>([]);
const loading = ref(true);
const saving = ref(false);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const connectedMessage = ref<string | null>(null);
const router = useRouter();
const route = useRoute();

const selectedCount = computed(() => calendars.value.filter((c) => c.selected).length);

function setAll(value: boolean) {
  calendars.value = calendars.value.map((c) => ({ ...c, selected: value }));
}

function setTaskWriteback(calId: string) {
  // Radio-style: only one calendar can be the task writeback target
  calendars.value = calendars.value.map((c) => ({
    ...c,
    is_task_writeback: c.id === calId,
  }));
}

async function loadCalendars() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const resp = await calendarService.listOutlookCalendars();
    calendars.value = resp.data.map((item) => ({
      id: item.id,
      name: item.name,
      color: item.color || '',
      is_default: item.is_default,
      can_edit: item.can_edit,
      selected: item.is_default || item.can_edit,
      includeAvailability: true,
      writable: item.can_edit,
      is_task_writeback: item.is_default,
    }));
  } catch (err: any) {
    const detail = err?.response?.data?.detail;
    errorMessage.value = detail
      ? `Failed to load calendars: ${detail}`
      : 'Failed to load Outlook calendars. Please reconnect and try again.';
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  errorMessage.value = null;
  successMessage.value = null;
  try {
    const payload = calendars.value
      .filter((c) => c.selected)
      .map((c) => ({
        id: c.id,
        name: c.name,
        include_in_availability: c.includeAvailability,
        writable: c.writable && c.can_edit,
        is_task_writeback: c.is_task_writeback,
        color: c.color || null,
        timezone: null,
      }));
    const resp = await calendarService.selectOutlookCalendars(payload);
    router.push({ name: 'calendar', query: { sync: 'started', provider: 'outlook' } });
  } catch (err: any) {
    errorMessage.value = err?.response?.data?.detail || 'Failed to save selection. Please try again.';
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  if (route.query.connected) {
    connectedMessage.value = 'Outlook connected. Choose which calendars to keep in sync.';
    router.replace({ query: {} });
  }
  if (route.query.error) {
    errorMessage.value = 'Outlook authorization failed. Please try again.';
    router.replace({ query: {} });
  }
  loadCalendars();
});
</script>
