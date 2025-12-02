<template>
<q-page class="q-pa-md">
  <div class="row q-mb-md items-center">
    <div class="col">
      <div class="text-h5">Calendar</div>
      <div class="text-body2 text-grey-7">Events shown in your local time. Stored in UTC.</div>
      <div class="row q-col-gutter-sm q-mt-sm">
        <div v-if="!combineCalendars" class="col-auto">
          <q-select
            v-model="selectedCalendarIds"
            :options="calendarOptionsList"
            multiple
            emit-value
            map-options
            outlined
            dense
            style="min-width: 240px;"
            label="Calendars"
          />
        </div>
        <div class="col-auto flex items-center">
          <q-toggle v-model="combineCalendars" label="Combine calendars" />
        </div>
      </div>
    </div>
    <div class="col-auto row items-center q-gutter-sm">
      <q-btn round flat icon="refresh" :loading="loading" @click="reload" />
      <q-btn round color="primary" icon="add" @click="showCreate = true" />
    </div>
  </div>
  <full-calendar
    ref="calendarRef"
    :options="calendarOptions"
      class="bg-white rounded-borders"
    />
    <div v-if="error" class="q-mt-md">
      <q-banner type="warning" dense>{{ error }}</q-banner>
    </div>

    <q-dialog v-model="showCreate" persistent>
      <q-card style="max-width: 500px; width: 100%;">
        <q-card-section class="text-h6">Create Event</q-card-section>
        <q-separator />
      <q-card-section class="q-gutter-md">
        <q-input v-model="form.title" label="Title" outlined dense />
        <q-input v-model="form.description" label="Description" type="textarea" outlined dense />
        <q-input v-model="form.start" label="Start" type="datetime-local" outlined dense />
        <q-input v-model="form.end" label="End" type="datetime-local" outlined dense />
          <div class="row q-col-gutter-md">
            <div class="col-6">
              <q-toggle v-model="form.is_all_day" label="All day" />
            </div>
            <div class="col-6">
              <q-toggle v-model="form.blocks_availability" label="Blocks availability" />
            </div>
          </div>
        </q-card-section>
        <q-separator />
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" :loading="creating" @click="handleCreate">Save</q-btn>
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import FullCalendar from '@fullcalendar/vue3';
import '@fullcalendar/core/vdom';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import { eventService, type CalendarEvent } from '../services/eventService';
import '@fullcalendar/common/main.css';
import '@fullcalendar/daygrid/main.css';
import '@fullcalendar/timegrid/main.css';

const calendarRef = ref();
const loading = ref(false);
const error = ref('');
const events = ref<any[]>([]);
const showCreate = ref(false);
const creating = ref(false);
const editing = ref(false);
const selectedEventId = ref<number | null>(null);
const calendarOptionsList = ref<{ label: string; value: number }[]>([]);
const selectedCalendarIds = ref<number[]>([]);
const combineCalendars = ref(true);
const form = ref({
  title: '',
  description: '',
  start: '',
  end: '',
  is_all_day: false,
  blocks_availability: true,
});

const calendarOptions = ref({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  firstDay: 1, // Monday start
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay',
  },
  events: events.value,
  datesSet: fetchRange,
  eventClick: handleEventClick,
  editable: true,
  eventDurationEditable: true,
  eventResizableFromStart: true,
  eventDrop: handleEventMove,
  eventResize: handleEventResize,
});

