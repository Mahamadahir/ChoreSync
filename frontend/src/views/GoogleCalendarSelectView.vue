<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 900px; width: 100%;">
      <div class="row items-center q-mb-md">
        <div class="col">
          <div class="text-h5">Choose Google Calendars</div>
          <div class="text-body2 text-grey-7">
            Select which Google calendars to import and whether they count toward availability.
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

      <q-banner v-if="connectedMessage" dense class="q-mb-sm" type="positive">
        {{ connectedMessage }}
      </q-banner>
      <q-banner v-if="errorMessage" dense class="q-mb-sm" type="negative">
        {{ errorMessage }}
      </q-banner>
      <q-banner v-if="successMessage" dense class="q-mb-sm" type="positive">
        {{ successMessage }}
      </q-banner>

      <div v-if="loading" class="q-pa-md flex flex-center">
        <q-spinner color="primary" size="32px" />
      </div>

      <div v-else>
        <div v-if="calendars.length === 0" class="text-body2 text-grey-7">
          No Google calendars found. Confirm access in Google and try again.
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
                        <q-badge v-if="cal.primary" color="primary" class="q-ml-xs">Primary</q-badge>
                      </div>
                      <div class="text-caption text-grey-7">
                        Access: {{ cal.accessRole }} • Timezone: {{ cal.timezone || '—' }}
                      </div>
                    </div>
                  </div>
                </div>
                <div class="col-12 col-md-6">
                  <div class="row items-center q-gutter-sm">
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
                      :disable="!cal.selected || !cal.writableSuggested"
                      :title="cal.writableSuggested ? 'Push updates to Google' : 'Readonly access from Google'"
                    />
                    <q-input
                      v-model="cal.color"
                      dense
                      :disable="!cal.selected"
                      label="Color"
                      hint="Optional"
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
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { calendarService } from '../services/calendarService';

type CalendarItem = {
  id: string;
  name: string;
  accessRole: string;
  primary: boolean;
  color?: string;
  writableSuggested: boolean;
  timezone?: string;
  selected: boolean;
  includeAvailability: boolean;
  writable: boolean;
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

async function loadCalendars() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const resp = await calendarService.listGoogleCalendars();
    calendars.value = resp.data.map((item) => ({
      id: item.id,
      name: item.summary || '(untitled)',
      accessRole: item.accessRole,
      primary: !!item.primary,
      color: item.color || '',
      writableSuggested: item.writable,
      timezone: item.timeZone || '',
      selected: !!item.primary || item.writable, // default to syncing primary or writable calendars
      includeAvailability: true,
      writable: item.writable,
    }));
  } catch (err) {
    errorMessage.value = 'Failed to load Google calendars. Please reconnect and try again.';
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
        writable: c.writable && c.writableSuggested,
        color: c.color || null,
        timezone: c.timezone || null,
      }));
    await calendarService.selectGoogleCalendars(payload);
    let syncDetail = '';
    try {
      const syncResp = await calendarService.syncGoogle();
      syncDetail = syncResp.data?.detail || '';
    } catch (err) {
      syncDetail = 'Saved selection, but sync failed. Try manual sync.';
    }
    successMessage.value = syncDetail || 'Saved selection and synced calendars.';
  } catch (err: any) {
    errorMessage.value = err?.response?.data?.detail || 'Failed to save selection. Please try again.';
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  const connected = route.query.connected as string | undefined;
  const imported = route.query.imported as string | undefined;
  if (connected) {
    connectedMessage.value = imported
      ? `Google connected. Imported ${imported} events. Choose which calendars to keep in sync.`
      : 'Google connected. Choose which calendars to keep in sync.';
    router.replace({ query: {} });
  }
  loadCalendars();
});
</script>
