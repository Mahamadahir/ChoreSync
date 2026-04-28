<template>
  <div class="cal-page">

    <!-- ── Page header ───────────────────────────────────────── -->
    <div class="cal-header">
      <div>
        <h2 class="cal-title">Calendar</h2>
        <p class="cal-sub">Events shown in your local time</p>
      </div>
      <div class="cal-actions">
        <div v-if="!combineCalendars" class="cal-filter-pill">
          <span class="material-symbols-outlined">filter_list</span>
          <q-select
            v-model="selectedCalendarIds"
            :options="calendarOptionsList"
            multiple emit-value map-options borderless dense
            style="min-width:150px"
            label="Calendars"
          />
        </div>
        <div class="cal-combine-row">
          <span class="cal-combine-label">Combine</span>
          <button
            :class="['cal-toggle', { 'cal-toggle--on': combineCalendars }]"
            @click="combineCalendars = !combineCalendars"
          ><div class="cal-toggle-thumb" /></button>
        </div>
        <button class="cal-icon-btn" @click="reload">
          <span class="material-symbols-outlined" :style="loading ? 'animation:spin .8s linear infinite' : ''">refresh</span>
        </button>
        <button class="cal-create-btn" @click="showCreate = true; editing = false; resetForm()">
          <span class="material-symbols-outlined">add</span>
          Create Event
        </button>
      </div>
    </div>

    <!-- ── Sync-started banner ──────────────────────────────── -->
    <div v-if="syncBanner" class="cal-sync-banner">
      <span class="material-symbols-outlined" style="font-size:16px;vertical-align:middle">sync</span>
      Your {{ syncProvider === 'outlook' ? 'Outlook' : 'Google' }} Calendar is syncing in the background. You'll get a notification when it's done.
      <button class="cal-sync-banner-close" @click="syncBanner = false">✕</button>
    </div>

    <!-- ── Error banner ──────────────────────────────────────── -->
    <div v-if="error" class="cal-error-banner">{{ error }}</div>

    <!-- ── Calendar card ─────────────────────────────────────── -->
    <div class="cal-card">

      <!-- Toolbar -->
      <div class="cal-toolbar">
        <div class="cal-toolbar-left">
          <div class="cal-nav">
            <button class="cal-nav-btn" @click="prevCal">
              <span class="material-symbols-outlined">chevron_left</span>
            </button>
            <button class="cal-nav-today" @click="todayCal">Today</button>
            <button class="cal-nav-btn" @click="nextCal">
              <span class="material-symbols-outlined">chevron_right</span>
            </button>
          </div>
          <h3 class="cal-month-label">{{ currentTitle }}</h3>
        </div>
        <div class="cal-view-switcher">
          <button
            v-for="v in viewOptions"
            :key="v.value"
            :class="['cal-view-btn', { 'cal-view-btn--active': currentView === v.value }]"
            @click="changeView(v.value)"
          >{{ v.label }}</button>
        </div>
      </div>

      <!-- FullCalendar -->
      <div class="cal-body">
        <full-calendar ref="calendarRef" :options="calendarOptions" class="cal-fc" />
      </div>
    </div>

    <!-- ── Connected Calendars settings ────────────────────────── -->
    <div v-if="externalCalendars.length > 0" class="cal-settings-panel">
      <h3 class="cal-settings-title">
        <span class="material-symbols-outlined" style="font-size:16px;vertical-align:middle;margin-right:6px">tune</span>
        Connected Calendars
      </h3>
      <div class="cal-settings-list">
        <div v-for="cal in externalCalendars" :key="cal.id" class="cal-settings-row">
          <div class="cal-settings-info">
            <span class="material-symbols-outlined cal-settings-provider-icon">
              {{ cal.provider === 'google' ? 'event' : 'calendar_month' }}
            </span>
            <div>
              <div class="cal-settings-name">{{ cal.name }}</div>
              <div class="cal-settings-provider">{{ cal.provider === 'google' ? 'Google Calendar' : 'Microsoft Outlook' }}</div>
            </div>
          </div>
          <div class="cal-settings-toggle-group">
            <span class="cal-settings-toggle-label">Push updates</span>
            <button
              :class="['cal-toggle', { 'cal-toggle--on': cal.push_enabled }]"
              @click="togglePushEnabled(cal)"
              :title="cal.push_enabled ? 'Disable push updates to this calendar' : 'Enable push updates to this calendar'"
            ><div class="cal-toggle-thumb" /></button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create / Edit dialog ──────────────────────────────── -->
    <q-dialog v-model="showCreate" persistent>
      <div class="cal-dialog">
        <div class="cal-dialog-body">
          <div class="cal-dialog-header">
            <h4 class="cal-dialog-title">{{ editing ? 'Edit Event' : 'Create Event' }}</h4>
            <button class="cal-dialog-close" @click="showCreate = false">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div class="cal-dialog-fields">
            <div class="cal-field">
              <label class="cal-field-label">Title</label>
              <input v-model="form.title" class="cal-input" placeholder="Add title" />
            </div>
            <div class="cal-field">
              <label class="cal-field-label">Description</label>
              <textarea v-model="form.description" class="cal-input cal-textarea" placeholder="Add description or notes" rows="3" />
            </div>
            <div class="cal-field">
              <label class="cal-field-label">Start</label>
              <input v-model="form.start" type="datetime-local" class="cal-input" />
            </div>
            <div class="cal-field">
              <label class="cal-field-label">End</label>
              <input v-model="form.end" type="datetime-local" class="cal-input" />
            </div>
            <div v-if="!editing && userCalendars.length > 0" class="cal-field">
              <label class="cal-field-label">Calendar</label>
              <select v-model="form.calendar_id" class="cal-input cal-select">
                <option v-for="cal in userCalendars" :key="cal.id" :value="cal.id">
                  {{ cal.provider === 'internal' ? 'ChoreSync (local only)' : cal.name }}
                </option>
              </select>
            </div>
            <div class="cal-toggles">
              <div class="cal-toggle-row">
                <span class="cal-toggle-label">All day</span>
                <button
                  :class="['cal-toggle', { 'cal-toggle--on': form.is_all_day }]"
                  @click="form.is_all_day = !form.is_all_day"
                ><div class="cal-toggle-thumb" /></button>
              </div>
              <div class="cal-toggle-row">
                <span class="cal-toggle-label">
                  Blocks availability
                  <span class="material-symbols-outlined cal-info-icon" title="Prevents task assignment during this time">info</span>
                </span>
                <button
                  :class="['cal-toggle', 'cal-toggle--secondary', { 'cal-toggle--on': form.blocks_availability }]"
                  @click="form.blocks_availability = !form.blocks_availability"
                ><div class="cal-toggle-thumb" /></button>
              </div>
            </div>
          </div>
        </div>
        <div class="cal-dialog-footer">
          <button v-if="editing" class="cal-delete-btn" :disabled="deleting" @click="handleDelete">
            <span class="material-symbols-outlined">delete</span>
            {{ deleting ? 'Deleting…' : 'Delete' }}
          </button>
          <div class="cal-dialog-footer-right">
            <button class="cal-cancel-btn" @click="showCreate = false">Cancel</button>
            <button class="cal-save-btn" :disabled="creating" @click="handleCreate">
              {{ creating ? 'Saving…' : 'Save Event' }}
            </button>
          </div>
        </div>
      </div>
    </q-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import FullCalendar from '@fullcalendar/vue3';