async function fetchRange(arg: any) {
  loading.value = true;
  error.value = '';
  try {
    const resp = await eventService.list({
      start: arg.startStr,
      end: arg.endStr,
    });
    const calendarsSeen = new Map<number, string>();
    const calColors = new Map<number, string | null>();
    resp.data.forEach((ev) => {
      calendarsSeen.set(ev.calendar_id, ev.calendar_name);
      calColors.set(ev.calendar_id, ev.calendar_color || '#1976d2');
    });
    calendarOptionsList.value = Array.from(calendarsSeen.entries()).map(([id, name]) => ({
      value: id,
      label: name,
    }));
    if (!selectedCalendarIds.value.length) {
      selectedCalendarIds.value = Array.from(calendarsSeen.keys());
    }
    const filterIds = combineCalendars.value ? Array.from(calendarsSeen.keys()) : selectedCalendarIds.value;
    events.value = resp.data
      .filter((ev: CalendarEvent) => filterIds.includes(ev.calendar_id))
      .map((ev: CalendarEvent) => ({
        id: ev.id,
        title: ev.title,
        start: ev.start,
        end: ev.end,
        allDay: ev.is_all_day,
        extendedProps: {
          source: ev.source,
          calendarName: ev.calendar_name,
          description: ev.description,
          blocksAvailability: ev.blocks_availability,
        },
        backgroundColor: ev.calendar_color || '#1976d2',
        borderColor: ev.calendar_color || '#1976d2',
      }));
    if (calendarRef.value?.getApi) {
      calendarRef.value.getApi().setOption('events', events.value);
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to load events.';
  } finally {
    loading.value = false;
  }
}

function reload() {
  const api = calendarRef.value?.getApi?.();
  if (api) {
    fetchRange({ startStr: api.view.activeStart.toISOString(), endStr: api.view.activeEnd.toISOString() });
  }
}

async function handleCreate() {
  creating.value = true;
  error.value = '';
  try {
    if (editing.value && selectedEventId.value !== null) {
      await eventService.update(selectedEventId.value, {
        title: form.value.title,
        description: form.value.description,
        start: form.value.start ? new Date(form.value.start).toISOString() : undefined,
        end: form.value.end ? new Date(form.value.end).toISOString() : undefined,
        is_all_day: form.value.is_all_day,
        blocks_availability: form.value.blocks_availability,
      });
    } else {
      await eventService.create({
        title: form.value.title,
        description: form.value.description,
        start: new Date(form.value.start).toISOString(),
        end: new Date(form.value.end).toISOString(),
        is_all_day: form.value.is_all_day,
        blocks_availability: form.value.blocks_availability,
      });
    }
    showCreate.value = false;
    // reset form
    form.value = {
      title: '',
      description: '',
      start: '',
      end: '',
      is_all_day: false,
      blocks_availability: true,
    };
    reload();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to save event.';
  } finally {
    creating.value = false;
  }
}

function handleEventClick(arg: any) {
  const ev = arg.event;
  selectedEventId.value = Number(ev.id);
  editing.value = true;
  showCreate.value = true;
  form.value = {
    title: ev.title,
    description: ev.extendedProps?.description || '',
    start: ev.start ? toLocalInput(ev.start) : '',
    end: ev.end ? toLocalInput(ev.end) : '',
    is_all_day: ev.allDay,
    blocks_availability: ev.extendedProps?.blocksAvailability ?? true,
  };
}

function toLocalInput(dateObj: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  const year = dateObj.getFullYear();
  const month = pad(dateObj.getMonth() + 1);
  const day = pad(dateObj.getDate());
  const hours = pad(dateObj.getHours());
  const mins = pad(dateObj.getMinutes());
  return `${year}-${month}-${day}T${hours}:${mins}`;
}

async function handleEventMove(arg: any) {
  error.value = '';
  try {
    await eventService.update(Number(arg.event.id), {
      start: arg.event.start?.toISOString(),
      end: arg.event.end?.toISOString(),
      is_all_day: arg.event.allDay,
    });
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to move event.';
    arg.revert();
  }
}

async function handleEventResize(arg: any) {
  error.value = '';
  try {
    await eventService.update(Number(arg.event.id), {
      start: arg.event.start?.toISOString(),
      end: arg.event.end?.toISOString(),
    });
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to resize event.';
    arg.revert();
  }
}
</script>

<style scoped>
.fc {
  background: #fff;
  border-radius: 8px;
}
</style>
