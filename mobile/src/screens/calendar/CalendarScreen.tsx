import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Modal,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import * as WebBrowser from 'expo-web-browser';
import { Calendar } from 'react-native-calendars';
import {
  calendarService,
  GoogleCalendarItem,
  GoogleCalendarSelectItem,
  OutlookCalendarItem,
  OutlookCalendarSelectItem,
} from '../../services/calendarService';
import { api } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';
import { Palette as C } from '../../theme';

type CalendarEvent = {
  id: number;
  title: string;
  start: string;
  end: string;
  is_all_day: boolean;
  blocks_availability: boolean;
  source: string;       // 'manual' | 'google' | 'outlook' | 'choresync'
  calendar_id: number;
  calendar_name: string;
  calendar_color?: string | null;
  description?: string | null;
};

function isEditable(ev: CalendarEvent): boolean {
  return ev.source === 'manual';
}

// ── Design tokens ─────────────────────────────────────────────

// ── How It Works steps ────────────────────────────────────────
const HOW_IT_WORKS = [
  { step: '1', icon: 'link',         title: 'Connect',  body: 'Securely link your preferred account to ChoreSync.' },
  { step: '2', icon: 'checklist',    title: 'Choose',   body: 'Select specific calendars for work or family chores.' },
  { step: '3', icon: 'auto_awesome', title: 'Sync',     body: 'Tasks appear as calendar events automatically.' },
];

type ProviderStatus = {
  connected: boolean;
  lastSynced: string | null;
  syncing: boolean;
};

// ── Calendar Picker Modal ─────────────────────────────────────
type PickerProvider = 'google' | 'outlook';

type CalendarRow =
  | (GoogleCalendarItem & { _provider: 'google' })
  | (OutlookCalendarItem & { _provider: 'outlook' });