import '@fullcalendar/core/vdom';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import { eventService, type CalendarEvent } from '../services/eventService';
import '@fullcalendar/common/main.css';
import '@fullcalendar/daygrid/main.css';
import '@fullcalendar/timegrid/main.css';
import { useAuthStore } from '../stores/auth';
import { api } from '../services/api';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const syncBanner = ref(false);
const syncProvider = ref<'google' | 'outlook'>('google');
const calendarRef = ref();
const loading = ref(false);
const error = ref('');
const events = ref<any[]>([]);
const showCreate = ref(false);
const creating = ref(false);
const deleting = ref(false);
const editing = ref(false);
const selectedEventId = ref<number | null>(null);
const calendarOptionsList = ref<{ label: string; value: number }[]>([]);
const selectedCalendarIds = ref<number[]>([]);
const combineCalendars = ref(true);
const userCalendars = ref<{ id: number; name: string; provider: string; push_enabled: boolean }[]>([]);
const currentTitle = ref('');
const currentView = ref('dayGridMonth');
const eventSource = ref<EventSource | null>(null);

const viewOptions = [
  { value: 'dayGridMonth', label: 'Month' },
  { value: 'timeGridWeek', label: 'Week' },
  { value: 'timeGridDay', label: 'Day' },
];

const form = ref({
  title: '',
  description: '',
  start: '',
  end: '',
  is_all_day: false,
  blocks_availability: true,
  calendar_id: null as number | null,
});

function toLocalDatetimeInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function resetForm() {
  const start = new Date();
  start.setMinutes(Math.ceil(start.getMinutes() / 30) * 30, 0, 0);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  // Prefer first Google/Outlook push-enabled calendar; fall back to any calendar
  const defaultCal = userCalendars.value.find(c => c.push_enabled && c.provider !== 'internal')
    ?? userCalendars.value.find(c => c.provider !== 'internal')
    ?? userCalendars.value[0];
  form.value = {
    title: '', description: '',
    start: toLocalDatetimeInput(start),
    end: toLocalDatetimeInput(end),
    is_all_day: false, blocks_availability: true,
    calendar_id: defaultCal?.id ?? null,
  };
  selectedEventId.value = null;
}

async function loadUserCalendars() {
  try {
    const resp = await api.get('/api/calendars/');
    userCalendars.value = resp.data;
  } catch {}
}

const externalCalendars = computed(() =>
  userCalendars.value.filter((c) => c.provider !== 'internal')
);

async function togglePushEnabled(cal: { id: number; name: string; provider: string; push_enabled: boolean }) {
  const newVal = !cal.push_enabled;
  cal.push_enabled = newVal;
  try {
    await api.patch(`/api/calendars/${cal.id}/`, { push_enabled: newVal });
  } catch {
    cal.push_enabled = !newVal;
  }
}

const calendarOptions = ref({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  firstDay: 1,
  headerToolbar: false as any,
  events: events.value,
  datesSet: fetchRange,
  eventClick: handleEventClick,
  editable: true,
  eventStartEditable: true,
  eventDurationEditable: true,
  eventResizableFromStart: true,
  forceEventDuration: true,
  eventDrop: handleEventMove,
  eventResize: handleEventResize,
  height: '100%',
  dayMaxEvents: 3,
});

// ── Navigation ───────────────────────────────────────────────
function prevCal() { calendarRef.value?.getApi?.()?.prev(); }
function nextCal() { calendarRef.value?.getApi?.()?.next(); }
function todayCal() { calendarRef.value?.getApi?.()?.today(); }
function changeView(view: string) {
  currentView.value = view;
  calendarRef.value?.getApi?.()?.changeView(view);
}

watch(combineCalendars, () => { reload(); });
watch(selectedCalendarIds, () => { if (!combineCalendars.value) reload(); });

onMounted(() => {
  if (route.query.sync === 'started') {
    syncBanner.value = true;
    syncProvider.value = route.query.provider === 'outlook' ? 'outlook' : 'google';
    router.replace({ query: {} });
  }
  loadUserCalendars();
  const api = calendarRef.value?.getApi?.();
  if (api) {
    currentTitle.value = api.view.title;
    fetchRange({ startStr: api.view.activeStart.toISOString(), endStr: api.view.activeEnd.toISOString(), view: api.view });
  }
  startStream();
});

onBeforeUnmount(() => {
  if (eventSource.value) { eventSource.value.close(); eventSource.value = null; }
});

async function fetchRange(arg: any) {
  currentTitle.value = arg.view?.title || currentTitle.value;
  currentView.value = arg.view?.type || currentView.value;
  loading.value = true;
  error.value = '';
  try {
    const api = calendarRef.value?.getApi?.();
    const viewType = api?.view?.type || 'dayGridMonth';
    const { startIso, endIso } = buildBufferedRange(arg.startStr, arg.endStr, viewType);
    const resp = await eventService.list({ start: startIso, end: endIso });
    const calendarsSeen = new Map<number, string>();
    resp.data.forEach((ev) => { calendarsSeen.set(ev.calendar_id, ev.calendar_name); });
    calendarOptionsList.value = Array.from(calendarsSeen.entries()).map(([id, name]) => ({ value: id, label: name }));
    if (!selectedCalendarIds.value.length) selectedCalendarIds.value = Array.from(calendarsSeen.keys());
    const filterIds = combineCalendars.value ? Array.from(calendarsSeen.keys()) : selectedCalendarIds.value;
    events.value = resp.data
      .filter((ev: CalendarEvent) => filterIds.includes(ev.calendar_id))
      .map((ev: CalendarEvent) => ({
        id: ev.id,
        title: ev.title,
        start: ev.start,
        end: ev.end || ev.start,
        allDay: ev.is_all_day,
        extendedProps: { source: ev.source, calendarName: ev.calendar_name, description: ev.description, blocksAvailability: ev.blocks_availability },
        backgroundColor: ev.calendar_color || '#94433a',
        borderColor: ev.calendar_color || '#94433a',
      }));
    calendarRef.value?.getApi?.()?.setOption('events', events.value);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to load events.';
  } finally {
    loading.value = false;
  }
}

