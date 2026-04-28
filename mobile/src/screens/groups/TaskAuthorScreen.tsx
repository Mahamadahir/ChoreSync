/**
 * TaskAuthorScreen — create or edit a task template.
 *
 * Route params:
 *   groupId    — the group this template belongs to (required)
 *   templateId — if provided, load the existing template and PATCH on save;
 *                if omitted, POST a new template on save
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { groupService } from '../../services/groupService';
import type { GroupsStackParamList } from '../../navigation/types';
import { Palette as C } from '../../theme';

type Nav   = NativeStackNavigationProp<GroupsStackParamList, 'TaskAuthor'>;
type Route = RouteProp<GroupsStackParamList, 'TaskAuthor'>;

// ── Option lists ───────────────────────────────────────────────
const CATEGORIES = ['cleaning', 'cooking', 'laundry', 'maintenance', 'other'] as const;
const RECUR_OPTIONS = [
  { value: 'none',        label: 'No repeat'      },
  { value: 'weekly',      label: 'Weekly'          },
  { value: 'monthly',     label: 'Monthly'         },
  { value: 'every_n_days', label: 'Every N days'   },
  { value: 'custom',      label: 'Custom days'     },
] as const;
const DAYS_OF_WEEK = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

type RecurChoice = (typeof RECUR_OPTIONS)[number]['value'];

// ── Pill selector ──────────────────────────────────────────────
function PillSelector<T extends string>({
  options,
  value,
  onChange,
  labelFn,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  labelFn?: (v: T) => string;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 2 }}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <TouchableOpacity
            key={opt}
            activeOpacity={0.7}
            onPress={() => onChange(opt)}
            style={[styles.pill, active && styles.pillActive]}
          >
            <Text style={[styles.pillText, active && styles.pillTextActive]}>
              {labelFn ? labelFn(opt) : opt.charAt(0).toUpperCase() + opt.slice(1)}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

// ── Day toggle row ─────────────────────────────────────────────
function DayToggleRow({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (days: string[]) => void;
}) {
  function toggle(d: string) {
    onChange(
      selected.includes(d) ? selected.filter((x) => x !== d) : [...selected, d],
    );
  }
  return (
    <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
      {DAYS_OF_WEEK.map((d) => {
        const active = selected.includes(d);
        return (
          <TouchableOpacity
            key={d}
            activeOpacity={0.7}
            onPress={() => toggle(d)}
            style={[styles.dayChip, active && styles.dayChipActive]}
          >
            <Text style={[styles.dayChipText, active && styles.dayChipTextActive]}>
              {d.charAt(0).toUpperCase() + d.slice(1)}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

// ── Field wrapper ──────────────────────────────────────────────
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────
export default function TaskAuthorScreen() {
  const insets  = useSafeAreaInsets();
  const navigation = useNavigation<Nav>();
  const route   = useRoute<Route>();
  const { groupId, templateId } = route.params;
  const isEdit  = templateId !== undefined;

  // ── Form state ────────────────────────────────────────────
  const [name,        setName]        = useState('');
  const [details,     setDetails]     = useState('');
  const [category,    setCategory]    = useState<(typeof CATEGORIES)[number]>('other');
  const [recurChoice, setRecurChoice] = useState<RecurChoice>('none');
  const [daysOfWeek,  setDaysOfWeek]  = useState<string[]>([]);
  const [recurValue,  setRecurValue]  = useState('');   // for every_n_days
  const [estimatedMins, setEstimatedMins] = useState('30');
  const [difficulty,  setDifficulty]  = useState('1');  // 1–5
  const [nextDueDate, setNextDueDate] = useState('');   // YYYY-MM-DD
  const [nextDueTime, setNextDueTime] = useState('09:00'); // HH:MM
  const [photoProof,  setPhotoProof]  = useState(false);

  const [loading,  setLoading]  = useState(isEdit);
  const [saving,   setSaving]   = useState(false);

  // ── Load existing template on edit ────────────────────────
  useEffect(() => {
    if (!isEdit) return;
    groupService.getTemplate(templateId!).then((res) => {
      const t = res.data;
      setName(t.name ?? '');
      setDetails(t.details ?? '');
      setCategory(t.category ?? 'other');
      setRecurChoice(t.recurring_choice ?? 'none');
      setDaysOfWeek(t.days_of_week ?? []);
      setRecurValue(t.recur_value != null ? String(t.recur_value) : '');
      setEstimatedMins(t.estimated_mins != null ? String(t.estimated_mins) : '30');
      setDifficulty(t.difficulty != null ? String(t.difficulty) : '1');
      setPhotoProof(t.photo_proof_required ?? false);
      if (t.next_due) {
        const d = new Date(t.next_due);
        setNextDueDate(d.toISOString().slice(0, 10));
        setNextDueTime(d.toTimeString().slice(0, 5));
      }
    }).catch(() => {
      Alert.alert('Error', 'Could not load template.');
      navigation.goBack();
    }).finally(() => setLoading(false));
  }, [isEdit, templateId]);

  // ── Validation ─────────────────────────────────────────────
  function validate(): string | null {
    if (!name.trim()) return 'Task name is required.';
    if (!nextDueDate) return 'First due date is required.';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(nextDueDate)) return 'Date must be YYYY-MM-DD.';
    if (!/^\d{2}:\d{2}$/.test(nextDueTime)) return 'Time must be HH:MM.';
    if (recurChoice === 'every_n_days') {
      const n = parseInt(recurValue, 10);
      if (!recurValue || isNaN(n) || n < 1) return 'Enter a valid number of days (≥ 1).';
    }
    if (recurChoice === 'custom' && daysOfWeek.length === 0) return 'Select at least one day.';
    const mins = parseInt(estimatedMins, 10);
    if (isNaN(mins) || mins < 1) return 'Estimated minutes must be ≥ 1.';
    const diff = parseInt(difficulty, 10);
    if (isNaN(diff) || diff < 1 || diff > 5) return 'Difficulty must be 1–5.';
    return null;
  }

  // ── Save ───────────────────────────────────────────────────
  async function handleSave() {
    const err = validate();
    if (err) { Alert.alert('Invalid input', err); return; }

    const next_due = new Date(`${nextDueDate}T${nextDueTime}:00`).toISOString();
    const payload: Record<string, unknown> = {
      name: name.trim(),
      details: details.trim() || null,
      category,
      recurring_choice: recurChoice,
      days_of_week: recurChoice === 'custom' ? daysOfWeek : null,
      recur_value: recurChoice === 'every_n_days' ? parseInt(recurValue, 10) : null,
      estimated_mins: parseInt(estimatedMins, 10),
      difficulty: parseInt(difficulty, 10),
      next_due,
      photo_proof_required: photoProof,
    };

    setSaving(true);
    try {
      if (isEdit) {
        await groupService.updateTemplate(templateId!, payload);
        Alert.alert('Saved', 'Recurring task updated.');
      } else {
        const res = await groupService.createTemplate(groupId, payload);
        const warn = res.data?.generation_warning;
        if (warn) {
          Alert.alert('Created', warn);
        } else {
          Alert.alert('Created', 'Recurring task created successfully.');
        }
      }
      navigation.goBack();
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? 'Could not save the template. Please try again.';
      Alert.alert('Error', detail);
    } finally {
      setSaving(false);
    }
  }

  // ── Delete ─────────────────────────────────────────────────
  function handleDelete() {
    Alert.alert(
      'Delete recurring task',
      'This will deactivate this recurring task and cancel all pending tasks. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await groupService.deleteTemplate(templateId!);
              navigation.goBack();
            } catch {
              Alert.alert('Error', 'Could not delete the template.');
            }
          },
        },
      ],
    );
  }

  if (loading) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      {/* ── Top bar ──────────────────────────────── */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
          <Text style={[styles.msIcon, { color: C.stone500 }]}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={styles.topBarTitle}>{isEdit ? 'Edit Task' : 'New Task'}</Text>
        {isEdit ? (
          <TouchableOpacity onPress={handleDelete} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
            <Text style={[styles.msIcon, { color: C.error, fontSize: 22 }]}>delete</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 34 }} />
        )}
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.top + 56}
      >
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 120 }]}
          keyboardShouldPersistTaps="handled"
        >

          {/* ── Name ─────────────────────────────── */}
          <Field label="TASK NAME *">
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="e.g. Vacuum living room"
              placeholderTextColor={C.outline}
              returnKeyType="next"
              maxLength={120}
            />
          </Field>

          {/* ── Details ──────────────────────────── */}
          <Field label="DETAILS (OPTIONAL)">
            <TextInput
              style={[styles.input, styles.inputMulti]}
              value={details}
              onChangeText={setDetails}
              placeholder="Any extra instructions for whoever gets assigned…"
              placeholderTextColor={C.outline}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
          </Field>

          {/* ── Category ─────────────────────────── */}
          <Field label="CATEGORY">
            <PillSelector
              options={CATEGORIES}
              value={category}
              onChange={setCategory}
              labelFn={(v) => v.charAt(0).toUpperCase() + v.slice(1)}
            />
          </Field>

          {/* ── Recurrence ───────────────────────── */}
          <Field label="RECURRENCE">
            <PillSelector
              options={RECUR_OPTIONS.map((o) => o.value) as unknown as readonly RecurChoice[]}
              value={recurChoice}
              onChange={setRecurChoice}
              labelFn={(v) => RECUR_OPTIONS.find((o) => o.value === v)?.label ?? v}
            />
          </Field>

          {recurChoice === 'custom' && (
            <Field label="REPEAT ON">
              <DayToggleRow selected={daysOfWeek} onChange={setDaysOfWeek} />
            </Field>
          )}

          {recurChoice === 'every_n_days' && (
            <Field label="EVERY N DAYS">
              <TextInput
                style={[styles.input, styles.inputNarrow]}
                value={recurValue}
                onChangeText={setRecurValue}
                keyboardType="number-pad"
                placeholder="e.g. 3"
                placeholderTextColor={C.outline}
                maxLength={4}
              />
            </Field>
          )}

          {/* ── First due ────────────────────────── */}
          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <Field label="FIRST DUE DATE *">
                <TextInput
                  style={styles.input}
                  value={nextDueDate}
                  onChangeText={setNextDueDate}
                  placeholder="YYYY-MM-DD"
                  placeholderTextColor={C.outline}
                  keyboardType="numbers-and-punctuation"
                  maxLength={10}
                />
              </Field>
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Field label="DUE TIME *">
                <TextInput
                  style={styles.input}
                  value={nextDueTime}
                  onChangeText={setNextDueTime}
                  placeholder="HH:MM"
                  placeholderTextColor={C.outline}
                  keyboardType="numbers-and-punctuation"
                  maxLength={5}
                />
              </Field>
            </View>
          </View>

          {/* ── Estimated time + Difficulty ─────── */}
          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <Field label="EST. MINUTES">
                <TextInput
                  style={styles.input}
                  value={estimatedMins}
                  onChangeText={setEstimatedMins}
                  keyboardType="number-pad"
                  placeholder="30"
                  placeholderTextColor={C.outline}
                  maxLength={4}
                />
              </Field>
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Field label="DIFFICULTY (1–5)">
                <TextInput
                  style={styles.input}
                  value={difficulty}
                  onChangeText={setDifficulty}
                  keyboardType="number-pad"
                  placeholder="1"
                  placeholderTextColor={C.outline}
                  maxLength={1}
                />
              </Field>
            </View>
          </View>

          {/* ── Photo proof ──────────────────────── */}
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.switchLabel}>Photo proof required</Text>
              <Text style={styles.switchSub}>Assignee must upload a photo to mark complete</Text>
            </View>
            <Switch
              value={photoProof}
              onValueChange={setPhotoProof}
              trackColor={{ false: C.surfaceContainerHighest, true: C.secondary }}
              thumbColor={C.white}
              ios_backgroundColor={C.surfaceContainerHighest}
            />
          </View>

        </ScrollView>
      </KeyboardAvoidingView>

      {/* ── Save button ──────────────────────────── */}
      <View style={[styles.footer, { paddingBottom: insets.bottom + 16 }]}>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={handleSave}
          disabled={saving}
          style={styles.saveBtn}
        >
          {saving
            ? <ActivityIndicator color={C.white} size="small" />
            : <Text style={styles.saveBtnText}>{isEdit ? 'Save changes' : 'Create task'}</Text>
          }
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },

  // Top bar
  topBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.outlineVariant,
    backgroundColor: C.bg,
  },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 17,
    color: C.onSurface,
  },
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
    color: C.onSurface,
  },

  // Scroll
  scroll: {
    padding: 20,
    gap: 20,
  },

  // Fields
  field: {
    gap: 8,
  },
  fieldLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 1.2,
    color: C.onSurfaceVariant,
  },
  input: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 13,
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 15,
    color: C.onSurface,
    borderWidth: 1,
    borderColor: C.outlineVariant,
  },
  inputMulti: {
    minHeight: 80,
    paddingTop: 13,
  },
  inputNarrow: {
    maxWidth: 120,
  },

  // Row layout
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },

  // Pills
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: C.surfaceContainerLow,
    borderWidth: 1,
    borderColor: C.outlineVariant,
  },
  pillActive: {
    backgroundColor: C.primaryFixed,
    borderColor: C.primary,
  },
  pillText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },
  pillTextActive: {
    color: C.primary,
  },

  // Day chips
  dayChip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: C.surfaceContainerLow,
    borderWidth: 1,
    borderColor: C.outlineVariant,
  },
  dayChipActive: {
    backgroundColor: C.secondaryContainer,
    borderColor: C.secondary,
  },
  dayChipText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: C.onSurfaceVariant,
  },
  dayChipTextActive: {
    color: C.secondary,
  },

  // Switch row
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: C.outlineVariant,
    gap: 12,
  },
  switchLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 14,
    color: C.onSurface,
    marginBottom: 2,
  },
  switchSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurfaceVariant,
    lineHeight: 17,
  },

  // Footer save button
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
    backgroundColor: C.bg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.outlineVariant,
  },
  saveBtn: {
    backgroundColor: C.primary,
    borderRadius: 14,
    paddingVertical: 17,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22,
    shadowRadius: 8,
    elevation: 4,
  },
  saveBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16,
    color: C.white,
  },
});