function CalendarPickerModal({
  visible,
  provider,
  onClose,
  onConfirm,
}: {
  visible: boolean;
  provider: PickerProvider | null;
  onClose: () => void;
  onConfirm: (provider: PickerProvider, items: CalendarRow[], newlyAdded: boolean) => void;
}) {
  const [calendars, setCalendars] = useState<CalendarRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  // availability toggle per calendar id
  const [availability, setAvailability] = useState<Record<string, boolean>>({});
  // outlook writeback calendar id (only one at a time)
  const [writebackId, setWritebackId] = useState<string | null>(null);

  useEffect(() => {
    if (!visible || !provider) return;
    setLoading(true);
    setCalendars([]);
    setAvailability({});
    setWritebackId(null);

    const fetch =
      provider === 'google'
        ? calendarService.googleList().then((r) =>
            (r.data as GoogleCalendarItem[]).map((c) => ({ ...c, _provider: 'google' as const }))
          )
        : calendarService.outlookList().then((r) =>
            (r.data as OutlookCalendarItem[]).map((c) => ({ ...c, _provider: 'outlook' as const }))
          );

    fetch
      .then((rows) => {
        setCalendars(rows as CalendarRow[]);
        // Default: all included in availability
        const init: Record<string, boolean> = {};
        (rows as CalendarRow[]).forEach((c) => { init[c.id] = true; });
        setAvailability(init);
      })
      .catch(() => Alert.alert('Error', 'Could not load calendars.'))
      .finally(() => setLoading(false));
  }, [visible, provider]);

  const handleConfirm = async () => {
    if (!provider) return;
    setSaving(true);
    try {
      let newlyAdded = false;
      if (provider === 'google') {
        const payload: GoogleCalendarSelectItem[] = (calendars as (GoogleCalendarItem & { _provider: 'google' })[]).map((c) => ({
          id: c.id,
          name: c.summary,
          include_in_availability: availability[c.id] ?? true,
          writable: c.writable,
          color: c.color,
          timezone: c.timeZone,
        }));
        newlyAdded = (calendars as (GoogleCalendarItem & { _provider: 'google' })[]).some((c) => !c.already_synced);
        await calendarService.googleSelect(payload);
      } else {
        const payload: OutlookCalendarSelectItem[] = (calendars as (OutlookCalendarItem & { _provider: 'outlook' })[]).map((c) => ({
          id: c.id,
          name: c.name,
          include_in_availability: availability[c.id] ?? true,
          writable: c.can_edit,
          is_task_writeback: writebackId === c.id,
          color: c.color,
        }));
        await calendarService.outlookSelect(payload);
        newlyAdded = true; // Outlook has no already_synced annotation yet; assume new
      }
      onConfirm(provider, calendars, newlyAdded);
    } catch {
      Alert.alert('Error', 'Could not save calendar selection. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={pickerStyles.root}>
        {/* Header */}
        <View style={pickerStyles.header}>
          <Text style={pickerStyles.title}>
            {provider === 'google' ? 'Google Calendars' : 'Outlook Calendars'}
          </Text>
          <TouchableOpacity onPress={onClose} style={pickerStyles.closeBtn}>
            <Text style={[styles.msIcon, { color: C.stone500 }]}>close</Text>
          </TouchableOpacity>
        </View>
        <Text style={pickerStyles.subtitle}>Choose which calendars to include in availability checks.</Text>

        {loading ? (
          <ActivityIndicator style={{ marginTop: 48 }} size="large" color={C.primary} />
        ) : (
          <FlatList
            data={calendars}
            keyExtractor={(item) => item.id}
            contentContainerStyle={pickerStyles.list}
            renderItem={({ item }) => {
              const name = item._provider === 'google'
                ? (item as GoogleCalendarItem).summary
                : (item as OutlookCalendarItem).name;
              const color = item.color || '#888';

              return (
                <View style={pickerStyles.row}>
                  {/* Color dot */}
                  <View style={[pickerStyles.dot, { backgroundColor: color }]} />

                  <View style={pickerStyles.rowInfo}>
                    <View style={pickerStyles.rowNameRow}>
                      <Text style={pickerStyles.rowName}>{name}</Text>
                      {item._provider === 'google' && (item as GoogleCalendarItem).already_synced && (
                        <View style={pickerStyles.syncingBadge}>
                          <Text style={pickerStyles.syncingBadgeText}>SYNCING</Text>
                        </View>
                      )}
                    </View>
                    {item._provider === 'outlook' && (
                      <TouchableOpacity
                        onPress={() => setWritebackId((prev) => (prev === item.id ? null : item.id))}
                        style={pickerStyles.writebackRow}
                      >
                        <View style={[
                          pickerStyles.radioOuter,
                          writebackId === item.id && { borderColor: C.primary },
                        ]}>
                          {writebackId === item.id && <View style={pickerStyles.radioInner} />}
                        </View>
                        <Text style={pickerStyles.writebackLabel}>Task write-back</Text>
                      </TouchableOpacity>
                    )}
                  </View>

                  {/* Availability toggle */}
                  <View style={pickerStyles.switchWrap}>
                    <Text style={pickerStyles.switchLabel}>Availability</Text>
                    <Switch
                      value={availability[item.id] ?? true}
                      onValueChange={(v) => setAvailability((prev) => ({ ...prev, [item.id]: v }))}
                      trackColor={{ false: C.surfaceContainerHighest, true: C.primary }}
                      thumbColor={C.white}
                      ios_backgroundColor={C.surfaceContainerHighest}
                    />
                  </View>
                </View>
              );
            }}
          />
        )}

        {/* Confirm */}
        <View style={pickerStyles.footer}>
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={handleConfirm}
            disabled={saving || loading || calendars.length === 0}
            style={{ borderRadius: 14, overflow: 'hidden' }}
          >
            <LinearGradient
              colors={[C.primary, C.primaryContainer]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={pickerStyles.confirmBtn}
            >
              {saving
                ? <ActivityIndicator color={C.white} size="small" />
                : <Text style={pickerStyles.confirmBtnText}>Save Selection</Text>
              }
            </LinearGradient>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

// ── Integration card ─────────────────────────────────────────
function IntegrationCard({
  icon,
  name,
  status,
  onToggle,
  onSync,
  onChooseCalendars,
  disabled,
}: {
  icon: string;
  name: string;
  status: ProviderStatus;
  onToggle: (val: boolean) => void;
  onSync: () => void;
  onChooseCalendars?: () => void;
  disabled?: boolean;
}) {
  return (
    <View style={[styles.integrationCard, disabled && { opacity: 0.8 }]}>
      <View style={styles.integrationLeft}>
        {/* Icon circle */}
        <View style={[styles.integrationIconCircle, !status.connected && { opacity: 0.6 }]}>
          <Text style={[styles.msIcon, { color: status.connected ? C.primary : C.onSurfaceVariant, fontSize: 28 }]}>
            {icon}
          </Text>
        </View>

        {/* Info */}
        <View style={styles.integrationInfo}>
          <View style={styles.integrationNameRow}>
            <Text style={styles.integrationName}>{name}</Text>
            {status.connected && (
              <View style={styles.connectedBadge}>
                <Text style={styles.connectedBadgeText}>CONNECTED</Text>
              </View>
            )}
          </View>

          <Text style={styles.integrationSubtitle}>
            {status.connected
              ? status.lastSynced
                ? `Last synced ${status.lastSynced}`
                : 'Connected'
              : 'Disconnected'}
          </Text>

          {status.connected && onChooseCalendars && (
            <TouchableOpacity activeOpacity={0.7} onPress={onChooseCalendars}>
              <Text style={styles.chooseCalendarsLink}>Choose Calendars</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Toggle */}
      <Switch
        value={status.connected}
        onValueChange={onToggle}
        trackColor={{ false: C.surfaceContainerHighest, true: C.primary }}
        thumbColor={C.white}
        ios_backgroundColor={C.surfaceContainerHighest}
        disabled={status.syncing}
      />
    </View>
  );
}

// ── How It Works step card ────────────────────────────────────
function StepCard({ step, icon, title, body }: { step: string; icon: string; title: string; body: string }) {
  return (
    <View style={styles.stepCard}>
      <View style={styles.stepNum}>
        <Text style={styles.stepNumText}>{step}</Text>
      </View>
      <View style={styles.stepIconRow}>
        <Text style={[styles.msIcon, { color: C.secondary, fontSize: 20 }]}>{icon}</Text>
        <Text style={styles.stepTitle}>{title}</Text>
      </View>
      <Text style={styles.stepBody}>{body}</Text>
    </View>
  );
}

// ── Helpers ───────────────────────────────────────────────────
/** Format a local-date string (YYYY-MM-DD) to a readable label. */
function formatDateLabel(dateStr: string): string {
  // Parse as local date by replacing '-' separators so Date doesn't treat as UTC
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
}

/** Extract the HH:MM portion from an ISO datetime string in local time. */
function isoToHHMM(iso: string): string {
  const d = new Date(iso);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

/** Validate that a string is a valid HH:MM time. */
function isValidHHMM(t: string): boolean {
  if (!/^\d{1,2}:\d{2}$/.test(t)) return false;
  const [h, m] = t.split(':').map(Number);
  return h >= 0 && h <= 23 && m >= 0 && m <= 59;
}

/** Build a UTC ISO-8601 string from a local YYYY-MM-DD date + HH:MM time.
 *  Uses the multi-argument Date constructor which is guaranteed to interpret
 *  arguments as local time, avoiding the ambiguous string-parsing behaviour
 *  of new Date('YYYY-MM-DDTHH:MM:SS') across JS engines (incl. Hermes).
 */
function buildIso(date: string, time: string): string {
  const [year, month, day] = date.split('-').map(Number);
  const [hours, minutes] = time.padStart(5, '0').split(':').map(Number);
  return new Date(year, month - 1, day, hours, minutes, 0).toISOString();
}

type UserCalendar = { id: number; name: string; provider: string; color: string; push_enabled: boolean };

// ── Calendar event view tab ───────────────────────────────────
function CalendarViewTab({ insets }: { insets: ReturnType<typeof useSafeAreaInsets> }) {
  const today = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD in local timezone
  const [selectedDate, setSelectedDate] = useState(today);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [markedDates, setMarkedDates] = useState<Record<string, any>>({});
  const [createVisible, setCreateVisible] = useState(false);
  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);
  const [userCalendars, setUserCalendars] = useState<UserCalendar[]>([]);
  const [showDatePicker, setShowDatePicker] = useState(false);

  // Create/edit form state — times stored as "HH:MM" strings
  const [form, setForm] = useState({
    title: '',
    description: '',
    date: today,
    startTime: '09:00',
    endTime: '10:00',
    is_all_day: false,
    blocks_availability: false,
    calendar_id: null as number | null,
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // Load user's calendars once on mount for the calendar picker
  useEffect(() => {
    api.get<UserCalendar[]>('/api/calendars/')
      .then((res) => {
        const cals: UserCalendar[] = Array.isArray(res.data) ? res.data : [];
        setUserCalendars(cals);
      })
      .catch(() => {});
  }, []);

  const loadEvents = useCallback(async (date: string) => {
    setLoading(true);
    setLoadError('');
    try {
      // Fetch a ±7 day window around the selected date
      const d = new Date(date + 'T00:00:00Z');
      const start = new Date(d); start.setUTCDate(start.getUTCDate() - 7);
      const end = new Date(d); end.setUTCDate(end.getUTCDate() + 21);
      const res = await api.get<CalendarEvent[]>('/api/events/', {
        params: { start: start.toISOString(), end: end.toISOString() },
      });
      const data: CalendarEvent[] = Array.isArray(res.data) ? res.data : [];
      setEvents(data);

      // Build marked dates for the calendar dots
      const marks: Record<string, any> = {};
      data.forEach((ev) => {
        const d = new Date(ev.start).toLocaleDateString('en-CA');
        marks[d] = {
          marked: true,
          dotColor: ev.calendar_color || C.primary,
        };
      });
      // Highlight selected
      marks[selectedDate] = {
        ...(marks[selectedDate] ?? {}),
        selected: true,
        selectedColor: C.primary,
      };
      setMarkedDates(marks);
    } catch {
      setLoadError('Could not load events. Tap to retry.');
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => { loadEvents(selectedDate); }, [selectedDate]);

  // ── Live-refresh: re-fetch when a calendar_sync_complete notification arrives ──
  const syncCount = useNotificationStore(
    (s) => s.notifications.filter((n) => n.type === 'calendar_sync_complete').length,
  );
  const prevSyncCount = useRef(syncCount);
  useEffect(() => {
    if (syncCount > prevSyncCount.current) {
      loadEvents(selectedDate);
    }
    prevSyncCount.current = syncCount;
  }, [syncCount, selectedDate, loadEvents]);

  const dayEvents = events.filter((ev) => new Date(ev.start).toLocaleDateString('en-CA') === selectedDate);

  function defaultCalendarId(): number | null {
    // Prefer: first push-enabled non-internal (Google/Outlook), then any, then null
    const preferred = userCalendars.find((c) => c.push_enabled && c.provider !== 'internal')
      ?? userCalendars.find((c) => c.provider !== 'internal')
      ?? userCalendars[0];
    return preferred?.id ?? null;
  }

  function openCreate() {
    setEditEvent(null);
    setFormError('');
    setShowDatePicker(false);
    setForm({
      title: '',
      description: '',
      date: selectedDate,
      startTime: '09:00',
      endTime: '10:00',
      is_all_day: false,
      blocks_availability: false,
      calendar_id: defaultCalendarId(),
    });
    setCreateVisible(true);
  }

  function openEdit(ev: CalendarEvent) {
    if (!isEditable(ev)) {
      const provider = ev.source === 'google' ? 'Google Calendar'
        : ev.source === 'outlook' ? 'Outlook' : 'the source app';
      Alert.alert(
        'External event',
        `This event was imported from ${provider}. Edit it there and it will sync back automatically.`,
      );
      return;
    }
    setEditEvent(ev);
    setFormError('');
    setShowDatePicker(false);
    setForm({
      title: ev.title,
      description: ev.description ?? '',
      date: ev.start.split('T')[0],
      startTime: isoToHHMM(ev.start),
      endTime: isoToHHMM(ev.end),
      is_all_day: ev.is_all_day,
      blocks_availability: ev.blocks_availability,
      calendar_id: ev.calendar_id ?? null,
    });
    setCreateVisible(true);
  }

  async function handleSave() {
    if (!form.title.trim()) {
      setFormError('Please enter a title.');
      return;
    }
    if (!form.is_all_day && !isValidHHMM(form.startTime)) {
      setFormError('Start time must be HH:MM (e.g. 09:00).');
      return;
    }
    if (!form.is_all_day && !isValidHHMM(form.endTime)) {
      setFormError('End time must be HH:MM (e.g. 10:00).');
      return;
    }
    setFormError('');
    setSaving(true);

    const payload: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description,
      start: form.is_all_day ? `${form.date}T00:00:00Z` : buildIso(form.date, form.startTime),
      end: form.is_all_day ? `${form.date}T23:59:59Z` : buildIso(form.date, form.endTime),
      is_all_day: form.is_all_day,
      blocks_availability: form.blocks_availability,
    };
    if (!editEvent && form.calendar_id !== null) {
      payload.calendar_id = form.calendar_id;
    }

    try {
      if (editEvent) {
        await api.patch(`/api/events/${editEvent.id}/`, payload);
      } else {
        await api.post('/api/events/', payload);
      }
      setCreateVisible(false);
      await loadEvents(selectedDate);
    } catch (err: any) {
      const data: Record<string, unknown> = err?.response?.data ?? {};
      const firstField = Object.values(data)[0];
      const msg = (data.detail as string | undefined)
        ?? (Array.isArray(firstField) ? (firstField as string[])[0] : undefined)
        ?? 'Could not save event. Please try again.';
      setFormError(String(msg));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(ev: CalendarEvent) {
    if (!isEditable(ev)) {
      const provider = ev.source === 'google' ? 'Google Calendar'
        : ev.source === 'outlook' ? 'Outlook' : 'the source app';
      Alert.alert('External event', `Delete this event in ${provider} — it will sync back automatically.`);
      return;
    }
    Alert.alert('Delete Event', 'Remove this event?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/api/events/${ev.id}/`);
            loadEvents(selectedDate);
          } catch {
            Alert.alert('Error', 'Could not delete event.');
          }
        },
      },
    ]);
  }

  function formatTime(iso: string) {
    return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  return (
    <View style={{ flex: 1 }}>
      {/* Month calendar */}
      <Calendar
        current={selectedDate}
        onDayPress={(day: { dateString: string }) => setSelectedDate(day.dateString)}
        markedDates={markedDates}
        theme={{
          backgroundColor: C.bg,
          calendarBackground: C.bg,
          todayTextColor: C.primary,
          selectedDayBackgroundColor: C.primary,
          selectedDayTextColor: C.white,
          arrowColor: C.primary,
          dotColor: C.primary,
          textDayFontFamily: 'PlusJakartaSans-Medium',
          textMonthFontFamily: 'PlusJakartaSans-Bold',
          textDayHeaderFontFamily: 'PlusJakartaSans-SemiBold',
          textDayFontSize: 14,
          textMonthFontSize: 16,
          textDayHeaderFontSize: 11,
        }}
        style={{ borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.outlineVariant }}
      />

      {/* Event list for selected day */}
      <View style={{ flex: 1 }}>
        <View style={cvStyles.dayHeader}>
          <Text style={cvStyles.dayTitle}>
            {formatDateLabel(selectedDate)}
          </Text>
          <TouchableOpacity style={cvStyles.addBtn} onPress={openCreate}>
            <Text style={[cvStyles.msIcon, { color: C.white, fontSize: 18 }]}>add</Text>
          </TouchableOpacity>
        </View>

        {loading ? (
          <ActivityIndicator style={{ marginTop: 32 }} color={C.primary} />
        ) : loadError ? (
          <TouchableOpacity style={cvStyles.emptyDay} onPress={() => loadEvents(selectedDate)}>
            <Text style={[cvStyles.msIcon, { color: C.error, fontSize: 36 }]}>cloud_off</Text>
            <Text style={cvStyles.emptyDayText}>{loadError}</Text>
          </TouchableOpacity>
        ) : dayEvents.length === 0 ? (
          <View style={cvStyles.emptyDay}>
            <Text style={[cvStyles.msIcon, { color: C.outlineVariant, fontSize: 36 }]}>event_available</Text>
            <Text style={cvStyles.emptyDayText}>No events — tap + to add one</Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ padding: 16, gap: 10 }} showsVerticalScrollIndicator={false}>
            {dayEvents.map((ev) => (
              <TouchableOpacity
                key={ev.id}
                activeOpacity={0.85}
                style={cvStyles.eventCard}
                onPress={() => openEdit(ev)}
                onLongPress={() => handleDelete(ev)}
              >
                <View style={[cvStyles.eventAccent, { backgroundColor: ev.calendar_color || C.primary }]} />
                <View style={{ flex: 1 }}>
                  <Text style={cvStyles.eventTitle}>{ev.title}</Text>
                  <Text style={cvStyles.eventMeta}>
                    {ev.is_all_day ? 'All day' : `${formatTime(ev.start)} → ${formatTime(ev.end)}`}
                    {ev.calendar_name ? `  ·  ${ev.calendar_name}` : ''}
                  </Text>
                  {ev.description ? <Text style={cvStyles.eventDesc} numberOfLines={2}>{ev.description}</Text> : null}
                </View>
                {ev.blocks_availability && (
                  <Text style={[cvStyles.msIcon, { color: C.error, fontSize: 18 }]}>block</Text>
                )}
                {!isEditable(ev) && (
                  <Text style={[cvStyles.msIcon, { color: C.outline, fontSize: 16 }]}>lock</Text>
                )}
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}
      </View>

      {/* Create / edit modal */}
      <Modal visible={createVisible} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setCreateVisible(false)}>
        <View style={cvStyles.formRoot}>
          <View style={cvStyles.formHeader}>
            <Text style={cvStyles.formTitle}>{editEvent ? 'Edit Event' : 'New Event'}</Text>
            <TouchableOpacity onPress={() => setCreateVisible(false)}>
              <Text style={[cvStyles.msIcon, { color: C.stone500 }]}>close</Text>
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={cvStyles.formBody} keyboardShouldPersistTaps="handled">
            <Text style={cvStyles.formLabel}>TITLE</Text>
            <TextInput
              style={cvStyles.formInput}
              value={form.title}
              onChangeText={(v) => setForm((p) => ({ ...p, title: v }))}
              placeholder="Event title"
              placeholderTextColor={C.outline}
              autoFocus
            />

            <Text style={[cvStyles.formLabel, { marginTop: 16 }]}>DESCRIPTION</Text>
            <TextInput
              style={[cvStyles.formInput, { height: 80, textAlignVertical: 'top' }]}
              value={form.description}
              onChangeText={(v) => setForm((p) => ({ ...p, description: v }))}
              placeholder="Optional notes"
              placeholderTextColor={C.outline}
              multiline
            />

            <Text style={[cvStyles.formLabel, { marginTop: 16 }]}>DATE</Text>
            <TouchableOpacity
              style={[cvStyles.formInput, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
              onPress={() => setShowDatePicker((v) => !v)}
              activeOpacity={0.75}
            >
              <Text style={{ fontFamily: 'PlusJakartaSans-Medium', fontSize: 15, color: C.onSurface }}>
                {formatDateLabel(form.date)}
              </Text>
              <Text style={[cvStyles.msIcon, { color: C.onSurfaceVariant, fontSize: 18 }]}>
                {showDatePicker ? 'expand_less' : 'calendar_month'}
              </Text>
            </TouchableOpacity>
            {showDatePicker && (
              <View style={{ marginTop: 8, borderRadius: 12, overflow: 'hidden', borderWidth: 1, borderColor: C.outlineVariant }}>
                <Calendar
                  current={form.date}
                  onDayPress={(day: { dateString: string }) => {
                    setForm((p) => ({ ...p, date: day.dateString }));
                    setShowDatePicker(false);
                  }}
                  markedDates={{ [form.date]: { selected: true, selectedColor: C.primary } }}
                  theme={{
                    backgroundColor: C.surfaceContainerLow,
                    calendarBackground: C.surfaceContainerLow,
                    todayTextColor: C.primary,
                    selectedDayBackgroundColor: C.primary,
                    selectedDayTextColor: C.white,
                    arrowColor: C.primary,
                    textDayFontFamily: 'PlusJakartaSans-Medium',
                    textMonthFontFamily: 'PlusJakartaSans-Bold',
                    textDayHeaderFontFamily: 'PlusJakartaSans-SemiBold',
                    textDayFontSize: 13,
                    textMonthFontSize: 14,
                    textDayHeaderFontSize: 10,
                  }}
                />
              </View>
            )}

            {/* Calendar picker — only shown when creating, not editing */}
            {!editEvent && userCalendars.length > 1 && (
              <>
                <Text style={[cvStyles.formLabel, { marginTop: 16 }]}>CALENDAR</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={{ gap: 8, paddingVertical: 4 }}
                >
                  {userCalendars.map((cal) => {
                    const selected = form.calendar_id === cal.id;
                    const label = cal.provider === 'internal' ? 'ChoreSync' : cal.name;
                    const dot = cal.color || C.primary;
                    return (
                      <TouchableOpacity
                        key={cal.id}
                        onPress={() => setForm((p) => ({ ...p, calendar_id: cal.id }))}
                        activeOpacity={0.75}
                        style={[
                          cvStyles.calChip,
                          selected && { borderColor: C.primary, backgroundColor: C.primaryContainer ?? C.surfaceContainerLow },
                        ]}
                      >
                        <View style={[cvStyles.calChipDot, { backgroundColor: dot }]} />
                        <Text style={[
                          cvStyles.calChipLabel,
                          selected && { color: C.primary, fontFamily: 'PlusJakartaSans-Bold' },
                        ]}>
                          {label}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </>
            )}

            {!form.is_all_day && (
              <View style={{ flexDirection: 'row', gap: 12, marginTop: 16 }}>
                <View style={{ flex: 1 }}>
                  <Text style={cvStyles.formLabel}>START TIME</Text>
                  <TextInput
                    style={cvStyles.formInput}
                    value={form.startTime}
                    onChangeText={(v) => setForm((p) => ({ ...p, startTime: v }))}
                    placeholder="09:00"
                    placeholderTextColor={C.outline}
                    keyboardType="numbers-and-punctuation"
                    autoCapitalize="none"
                    maxLength={5}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={cvStyles.formLabel}>END TIME</Text>
                  <TextInput
                    style={cvStyles.formInput}
                    value={form.endTime}
                    onChangeText={(v) => setForm((p) => ({ ...p, endTime: v }))}
                    placeholder="10:00"
                    placeholderTextColor={C.outline}
                    keyboardType="numbers-and-punctuation"
                    autoCapitalize="none"
                    maxLength={5}
                  />
                </View>
              </View>
            )}

            <View style={cvStyles.toggleRow}>
              <Text style={cvStyles.toggleLabel}>All day</Text>
              <Switch
                value={form.is_all_day}
                onValueChange={(v) => setForm((p) => ({ ...p, is_all_day: v }))}
                trackColor={{ false: C.surfaceContainerHighest, true: C.primary }}
                thumbColor={C.white}
                ios_backgroundColor={C.surfaceContainerHighest}
              />
            </View>

            <View style={cvStyles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={cvStyles.toggleLabel}>Blocks availability</Text>
                <Text style={cvStyles.toggleSub}>Penalises task assignment during this time</Text>
              </View>
              <Switch
                value={form.blocks_availability}
                onValueChange={(v) => setForm((p) => ({ ...p, blocks_availability: v }))}
                trackColor={{ false: C.surfaceContainerHighest, true: C.error }}
                thumbColor={C.white}
                ios_backgroundColor={C.surfaceContainerHighest}
              />
            </View>

            {editEvent && (
              <TouchableOpacity
                style={cvStyles.deleteBtn}
                onPress={() => { setCreateVisible(false); handleDelete(editEvent); }}
              >
                <Text style={[cvStyles.msIcon, { color: C.error, fontSize: 18 }]}>delete</Text>
                <Text style={cvStyles.deleteBtnText}>Delete event</Text>
              </TouchableOpacity>
            )}
          </ScrollView>

          {!!formError && (
            <View style={cvStyles.formErrorBanner}>
              <Text style={cvStyles.formErrorText}>{formError}</Text>
            </View>
          )}

          <View style={cvStyles.formFooter}>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={handleSave}
              disabled={saving}
              style={{ borderRadius: 14, overflow: 'hidden', flex: 1 }}
            >
              <LinearGradient
                colors={[C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={cvStyles.saveBtn}
              >
                {saving
                  ? <ActivityIndicator color={C.white} size="small" />
                  : <Text style={cvStyles.saveBtnText}>{editEvent ? 'Save Changes' : 'Create Event'}</Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const cvStyles = StyleSheet.create({
  dayHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 12,
  },
  dayTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.onSurface,
  },
  addBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
  emptyDay: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, paddingTop: 40,
  },
  emptyDayText: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.onSurfaceVariant,
  },
  eventCard: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16, padding: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  eventAccent: {
    width: 4, borderRadius: 2, alignSelf: 'stretch', flexShrink: 0,
  },
  eventTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurface, marginBottom: 2,
  },
  eventMeta: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 11, color: C.onSurfaceVariant,
  },
  eventDesc: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant,
    marginTop: 4, lineHeight: 17,
  },
  // Form
  formRoot: { flex: 1, backgroundColor: C.bg },
  formHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 24, paddingTop: 24, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.outlineVariant,
  },
  formTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.onSurface,
  },
  formBody: { padding: 24 },
  formLabel: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10,
    color: C.onSurfaceVariant, letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 8,
  },
  formInput: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14,
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 15, color: C.onSurface,
    borderWidth: 1, borderColor: C.outlineVariant,
  },
  toggleRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginTop: 20, paddingTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: C.outlineVariant,
  },
  toggleLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurface,
  },
  toggleSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 11, color: C.onSurfaceVariant, marginTop: 2,
  },
  deleteBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginTop: 28, paddingVertical: 12, justifyContent: 'center',
  },
  deleteBtnText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.error,
  },
  calChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 9,
    borderRadius: 20, borderWidth: 1.5,
    borderColor: C.outlineVariant, backgroundColor: C.surfaceContainerLow,
  },
  calChipDot: { width: 8, height: 8, borderRadius: 4 },
  calChipLabel: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.onSurface,
  },
  formErrorBanner: {
    marginHorizontal: 24, marginBottom: 8,
    backgroundColor: C.errorContainer ?? '#FDECEA',
    borderRadius: 10, padding: 12,
  },
  formErrorText: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.error,
  },
  formFooter: {
    padding: 24, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: C.outlineVariant,
  },
  saveBtn: {
    alignItems: 'center', justifyContent: 'center', paddingVertical: 18, borderRadius: 14,
  },
  saveBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.white,
  },
});

// ── Main screen ────────────────────────────────────────────────
export default function CalendarScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const user = useAuthStore((s) => s.user);
  const [activeTab, setActiveTab] = useState<'calendar' | 'connections'>('calendar');

  const [google, setGoogle] = useState<ProviderStatus>({
    connected: false, lastSynced: null, syncing: false,
  });
  const [outlook, setOutlook] = useState<ProviderStatus>({
    connected: false, lastSynced: null, syncing: false,
  });
  const [connectingProvider, setConnectingProvider] = useState<'google' | 'outlook' | null>(null);

  // Calendar picker state
  const [pickerVisible, setPickerVisible] = useState(false);
  const [pickerProvider, setPickerProvider] = useState<PickerProvider | null>(null);

  // Connected calendars (for push_enabled toggles)
  const [connectedCalendars, setConnectedCalendars] = useState<UserCalendar[]>([]);

  // ── Load connected status via dedicated endpoint ──────────────
  const loadStatus = useCallback(() => {
    calendarService.status().then((res) => {
      const data = res.data;
      setGoogle((p) => ({ ...p, connected: data.google.connected }));
      setOutlook((p) => ({ ...p, connected: data.outlook.connected }));
    }).catch(() => {});
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  // ── Load calendar list for push_enabled toggles ───────────────
  const loadCalendars = useCallback(() => {
    api.get<UserCalendar[]>('/api/calendars/')
      .then((res) => setConnectedCalendars(
        (Array.isArray(res.data) ? res.data : []).filter((c) => c.provider !== 'internal')
      ))
      .catch(() => {});
  }, []);

  useEffect(() => { loadCalendars(); }, [loadCalendars]);

  const handleTogglePushEnabled = useCallback(async (cal: UserCalendar) => {
    const newVal = !cal.push_enabled;
    setConnectedCalendars((prev) =>
      prev.map((c) => c.id === cal.id ? { ...c, push_enabled: newVal } : c)
    );
    try {
      await api.patch(`/api/calendars/${cal.id}/`, { push_enabled: newVal });
    } catch {
      setConnectedCalendars((prev) =>
        prev.map((c) => c.id === cal.id ? { ...c, push_enabled: !newVal } : c)
      );
      Alert.alert('Error', 'Could not update calendar setting. Please try again.');
    }
  }, []);

  // ── OAuth connect flow (Google) ───────────────────────────────
  const handleGoogleToggle = useCallback(async (val: boolean) => {
    if (!val) {
      setGoogle((p) => ({ ...p, connected: false }));
      return;
    }
    setConnectingProvider('google');
    try {
      const res = await calendarService.googleAuthUrl();
      const url = res.data.auth_url;
      // openAuthSessionAsync intercepts the choresync:// deep-link redirect
      const result = await WebBrowser.openAuthSessionAsync(url, 'choresync://');
      if (result.type === 'success') {
        // Reload real status from the server
        loadStatus();
      }
    } catch {
      Alert.alert('Error', 'Could not fetch the Google auth URL. Please try again.');
    } finally {
      setConnectingProvider(null);
    }
  }, [loadStatus]);

  // ── OAuth connect flow (Outlook) ──────────────────────────────
  const handleOutlookToggle = useCallback(async (val: boolean) => {
    if (!val) {
      setOutlook((p) => ({ ...p, connected: false }));
      return;
    }
    setConnectingProvider('outlook');
    try {
      const res = await calendarService.outlookAuthUrl();
      const url = res.data.auth_url;
      const result = await WebBrowser.openAuthSessionAsync(url, 'choresync://');
      if (result.type === 'success') {
        loadStatus();
      }
    } catch {
      Alert.alert('Error', 'Could not fetch the Outlook auth URL. Please try again.');
    } finally {
      setConnectingProvider(null);
    }
  }, [loadStatus]);

  // ── Sync Google ───────────────────────────────────────────────
  const handleGoogleSync = useCallback(async () => {
    setGoogle((p) => ({ ...p, syncing: true }));
    try {
      await calendarService.googleSync();
      const now = new Date();
      setGoogle((p) => ({
        ...p,
        syncing: false,
        lastSynced: `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`,
      }));
    } catch {
      setGoogle((p) => ({ ...p, syncing: false }));
      Alert.alert('Sync failed', 'Could not sync Google Calendar. Please try again.');
    }
  }, []);

  // ── Sync Outlook ──────────────────────────────────────────────
  const handleOutlookSync = useCallback(async () => {
    setOutlook((p) => ({ ...p, syncing: true }));
    try {
      await calendarService.outlookSync();
      const now = new Date();
      setOutlook((p) => ({
        ...p,
        syncing: false,
        lastSynced: `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`,
      }));
    } catch {
      setOutlook((p) => ({ ...p, syncing: false }));
      Alert.alert('Sync failed', 'Could not sync Outlook Calendar. Please try again.');
    }
  }, []);

  // ── Open calendar picker ──────────────────────────────────────
  const openPicker = useCallback((provider: PickerProvider) => {
    setPickerProvider(provider);
    setPickerVisible(true);
  }, []);

  const handlePickerConfirm = useCallback((_provider: PickerProvider, _items: CalendarRow[], newlyAdded: boolean) => {
    setPickerVisible(false);
    if (newlyAdded) {
      Alert.alert(
        'Sync started',
        'Your calendar is syncing in the background. You\'ll receive a notification when it\'s done.',
        [{ text: 'OK' }],
      );
    }
  }, []);

  // ── Primary connect action ────────────────────────────────────
  const handleConnectCalendar = useCallback(() => {
    Alert.alert(
      'Connect a Calendar',
      'Which calendar would you like to connect?',
      [
        { text: 'Google Calendar',    onPress: () => handleGoogleToggle(true)  },
        { text: 'Microsoft Outlook',  onPress: () => handleOutlookToggle(true) },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  }, [handleGoogleToggle, handleOutlookToggle]);

  const bothConnected = google.connected && outlook.connected;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* Calendar picker modal */}
      <CalendarPickerModal
        visible={pickerVisible}
        provider={pickerProvider}
        onClose={() => setPickerVisible(false)}
        onConfirm={handlePickerConfirm}
      />

      {/* ── Top App Bar ──────────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.stone500 }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>Calendar</Text>
        </View>
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => navigation.navigate('Profile')}
          style={styles.topBarAvatar}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          {user?.avatar_url ? (
            <Image source={{ uri: user.avatar_url }} style={styles.topBarAvatarImg} resizeMode="cover" />
          ) : (
            <Text style={styles.topBarAvatarText}>
              {(user?.first_name?.[0] ?? user?.username?.[0] ?? 'U').toUpperCase()}
            </Text>
          )}
        </TouchableOpacity>
      </View>

      {/* ── Tab bar ──────────────────────────────────── */}
      <View style={styles.tabBar}>
        {(['calendar', 'connections'] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tabItem, activeTab === tab && styles.tabItemActive]}
            onPress={() => setActiveTab(tab)}
            activeOpacity={0.75}
          >
            <Text style={[styles.tabLabel, activeTab === tab && styles.tabLabelActive]}>
              {tab === 'calendar' ? 'Calendar' : 'Connections'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Tab content ──────────────────────────────── */}
      {activeTab === 'calendar' ? (
        <CalendarViewTab insets={insets} />
      ) : (
        <>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 120 },
        ]}
      >

        {/* ── Hero ──────────────────────────────────── */}
        <View style={styles.heroCard}>
          <View style={styles.heroBlob} />
          <View style={styles.heroIconWrap}>
            <Text style={[styles.msIcon, { color: C.primary, fontSize: 44 }]}>calendar_today</Text>
          </View>
          <Text style={styles.heroTitle}>Connect Your Calendar</Text>
          <Text style={styles.heroSubtitle}>
            Sync tasks with your Google or Outlook calendar to keep your life in harmony.
          </Text>
        </View>

        {/* ── Integration Cards ──────────────────────── */}
        <View style={styles.sectionGap}>
          <IntegrationCard
            icon="event"
            name="Google Calendar"
            status={google}
            onToggle={handleGoogleToggle}
            onSync={handleGoogleSync}
            onChooseCalendars={() => openPicker('google')}
            disabled={connectingProvider === 'google'}
          />
          <IntegrationCard
            icon="calendar_month"
            name="Microsoft Outlook"
            status={outlook}
            onToggle={handleOutlookToggle}
            onSync={handleOutlookSync}
            onChooseCalendars={() => openPicker('outlook')}
            disabled={connectingProvider === 'outlook'}
          />
        </View>

        {/* Sync now row (shown when at least one connected) */}
        {(google.connected || outlook.connected) && (
          <View style={styles.syncRow}>
            {google.connected && (
              <TouchableOpacity
                activeOpacity={0.8}
                onPress={handleGoogleSync}
                disabled={google.syncing}
                style={styles.syncChip}
              >
                {google.syncing
                  ? <ActivityIndicator size="small" color={C.secondary} />
                  : <Text style={[styles.msIcon, { color: C.secondary, fontSize: 16 }]}>sync</Text>
                }
                <Text style={styles.syncChipText}>Sync Google</Text>
              </TouchableOpacity>
            )}
            {outlook.connected && (
              <TouchableOpacity
                activeOpacity={0.8}
                onPress={handleOutlookSync}
                disabled={outlook.syncing}
                style={styles.syncChip}
              >
                {outlook.syncing
                  ? <ActivityIndicator size="small" color={C.secondary} />
                  : <Text style={[styles.msIcon, { color: C.secondary, fontSize: 16 }]}>sync</Text>
                }
                <Text style={styles.syncChipText}>Sync Outlook</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* ── Connected Calendars / Push Settings ────── */}
        {connectedCalendars.length > 0 && (
          <View style={styles.pushSection}>
            <Text style={styles.pushSectionTitle}>PUSH SETTINGS</Text>
            {connectedCalendars.map((cal) => (
              <View key={cal.id} style={styles.pushRow}>
                <View style={styles.pushRowInfo}>
                  <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>
                    {cal.provider === 'google' ? 'event' : 'calendar_month'}
                  </Text>
                  <View>
                    <Text style={styles.pushCalName} numberOfLines={1}>{cal.name}</Text>
                    <Text style={styles.pushCalProvider}>
                      {cal.provider === 'google' ? 'Google Calendar' : 'Microsoft Outlook'}
                    </Text>
                  </View>
                </View>
                <View style={styles.pushToggleGroup}>
                  <Text style={styles.pushToggleLabel}>Push updates</Text>
                  <Switch
                    value={cal.push_enabled}
                    onValueChange={() => handleTogglePushEnabled(cal)}
                    trackColor={{ false: C.surfaceContainerHighest, true: C.secondaryContainer }}
                    thumbColor={cal.push_enabled ? C.secondary : C.onSurfaceVariant}
                  />
                </View>
              </View>
            ))}
          </View>
        )}

        {/* ── How It Works ───────────────────────────── */}
        <View style={styles.howItWorksSection}>
          <Text style={styles.howItWorksTitle}>How it works</Text>
          <View style={styles.stepsRow}>
            {HOW_IT_WORKS.map((s) => (
              <StepCard key={s.step} {...s} />
            ))}
          </View>
        </View>

      </ScrollView>

      {/* ── Bottom CTA ─────────────────────────────────── */}
      {!bothConnected && (
        <View style={[styles.bottomCta, { paddingBottom: insets.bottom + 16 }]}>
          <TouchableOpacity
            activeOpacity={0.88}
            onPress={handleConnectCalendar}
            disabled={connectingProvider !== null}
            style={{ borderRadius: 16, overflow: 'hidden' }}
          >
            <LinearGradient
              colors={[C.primary, C.primaryContainer]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.ctaBtn}
            >
              {connectingProvider
                ? <ActivityIndicator color={C.white} size="small" />
                : <Text style={[styles.msIcon, { color: C.white, fontSize: 22 }]}>add_circle</Text>
              }
              <Text style={styles.ctaBtnText}>
                {connectingProvider ? 'Opening…' : 'Connect a Calendar'}
              </Text>
            </LinearGradient>
          </TouchableOpacity>
        </View>
      )}
        </>
      )}
    </View>
  );
}


// ── Picker styles ──────────────────────────────────────────────
const pickerStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 24, paddingTop: 24, paddingBottom: 8,
  },
  title: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.onSurface },
  closeBtn: { padding: 4 },
  subtitle: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13,
    color: C.onSurfaceVariant, paddingHorizontal: 24, paddingBottom: 16,
  },
  list: { paddingHorizontal: 24, gap: 12, paddingBottom: 24 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: C.surfaceContainerLowest, borderRadius: 16,
    padding: 16,
  },
  dot: { width: 14, height: 14, borderRadius: 7, flexShrink: 0 },
  rowInfo: { flex: 1, gap: 4 },
  rowNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  rowName: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurface },
  syncingBadge: {
    backgroundColor: C.secondaryContainer,
    paddingHorizontal: 7, paddingVertical: 2, borderRadius: 999,
  },
  syncingBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9,
    color: C.onSecondaryContainer, letterSpacing: 0.8,
  },
  writebackRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  radioOuter: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 2, borderColor: C.outlineVariant,
    alignItems: 'center', justifyContent: 'center',
  },
  radioInner: {
    width: 9, height: 9, borderRadius: 5, backgroundColor: C.primary,
  },
  writebackLabel: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant,
  },
  switchWrap: { alignItems: 'center', gap: 2 },
  switchLabel: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 10, color: C.onSurfaceVariant,
  },
  footer: { paddingHorizontal: 24, paddingVertical: 16 },
  confirmBtn: {
    alignItems: 'center', justifyContent: 'center',
    paddingVertical: 18, borderRadius: 14,
  },
  confirmBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.white,
  },
});