function reload() {
  const api = calendarRef.value?.getApi?.();
  if (api) fetchRange({ startStr: api.view.activeStart.toISOString(), endStr: api.view.activeEnd.toISOString(), view: api.view });
}

function buildBufferedRange(startStr: string, endStr: string, viewType: string) {
  const start = new Date(startStr); const end = new Date(endStr);
  if (viewType === 'dayGridMonth') { start.setMonth(start.getMonth() - 1); end.setMonth(end.getMonth() + 1); }
  else if (viewType === 'timeGridWeek') { start.setDate(start.getDate() - 7); end.setDate(end.getDate() + 7); }
  else { start.setDate(start.getDate() - 1); end.setDate(end.getDate() + 1); }
  return { startIso: start.toISOString(), endIso: end.toISOString() };
}

async function handleCreate() {
  creating.value = true; error.value = '';
  try {
    if (editing.value && selectedEventId.value !== null) {
      await eventService.update(selectedEventId.value, {
        title: form.value.title, description: form.value.description,
        start: form.value.start ? new Date(form.value.start).toISOString() : undefined,
        end: form.value.end ? new Date(form.value.end).toISOString() : undefined,
        is_all_day: form.value.is_all_day, blocks_availability: form.value.blocks_availability,
      });
    } else {
      await eventService.create({
        title: form.value.title, description: form.value.description,
        start: new Date(form.value.start).toISOString(), end: new Date(form.value.end).toISOString(),
        is_all_day: form.value.is_all_day, blocks_availability: form.value.blocks_availability,
        calendar_id: form.value.calendar_id ?? undefined,
      });
    }
    showCreate.value = false; resetForm(); reload();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to save event.';
  } finally { creating.value = false; }
}

async function handleDelete() {
  if (selectedEventId.value === null) return;
  deleting.value = true; error.value = '';
  try {
    await eventService.delete(selectedEventId.value);
    showCreate.value = false; editing.value = false; selectedEventId.value = null; reload();
  } catch (err: any) {
    error.value = err?.response?.data?.detail || 'Unable to delete event.';
  } finally { deleting.value = false; }
}

function handleEventClick(arg: any) {
  const ev = arg.event;
  selectedEventId.value = Number(ev.id); editing.value = true; showCreate.value = true;
  form.value = {
    title: ev.title, description: ev.extendedProps?.description || '',
    start: ev.start ? toLocalInput(ev.start) : '', end: ev.end ? toLocalInput(ev.end) : '',
    is_all_day: ev.allDay, blocks_availability: ev.extendedProps?.blocksAvailability ?? true,
    calendar_id: null,
  };
}

function toLocalInput(dateObj: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${dateObj.getFullYear()}-${pad(dateObj.getMonth()+1)}-${pad(dateObj.getDate())}T${pad(dateObj.getHours())}:${pad(dateObj.getMinutes())}`;
}

async function handleEventMove(arg: any) {
  try { await eventService.update(Number(arg.event.id), { start: arg.event.start?.toISOString(), end: arg.event.end?.toISOString(), is_all_day: arg.event.allDay }); }
  catch (err: any) { error.value = err?.response?.data?.detail || 'Unable to move event.'; arg.revert(); }
}

async function handleEventResize(arg: any) {
  try { await eventService.update(Number(arg.event.id), { start: arg.event.start?.toISOString(), end: arg.event.end?.toISOString(), is_all_day: arg.event.allDay }); }
  catch (err: any) { error.value = err?.response?.data?.detail || 'Unable to resize event.'; arg.revert(); }
}

function startStream() {
  if (!authStore.isAuthenticated) return;
  try {
    const es = eventService.stream(); eventSource.value = es;
    es.onmessage = () => { reload(); };
    es.addEventListener('ping', () => {});
    es.addEventListener('close', () => { es.close(); eventSource.value = null; });
    es.onerror = () => { es.close(); eventSource.value = null; if (authStore.isAuthenticated) setTimeout(startStream, 10000); };
  } catch {}
}
</script>

<style scoped>
/* ── Page shell ───────────────────────────────────────────── */
.cal-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--cs-topbar-h, 64px));
  padding: 28px 32px 24px;
  overflow: hidden;
  box-sizing: border-box;
}

/* ── Header ───────────────────────────────────────────────── */
.cal-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-shrink: 0;
  margin-bottom: 24px;
}
.cal-title {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--cs-on-surface);
  margin: 0 0 4px;
}
.cal-sub {
  font-size: 13px;
  color: var(--cs-muted);
  font-weight: 500;
  margin: 0;
}
.cal-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cal-filter-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--cs-surface);
  border-radius: var(--cs-radius-md);
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--cs-on-surface-variant);
}
.cal-filter-pill .material-symbols-outlined { font-size: 18px; color: var(--cs-muted); }
.cal-combine-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cal-combine-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--cs-muted);
}
.cal-icon-btn {
  width: 40px; height: 40px;
  border-radius: var(--cs-radius-md);
  border: none;
  background: var(--cs-surface);
  color: var(--cs-on-surface-variant);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.cal-icon-btn:hover { background: var(--cs-surface-high); color: var(--cs-primary); }
.cal-create-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 22px;
  border-radius: var(--cs-radius-md);
  border: none;
  background: linear-gradient(135deg, #94433a 0%, #b35b50 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(148,67,58,.2);
  transition: transform 0.1s, box-shadow 0.15s;
}
.cal-create-btn:hover { transform: scale(0.98); box-shadow: 0 6px 16px rgba(148,67,58,.25); }
.cal-create-btn .material-symbols-outlined { font-size: 18px; }

/* ── Toggle ───────────────────────────────────────────────── */
.cal-toggle {
  width: 40px; height: 24px;
  border-radius: 12px;
  border: none;
  background: var(--cs-surface-high);
  position: relative;
  display: flex; align-items: center;
  padding: 0 4px;
  cursor: pointer;
  transition: background 0.2s;
}
.cal-toggle--on { background: var(--cs-secondary-container); justify-content: flex-end; }
.cal-toggle--secondary.cal-toggle--on { background: var(--cs-secondary-container); }
.cal-toggle-thumb {
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--cs-muted);
  box-shadow: 0 1px 3px rgba(0,0,0,.2);
  transition: background 0.2s;
}
.cal-toggle--on .cal-toggle-thumb { background: var(--cs-secondary); }

/* ── Sync-started banner ──────────────────────────────────── */
.cal-sync-banner {
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 10px 16px;
  background: #e8f4fd;
  color: #1565c0;
  border-radius: var(--cs-radius-md);
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}
.cal-sync-banner-close {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: #1565c0;
  font-size: 14px;
  opacity: 0.7;
  padding: 0 4px;
}
.cal-sync-banner-close:hover { opacity: 1; }

/* ── Error banner ─────────────────────────────────────────── */
.cal-error-banner {
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 10px 16px;
  background: var(--cs-overdue-bg);
  color: var(--cs-overdue);
  border-radius: var(--cs-radius-md);
  font-size: 13px;
  font-weight: 500;
}

/* ── Calendar card ────────────────────────────────────────── */
.cal-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f5f3ef;
  border-radius: 28px;
  box-shadow: 0 20px 50px -12px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.04);
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.5);
}

/* ── Toolbar ──────────────────────────────────────────────── */
.cal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid rgba(214,211,208,.4);
  flex-shrink: 0;
  border-radius: 28px 28px 0 0;
}
.cal-toolbar-left { display: flex; align-items: center; gap: 16px; }
.cal-nav {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: var(--cs-radius-md);
  padding: 4px;
  gap: 2px;
}
.cal-nav-btn {
  width: 34px; height: 34px;
  border: none; background: transparent;
  border-radius: var(--cs-radius-sm);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--cs-on-surface-variant);
  transition: background 0.15s;
}
.cal-nav-btn:hover { background: var(--cs-surface); }
.cal-nav-btn .material-symbols-outlined { font-size: 20px; }
.cal-nav-today {
  padding: 6px 14px;
  border: none; background: transparent;
  border-radius: var(--cs-radius-sm);
  font-size: 13px; font-weight: 700;
  color: var(--cs-on-surface-variant);
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: background 0.15s;
}
.cal-nav-today:hover { background: var(--cs-surface); }
.cal-month-label {
  font-size: 20px;
  font-weight: 700;
  color: var(--cs-on-surface);
  margin: 0;
  letter-spacing: -0.3px;
}
.cal-view-switcher {
  display: flex;
  background: var(--cs-surface);
  border-radius: var(--cs-radius-md);
  padding: 4px;
  gap: 2px;
}
.cal-view-btn {
  padding: 8px 20px;
  border: none; background: transparent;
  border-radius: var(--cs-radius-sm);
  font-size: 13px; font-weight: 700;
  color: var(--cs-muted);
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.cal-view-btn:hover { color: var(--cs-on-surface); }
.cal-view-btn--active {
  background: linear-gradient(135deg, #94433a 0%, #b35b50 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(148,67,58,.3);
}

/* ── FC body ──────────────────────────────────────────────── */
.cal-body { flex: 1; min-height: 0; overflow: hidden; }
.cal-fc { height: 100%; }

:deep(.fc) {
  height: 100%;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  border: none;
}
:deep(.fc .fc-view-harness) { height: 100% !important; }
:deep(.fc .fc-scrollgrid) { border: none !important; }
:deep(.fc .fc-scrollgrid td),
:deep(.fc .fc-scrollgrid th) { border-color: rgba(214,211,208,.25) !important; }
:deep(.fc .fc-scrollgrid-section > *) { border: none !important; }
:deep(.fc .fc-col-header) { background: transparent; }
:deep(.fc .fc-col-header-cell) {
  background: transparent;
  border-color: rgba(214,211,208,.3) !important;
  padding: 12px 0;
}
:deep(.fc .fc-col-header-cell-cushion) {
  font-size: 10px;
  font-weight: 700;
  color: #a8a29e;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  text-decoration: none;
}
:deep(.fc .fc-daygrid-day) {
  background: rgba(255,255,255,.4);
  border-color: rgba(214,211,208,.2) !important;
}
:deep(.fc .fc-daygrid-day-number) {
  font-weight: 700;
  font-size: 13px;
  color: #292524;
  padding: 10px 14px;
  text-decoration: none;
}
:deep(.fc .fc-day-other) { background: rgba(245,243,239,.6); }
:deep(.fc .fc-day-other .fc-daygrid-day-number) { color: #a8a29e; }
:deep(.fc .fc-day-today) { background: rgba(148,67,58,.05) !important; }
:deep(.fc .fc-day-today .fc-daygrid-day-number) { color: #94433a; }
:deep(.fc .fc-event) {
  background: linear-gradient(135deg, #94433a 0%, #b35b50 100%);
  border: none;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  box-shadow: 0 1px 3px rgba(148,67,58,.25);
  cursor: pointer;
}
:deep(.fc .fc-event-title),
:deep(.fc .fc-event-time) { color: #fff; }
:deep(.fc .fc-more-link) {
  font-size: 11px; font-weight: 700;
  color: var(--cs-primary);
}
:deep(.fc .fc-timegrid-slot) { border-color: rgba(214,211,208,.2) !important; }
:deep(.fc .fc-timegrid-axis) { border-color: rgba(214,211,208,.2) !important; }

/* ── Dialog ───────────────────────────────────────────────── */
.cal-dialog {
  background: #fff;
  width: 100%;
  max-width: 500px;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 60px rgba(0,0,0,.15);
  border: 1px solid rgba(255,255,255,.6);
}
.cal-dialog-body { padding: 28px 28px 0; }
.cal-dialog-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 24px;
}
.cal-dialog-title {
  font-size: 22px; font-weight: 800; letter-spacing: -0.3px;
  color: var(--cs-on-surface); margin: 0;
}
.cal-dialog-close {
  width: 32px; height: 32px; border: none;
  background: var(--cs-surface); border-radius: var(--cs-radius-sm);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--cs-muted);
  transition: background 0.15s, color 0.15s;
}
.cal-dialog-close:hover { background: var(--cs-surface-high); color: var(--cs-on-surface); }
.cal-dialog-fields { display: flex; flex-direction: column; gap: 20px; padding-bottom: 24px; }
.cal-field { display: flex; flex-direction: column; gap: 6px; }
.cal-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.cal-field-label {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.12em; color: var(--cs-muted);
}
.cal-input {
  background: #efeeea;
  border: none; outline: none;
  border-radius: var(--cs-radius-md);
  padding: 12px 16px;
  font-size: 14px; font-weight: 500;
  color: var(--cs-on-surface);
  font-family: 'Plus Jakarta Sans', sans-serif;
  width: 100%;
  transition: box-shadow 0.15s;
}
.cal-input:focus { box-shadow: 0 0 0 2px rgba(148,67,58,.2); }
.cal-textarea { resize: none; }
.cal-select { cursor: pointer; appearance: auto; }
.cal-toggles { display: flex; flex-direction: column; gap: 14px; padding: 4px 0; }
.cal-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
}
.cal-toggle-label {
  font-size: 14px; font-weight: 700; color: var(--cs-on-surface);
  display: flex; align-items: center; gap: 6px;
}
.cal-info-icon { font-size: 14px !important; color: var(--cs-muted); cursor: help; }
.cal-dialog-footer {
  padding: 18px 24px;
  background: #f5f3ef;
  display: flex; align-items: center; justify-content: space-between;
}
.cal-dialog-footer-right { display: flex; gap: 12px; }
.cal-delete-btn {
  display: flex; align-items: center; gap: 6px;
  background: none; border: none;
  color: var(--cs-error); font-size: 13px; font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: opacity 0.15s;
}
.cal-delete-btn:hover { opacity: 0.75; }
.cal-delete-btn .material-symbols-outlined { font-size: 16px; }
.cal-cancel-btn {
  padding: 10px 20px; border-radius: var(--cs-radius-md);
  border: 1px solid var(--cs-outline-variant);
  background: #fff; color: var(--cs-on-surface-variant);
  font-size: 13px; font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  transition: background 0.15s;
}
.cal-cancel-btn:hover { background: var(--cs-surface); }
.cal-save-btn {
  padding: 10px 28px; border-radius: var(--cs-radius-md); border: none;
  background: linear-gradient(135deg, #94433a 0%, #b35b50 100%);
  color: #fff; font-size: 13px; font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(148,67,58,.25);
  transition: transform 0.1s;
}
.cal-save-btn:hover { transform: scale(0.98); }
.cal-save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Connected Calendars settings panel ──────────────────────── */
.cal-settings-panel {
  margin-top: 16px;
  background: var(--cs-surface-container-lowest, #fafafa);
  border-radius: 16px;
  padding: 18px 20px;
  border: 1px solid rgba(0,0,0,0.06);
}
.cal-settings-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--cs-on-surface-variant, #49454f);
  letter-spacing: 0.4px;
  margin: 0 0 14px;
  text-transform: uppercase;
}
.cal-settings-list { display: flex; flex-direction: column; gap: 10px; }
.cal-settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.05);
}
.cal-settings-info { display: flex; align-items: center; gap: 12px; }
.cal-settings-provider-icon { font-size: 20px; color: var(--cs-primary, #6750a4); font-family: 'Material Symbols Outlined'; }
.cal-settings-name { font-size: 14px; font-weight: 600; color: var(--cs-on-surface, #1c1b1f); }
.cal-settings-provider { font-size: 11px; color: var(--cs-on-surface-variant, #49454f); margin-top: 1px; }
.cal-settings-toggle-group { display: flex; align-items: center; gap: 10px; }
.cal-settings-toggle-label { font-size: 12px; color: var(--cs-on-surface-variant, #49454f); white-space: nowrap; }
</style>

<style>
/* FullCalendar dark mode */
body.body--dark .cal-card { background: #1e1e1e; }
body.body--dark .fc { background: #1e1e1e; color: #e0e0e0; }
body.body--dark .fc .fc-toolbar { background: #1e1e1e; }
body.body--dark .fc .fc-toolbar-title { color: #e0e0e0; }
body.body--dark .fc .fc-col-header-cell { background: #272727; border-color: #333 !important; }
body.body--dark .fc .fc-daygrid-day { background: #1e1e1e; border-color: #2e2e2e !important; }
body.body--dark .fc .fc-day-today { background: rgba(148,67,58,.12) !important; }
body.body--dark .fc .fc-daygrid-day-number,
body.body--dark .fc .fc-col-header-cell-cushion { color: #ccc; }
body.body--dark .fc .fc-day-today .fc-daygrid-day-number { color: #ffb4aa; }
body.body--dark .fc .fc-scrollgrid td,
body.body--dark .fc .fc-scrollgrid th { border-color: #2e2e2e !important; }
body.body--dark .fc .fc-timegrid-slot,
body.body--dark .fc .fc-timegrid-axis { border-color: #2e2e2e !important; }
</style>