// ── Screen styles ──────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },

  // Top bar
  topBar: {
    height: 56, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', paddingHorizontal: 20, backgroundColor: C.bg,
  },
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  topBarBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.primary, letterSpacing: -0.4,
  },
  topBarAvatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
    borderWidth: 2, borderColor: C.surfaceContainerHigh,
  },
  topBarAvatarImg: { width: 36, height: 36, borderRadius: 18 },
  topBarAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurfaceVariant,
  },

  // Tab bar
  tabBar: {
    flexDirection: 'row',
    backgroundColor: C.bg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.outlineVariant,
    paddingHorizontal: 20,
  },
  tabItem: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabItemActive: {
    borderBottomColor: C.primary,
  },
  tabLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 14,
    color: C.onSurfaceVariant,
  },
  tabLabelActive: {
    color: C.primary,
  },

  // Scroll
  scrollContent: { paddingHorizontal: 24, paddingTop: 8, gap: 24 },

  // Hero card
  heroCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 24, padding: 36,
    alignItems: 'center', overflow: 'hidden', gap: 14,
  },
  heroBlob: {
    position: 'absolute', top: -48, right: -48,
    width: 192, height: 192, borderRadius: 96,
    backgroundColor: `${C.primary}0d`,
  },
  heroIconWrap: {
    width: 96, height: 96,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  heroTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 28,
    color: C.onSurface, letterSpacing: -0.5, textAlign: 'center', lineHeight: 34,
  },
  heroSubtitle: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 15,
    color: C.onSurfaceVariant, textAlign: 'center', lineHeight: 22, maxWidth: 280,
  },

  // Integration section gap
  sectionGap: { gap: 12 },

  // Integration card
  integrationCard: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20, padding: 20,
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', gap: 12,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05, shadowRadius: 6, elevation: 1,
  },
  integrationLeft: { flexDirection: 'row', alignItems: 'center', gap: 16, flex: 1 },
  integrationIconCircle: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: C.surfaceContainerLow,
    alignItems: 'center', justifyContent: 'center',
  },
  integrationInfo: { flex: 1, gap: 3 },
  integrationNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  integrationName: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.onSurface,
  },
  connectedBadge: {
    backgroundColor: C.secondaryContainer,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999,
  },
  connectedBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9,
    color: C.onSecondaryContainer, letterSpacing: 0.8,
  },
  integrationSubtitle: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant,
  },
  chooseCalendarsLink: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 13, color: C.primary,
    textDecorationLine: 'underline', marginTop: 2,
  },

  // Sync chips
  syncRow: {
    flexDirection: 'row', gap: 10, flexWrap: 'wrap',
  },
  syncChip: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: C.secondaryContainer,
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: 999,
  },
  syncChipText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 12, color: C.onSecondaryContainer,
  },

  // Push settings
  pushSection: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16,
    padding: 16,
    gap: 10,
  },
  pushSectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 1,
    color: C.onSurfaceVariant,
    marginBottom: 4,
  },
  pushRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: C.surfaceContainer,
    borderRadius: 12,
    padding: 12,
  },
  pushRowInfo: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  pushCalName: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: C.onSurface,
    maxWidth: 160,
  },
  pushCalProvider: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
    marginTop: 1,
  },
  pushToggleGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pushToggleLabel: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
  },

  // How it works
  howItWorksSection: { gap: 20, paddingTop: 8 },
  howItWorksTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 22, color: C.onSurface,
    letterSpacing: -0.3, paddingHorizontal: 2,
  },
  stepsRow: { gap: 20 },

  // Step card
  stepCard: { gap: 10 },
  stepNum: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center',
  },
  stepNumText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 20, color: C.primary,
  },
  stepIconRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface,
  },
  stepBody: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13,
    color: C.onSurfaceVariant, lineHeight: 20,
  },

  // Bottom CTA
  bottomCta: {
    paddingHorizontal: 24, paddingTop: 12,
    backgroundColor: C.bg,
  },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 10, paddingVertical: 20, borderRadius: 16,
  },
  ctaBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.white,
  },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
