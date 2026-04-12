import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Modal,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import { groupService } from '../../services/groupService';
import type { ProposalsScreenProps } from '../../navigation/types';
import { Palette as C } from '../../theme';

// ── Types ─────────────────────────────────────────────────────────────

interface ProposedPayload {
  name?: string;
  category?: string;
  recurring_choice?: string;
  recur_value?: number;
  difficulty?: number;
  estimated_mins?: number;
  next_due?: string;
  details?: string;
}

interface PayloadDiff {
  [key: string]: { from: unknown; to: unknown };
}

interface Proposal {
  id: number;
  state: 'pending' | 'approved' | 'rejected' | 'expired';
  reason: string;
  proposed_payload: ProposedPayload;
  approved_payload: ProposedPayload | null;
  payload_diff: PayloadDiff;
  approval_note: string;
  approved_at: string | null;
  approved_by: string | null;
  created_at: string;
  proposed_by: string;
  proposed_by_id: string | null;
  task_template_id: number | null;
  task_template_name: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diff = d.getTime() - now.getTime();
  if (diff < 0) return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

function stateColor(state: Proposal['state']): { bg: string; fg: string } {
  switch (state) {
    case 'approved': return { bg: C.secondaryContainer, fg: C.onSecondaryContainer };
    case 'rejected': return { bg: C.errorContainer,     fg: C.error };
    case 'expired':  return { bg: C.surfaceContainerHighest, fg: C.stone500 };
    default:         return { bg: C.primaryFixed,       fg: C.primary };
  }
}

function localDatetimeToIso(dt: string): string {
  // datetime-local gives "YYYY-MM-DDTHH:MM" — treat as UTC
  return dt.length === 16 ? dt + ':00Z' : dt;
}

function isoToLocalDatetime(iso: string | undefined): string {
  if (!iso) return '';
  return iso.substring(0, 16);
}

// ── Diff display ──────────────────────────────────────────────────────

function DiffBlock({ diff, note }: { diff: PayloadDiff; note: string }) {
  const keys = Object.keys(diff);
  if (keys.length === 0 && !note) return null;
  return (
    <View style={diffStyles.wrap}>
      {keys.length > 0 && (
        <>
          <Text style={diffStyles.label}>Moderator adjusted:</Text>
          {keys.map((k) => (
            <Text key={k} style={diffStyles.row}>
              <Text style={diffStyles.field}>{k}: </Text>
              <Text style={diffStyles.from}>{String(diff[k].from)}</Text>
              <Text style={diffStyles.arrow}> → </Text>
              <Text style={diffStyles.to}>{String(diff[k].to)}</Text>
            </Text>
          ))}
        </>
      )}
      {!!note && <Text style={diffStyles.noteText}>"{note}"</Text>}
    </View>
  );
}

const diffStyles = StyleSheet.create({
  wrap: {
    backgroundColor: C.surfaceContainer,
    borderRadius: 10, padding: 10, gap: 4, marginTop: 4,
  },
  label: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 11, color: C.onSurfaceVariant, letterSpacing: 0.5 },
  row: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurface },
  field: { fontFamily: 'PlusJakartaSans-SemiBold' },
  from: { color: C.error, textDecorationLine: 'line-through' },
  arrow: { color: C.onSurfaceVariant },
  to: { color: C.secondary },
  noteText: { fontFamily: 'PlusJakartaSans-RegularItalic', fontSize: 12, color: C.onSurfaceVariant, marginTop: 2 },
});

// ── Proposal card ─────────────────────────────────────────────────────

function ProposalCard({
  proposal,
  isModerator,
  onApprove,
  onReject,
  acting,
}: {
  proposal: Proposal;
  isModerator: boolean;
  onApprove: () => void;
  onReject: () => void;
  acting: boolean;
}) {
  const sc = stateColor(proposal.state);
  const isPending = proposal.state === 'pending';
  const pp = proposal.proposed_payload;

  return (
    <View style={cardStyles.card}>
      {/* Header */}
      <View style={cardStyles.header}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={cardStyles.title} numberOfLines={2}>
            {pp.name ?? `Proposal #${proposal.id}`}
          </Text>
          <Text style={cardStyles.meta}>
            By {proposal.proposed_by} · {formatDate(proposal.created_at)}
          </Text>
        </View>
        <View style={[cardStyles.badge, { backgroundColor: sc.bg }]}>
          <Text style={[cardStyles.badgeText, { color: sc.fg }]}>{proposal.state.toUpperCase()}</Text>
        </View>
      </View>

      {/* Tags */}
      <View style={cardStyles.tagRow}>
        {!!pp.category && <View style={cardStyles.tag}><Text style={cardStyles.tagText}>{pp.category}</Text></View>}
        {!!pp.recurring_choice && <View style={cardStyles.tag}><Text style={cardStyles.tagText}>{pp.recurring_choice}</Text></View>}
        {pp.recurring_choice === 'every_n_days' && !!pp.recur_value && (
          <View style={cardStyles.tag}><Text style={cardStyles.tagText}>every {pp.recur_value}d</Text></View>
        )}
        {!!pp.estimated_mins && <View style={cardStyles.tag}><Text style={cardStyles.tagText}>~{pp.estimated_mins}min</Text></View>}
      </View>

      {/* Reason */}
      {!!proposal.reason && (
        <Text style={cardStyles.reason}>"{proposal.reason}"</Text>
      )}

      {/* Diff */}
      <DiffBlock diff={proposal.payload_diff ?? {}} note={proposal.approval_note} />

      {/* Approved/rejected info */}
      {!isPending && !!proposal.approved_by && (
        <Text style={cardStyles.meta} numberOfLines={1}>
          {proposal.state === 'approved' ? 'Approved' : 'Declined'} by {proposal.approved_by}
          {proposal.approved_at ? ` · ${formatDate(proposal.approved_at)}` : ''}
        </Text>
      )}

      {/* Moderator actions */}
      {isPending && isModerator && (
        <View style={cardStyles.actionsRow}>
          <TouchableOpacity
            activeOpacity={0.8}
            disabled={acting}
            onPress={onApprove}
            style={[cardStyles.actionBtn, cardStyles.approveBtn]}
          >
            {acting
              ? <ActivityIndicator color={C.white} size="small" />
              : <Text style={[cardStyles.actionBtnText, { color: C.white }]}>Approve</Text>
            }
          </TouchableOpacity>
          <TouchableOpacity
            activeOpacity={0.8}
            disabled={acting}
            onPress={onReject}
            style={[cardStyles.actionBtn, cardStyles.rejectBtn]}
          >
            <Text style={[cardStyles.actionBtnText, { color: C.error }]}>Decline</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20, padding: 18, gap: 10,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04, shadowRadius: 16, elevation: 2,
    borderWidth: StyleSheet.hairlineWidth, borderColor: `${C.outlineVariant}26`,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  title: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface, lineHeight: 21 },
  meta: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 11, color: C.onSurfaceVariant },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, flexShrink: 0 },
  badgeText: { fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 10, letterSpacing: 1 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  tag: {
    backgroundColor: C.surfaceContainer, borderRadius: 999,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  tagText: { fontFamily: 'PlusJakartaSans-Medium', fontSize: 11, color: C.onSurfaceVariant },
  reason: { fontFamily: 'PlusJakartaSans-RegularItalic', fontSize: 13, color: C.onSurfaceVariant },
  actionsRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  actionBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5,
    alignItems: 'center', justifyContent: 'center',
  },
  approveBtn: { backgroundColor: C.primary, borderColor: C.primary },
  rejectBtn: { borderColor: C.error, backgroundColor: `${C.errorContainer}40` },
  actionBtnText: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13 },
});

// ── Suggestion sheet (full-payload form) ──────────────────────────────

interface SuggestForm {
  name: string; category: string; recurring_choice: string;
  recur_value: string; difficulty: string; estimated_mins: string;
  next_due: string; due_time: string; reason: string;
}

function SuggestSheet({
  visible,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  onClose: () => void;
  onSubmit: (form: SuggestForm) => Promise<void>;
}) {
  const slideAnim = useRef(new Animated.Value(700)).current;
  const [form, setForm] = useState<SuggestForm>({
    name: '', category: 'other', recurring_choice: 'none',
    recur_value: '3', difficulty: '1', estimated_mins: '30', next_due: '', due_time: '09:00', reason: '',
  });
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    if (visible) {
      setForm({ name: '', category: 'other', recurring_choice: 'none', recur_value: '3', difficulty: '1', estimated_mins: '30', next_due: '', due_time: '09:00', reason: '' });
      setLocalError('');
      Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 80, friction: 12 }).start();
    } else {
      Animated.timing(slideAnim, { toValue: 700, duration: 200, useNativeDriver: true }).start();
    }
  }, [visible]);

  function set(field: keyof SuggestForm, val: string) {
    setForm(f => ({ ...f, [field]: val }));
  }

  async function handleSubmit() {
    if (!form.name.trim()) { setLocalError('Task name is required.'); return; }
    if (!form.next_due) { setLocalError('Start date is required.'); return; }
    setLocalError('');
    setLoading(true);
    try {
      await onSubmit(form);
      onClose();
    } catch (e: any) {
      setLocalError(e?.response?.data?.detail ?? 'Failed to submit.');
    } finally {
      setLoading(false);
    }
  }

  const CATEGORIES = ['cleaning', 'cooking', 'laundry', 'maintenance', 'other'];
  const RECURRENCES = ['none', 'weekly', 'monthly', 'every_n_days'];

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <TouchableOpacity style={sheetStyles.backdrop} activeOpacity={1} onPress={onClose} />
      <Animated.View style={[sheetStyles.sheet, { transform: [{ translateY: slideAnim }] }]}>
        <View style={sheetStyles.handle} />
        <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <Text style={sheetStyles.title}>Suggest a Task</Text>
          <Text style={sheetStyles.sub}>A moderator will review your suggestion.</Text>

          <Text style={sheetStyles.label}>Task Name *</Text>
          <TextInput style={sheetStyles.input} value={form.name} onChangeText={v => set('name', v)} placeholder="e.g. Take out bins" placeholderTextColor={`${C.onSurfaceVariant}60`} />

          <Text style={sheetStyles.label}>Category</Text>
          <View style={sheetStyles.chipRow}>
            {CATEGORIES.map(c => (
              <TouchableOpacity key={c} activeOpacity={0.8} onPress={() => set('category', c)}
                style={[sheetStyles.chip, form.category === c && sheetStyles.chipActive]}>
                <Text style={[sheetStyles.chipText, form.category === c && sheetStyles.chipTextActive]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={sheetStyles.label}>Recurrence</Text>
          <View style={sheetStyles.chipRow}>
            {RECURRENCES.map(r => (
              <TouchableOpacity key={r} activeOpacity={0.8} onPress={() => set('recurring_choice', r)}
                style={[sheetStyles.chip, form.recurring_choice === r && sheetStyles.chipActive]}>
                <Text style={[sheetStyles.chipText, form.recurring_choice === r && sheetStyles.chipTextActive]}>{r}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {form.recurring_choice === 'every_n_days' && (
            <>
              <Text style={sheetStyles.label}>Every N Days</Text>
              <TextInput style={sheetStyles.input} value={form.recur_value} onChangeText={v => set('recur_value', v)} keyboardType="number-pad" />
            </>
          )}

          <View style={{ flexDirection: 'row', gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Text style={sheetStyles.label}>Difficulty (1–5)</Text>
              <TextInput style={sheetStyles.input} value={form.difficulty} onChangeText={v => set('difficulty', v)} keyboardType="number-pad" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={sheetStyles.label}>Est. Minutes</Text>
              <TextInput style={sheetStyles.input} value={form.estimated_mins} onChangeText={v => set('estimated_mins', v)} keyboardType="number-pad" />
            </View>
          </View>

          <Text style={sheetStyles.label}>{form.recurring_choice === 'none' ? 'Due Date & Time' : 'First Occurrence'}</Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <TextInput
              style={[sheetStyles.input, { flex: 3 }]}
              value={form.next_due}
              onChangeText={v => set('next_due', v)}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={`${C.onSurfaceVariant}60`}
            />
            <TextInput
              style={[sheetStyles.input, { flex: 2 }]}
              value={form.due_time}
              onChangeText={v => set('due_time', v)}
              placeholder="HH:MM"
              placeholderTextColor={`${C.onSurfaceVariant}60`}
              keyboardType="numbers-and-punctuation"
            />
          </View>

          <Text style={sheetStyles.label}>Why is this needed? (optional)</Text>
          <TextInput style={[sheetStyles.input, { minHeight: 70 }]} value={form.reason} onChangeText={v => set('reason', v)} multiline textAlignVertical="top" />

          {!!localError && <Text style={sheetStyles.errorText}>{localError}</Text>}

          <TouchableOpacity
            activeOpacity={!form.name.trim() || loading ? 1 : 0.85}
            disabled={!form.name.trim() || loading}
            onPress={handleSubmit}
            style={[sheetStyles.submitBtn, (!form.name.trim() || loading) && { opacity: 0.5 }]}
          >
            {loading ? <ActivityIndicator color={C.white} /> : <Text style={sheetStyles.submitBtnText}>Submit Suggestion</Text>}
          </TouchableOpacity>
        </ScrollView>
      </Animated.View>
    </Modal>
  );
}

// ── Approve sheet (moderator, with optional edits) ─────────────────────

function ApproveSheet({
  visible,
  proposal,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  proposal: Proposal | null;
  onClose: () => void;
  onSubmit: (editedPayload: Record<string, unknown>, note: string) => Promise<void>;
}) {
  const slideAnim = useRef(new Animated.Value(700)).current;
  const pp = proposal?.proposed_payload ?? {};
  const [form, setForm] = useState({ name: '', category: 'other', recurring_choice: 'none', recur_value: '3', difficulty: '1', estimated_mins: '30', next_due: '', due_time: '09:00', approval_note: '' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible && pp) {
      setForm({
        name: pp.name ?? '',
        category: pp.category ?? 'other',
        recurring_choice: pp.recurring_choice ?? 'none',
        recur_value: String(pp.recur_value ?? 3),
        difficulty: String(pp.difficulty ?? 1),
        estimated_mins: String(pp.estimated_mins ?? 30),
        next_due: pp.next_due ? pp.next_due.substring(0, 10) : '',
        due_time: pp.next_due ? pp.next_due.substring(11, 16) || '09:00' : '09:00',
        approval_note: '',
      });
      Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 80, friction: 12 }).start();
    } else {
      Animated.timing(slideAnim, { toValue: 700, duration: 200, useNativeDriver: true }).start();
    }
  }, [visible]);

  function set(field: string, val: string) { setForm(f => ({ ...f, [field]: val })); }

  async function handleApprove() {
    setLoading(true);
    try {
      const editedPayload: Record<string, unknown> = {
        name: form.name.trim(),
        category: form.category,
        recurring_choice: form.recurring_choice,
        difficulty: parseInt(form.difficulty, 10),
        estimated_mins: parseInt(form.estimated_mins, 10),
        next_due: form.next_due
          ? new Date(`${form.next_due}T${form.due_time || '09:00'}:00`).toISOString()
          : undefined,
      };
      if (form.recurring_choice === 'every_n_days') {
        editedPayload.recur_value = parseInt(form.recur_value, 10);
      }
      await onSubmit(editedPayload, form.approval_note);
      onClose();
    } finally {
      setLoading(false);
    }
  }

  const CATEGORIES = ['cleaning', 'cooking', 'laundry', 'maintenance', 'other'];
  const RECURRENCES = ['none', 'weekly', 'monthly', 'every_n_days'];

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <TouchableOpacity style={sheetStyles.backdrop} activeOpacity={1} onPress={onClose} />
      <Animated.View style={[sheetStyles.sheet, { transform: [{ translateY: slideAnim }] }]}>
        <View style={sheetStyles.handle} />
        <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          <Text style={sheetStyles.title}>Approve Suggestion</Text>
          <Text style={sheetStyles.sub}>Edit any fields before approving, or approve as-is.</Text>

          <Text style={sheetStyles.label}>Task Name</Text>
          <TextInput style={sheetStyles.input} value={form.name} onChangeText={v => set('name', v)} />

          <Text style={sheetStyles.label}>Category</Text>
          <View style={sheetStyles.chipRow}>
            {CATEGORIES.map(c => (
              <TouchableOpacity key={c} activeOpacity={0.8} onPress={() => set('category', c)}
                style={[sheetStyles.chip, form.category === c && sheetStyles.chipActive]}>
                <Text style={[sheetStyles.chipText, form.category === c && sheetStyles.chipTextActive]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={sheetStyles.label}>Recurrence</Text>
          <View style={sheetStyles.chipRow}>
            {RECURRENCES.map(r => (
              <TouchableOpacity key={r} activeOpacity={0.8} onPress={() => set('recurring_choice', r)}
                style={[sheetStyles.chip, form.recurring_choice === r && sheetStyles.chipActive]}>
                <Text style={[sheetStyles.chipText, form.recurring_choice === r && sheetStyles.chipTextActive]}>{r}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {form.recurring_choice === 'every_n_days' && (
            <>
              <Text style={sheetStyles.label}>Every N Days</Text>
              <TextInput style={sheetStyles.input} value={form.recur_value} onChangeText={v => set('recur_value', v)} keyboardType="number-pad" />
            </>
          )}

          <View style={{ flexDirection: 'row', gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Text style={sheetStyles.label}>Difficulty</Text>
              <TextInput style={sheetStyles.input} value={form.difficulty} onChangeText={v => set('difficulty', v)} keyboardType="number-pad" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={sheetStyles.label}>Est. Minutes</Text>
              <TextInput style={sheetStyles.input} value={form.estimated_mins} onChangeText={v => set('estimated_mins', v)} keyboardType="number-pad" />
            </View>
          </View>

          <Text style={sheetStyles.label}>First Occurrence</Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <TextInput
              style={[sheetStyles.input, { flex: 3 }]}
              value={form.next_due}
              onChangeText={v => set('next_due', v)}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={`${C.onSurfaceVariant}60`}
            />
            <TextInput
              style={[sheetStyles.input, { flex: 2 }]}
              value={form.due_time}
              onChangeText={v => set('due_time', v)}
              placeholder="HH:MM"
              placeholderTextColor={`${C.onSurfaceVariant}60`}
              keyboardType="numbers-and-punctuation"
            />
          </View>

          <Text style={sheetStyles.label}>Note to proposer (optional)</Text>
          <TextInput style={[sheetStyles.input, { minHeight: 60 }]} value={form.approval_note} onChangeText={v => set('approval_note', v)} multiline textAlignVertical="top" placeholder="e.g. Changed to every 3 days instead of daily" placeholderTextColor={`${C.onSurfaceVariant}60`} />

          <TouchableOpacity
            activeOpacity={loading ? 1 : 0.85}
            disabled={loading}
            onPress={handleApprove}
            style={[sheetStyles.submitBtn, loading && { opacity: 0.6 }]}
          >
            {loading ? <ActivityIndicator color={C.white} /> : <Text style={sheetStyles.submitBtnText}>Approve Task</Text>}
          </TouchableOpacity>
        </ScrollView>
      </Animated.View>
    </Modal>
  );
}

const sheetStyles = StyleSheet.create({
  backdrop: { position: 'absolute', inset: 0, backgroundColor: 'rgba(27,28,26,0.45)' } as any,
  sheet: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: C.surfaceContainerLowest,
    borderTopLeftRadius: 28, borderTopRightRadius: 28,
    padding: 24, paddingBottom: 48, maxHeight: '90%',
  },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: C.outlineVariant, alignSelf: 'center', marginBottom: 16 },
  title: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.onSurface, marginBottom: 4 },
  sub: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.onSurfaceVariant, marginBottom: 16 },
  label: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 11, color: C.onSurfaceVariant, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 12, marginBottom: 4 },
  input: {
    borderWidth: 1.5, borderColor: C.outlineVariant, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 11, marginBottom: 2,
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 14, color: C.onSurface,
    backgroundColor: C.surfaceContainerLow,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, backgroundColor: C.surfaceContainer, borderWidth: 1.5, borderColor: C.outlineVariant },
  chipActive: { backgroundColor: C.primaryFixed, borderColor: C.primary },
  chipText: { fontFamily: 'PlusJakartaSans-Medium', fontSize: 12, color: C.onSurfaceVariant },
  chipTextActive: { color: C.primary, fontFamily: 'PlusJakartaSans-SemiBold' },
  errorText: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.error, marginTop: 8, textAlign: 'center' },
  submitBtn: { marginTop: 16, backgroundColor: C.primary, borderRadius: 14, paddingVertical: 16, alignItems: 'center' },
  submitBtnText: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.white },
});

// ── Main screen ────────────────────────────────────────────────────────

export default function ProposalsScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<ProposalsScreenProps['route']>();
  const { groupId, myRole } = route.params;
  const isModerator = myRole === 'moderator';

  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [acting, setActing] = useState<Record<number, boolean>>({});
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [approveTarget, setApproveTarget] = useState<Proposal | null>(null);
  const [activeFilter, setActiveFilter] = useState<'pending' | 'all'>('pending');

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const res = await groupService.proposals(groupId);
      setProposals(Array.isArray(res.data) ? res.data : (res.data?.results ?? []));
    } catch { /* show empty */ }
    finally { setLoading(false); setRefreshing(false); }
  }, [groupId]);

  useEffect(() => { load(); }, [load]);

  async function handleSuggest(form: SuggestForm) {
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      category: form.category,
      recurring_choice: form.recurring_choice,
      difficulty: parseInt(form.difficulty, 10) || 1,
      estimated_mins: parseInt(form.estimated_mins, 10) || 30,
      next_due: form.next_due
        ? new Date(`${form.next_due}T${form.due_time || '09:00'}:00`).toISOString()
        : undefined,
    };
    if (form.recurring_choice === 'every_n_days') {
      payload.recur_value = parseInt(form.recur_value, 10) || 3;
    }
    await groupService.createProposal(groupId, { payload, reason: form.reason.trim() });
    await load();
  }

  async function handleApprove(proposal: Proposal, editedPayload: Record<string, unknown>, note: string) {
    setActing(a => ({ ...a, [proposal.id]: true }));
    try {
      await groupService.approveProposal(proposal.id, { edited_payload: editedPayload, approval_note: note });
      await load();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not approve.');
    } finally {
      setActing(a => { const n = { ...a }; delete n[proposal.id]; return n; });
    }
  }

  async function handleReject(proposal: Proposal) {
    Alert.prompt(
      'Decline Suggestion',
      'Optional: explain why (the proposer will be notified)',
      async (note) => {
        setActing(a => ({ ...a, [proposal.id]: true }));
        try {
          await groupService.rejectProposal(proposal.id, { note: note ?? '' });
          await load();
        } catch (e: any) {
          Alert.alert('Error', e?.response?.data?.detail ?? 'Could not decline.');
        } finally {
          setActing(a => { const n = { ...a }; delete n[proposal.id]; return n; });
        }
      },
      'plain-text',
      '',
    );
  }

  const filtered = activeFilter === 'pending'
    ? proposals.filter(p => p.state === 'pending')
    : proposals;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* Top bar */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>{isModerator ? 'Pending Approvals' : 'Suggestions'}</Text>
        </View>
        <TouchableOpacity activeOpacity={0.85} onPress={() => setSuggestOpen(true)} style={styles.newBtn}>
          <Text style={[styles.msIcon, { color: C.white, fontSize: 20 }]}>lightbulb</Text>
        </TouchableOpacity>
      </View>

      {/* Filter chips */}
      <View style={styles.filterRow}>
        {(['pending', 'all'] as const).map(f => (
          <TouchableOpacity key={f} activeOpacity={0.8} onPress={() => setActiveFilter(f)}
            style={[styles.filterChip, activeFilter === f && styles.filterChipActive]}>
            <Text style={[styles.filterChipText, activeFilter === f && styles.filterChipTextActive]}>
              {f === 'pending' ? 'Open' : 'All'}
            </Text>
          </TouchableOpacity>
        ))}
        <Text style={styles.countLabel}>{filtered.length} suggestion{filtered.length !== 1 ? 's' : ''}</Text>
      </View>

      {/* Content */}
      {loading ? (
        <View style={styles.loadingWrap}><ActivityIndicator color={C.primary} size="large" /></View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.primary} />}
          contentContainerStyle={[styles.listContent, { paddingBottom: insets.bottom + 32 }]}
        >
          {filtered.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={[styles.msIcon, { fontSize: 52, color: C.outlineVariant }]}>lightbulb</Text>
              <Text style={styles.emptyTitle}>{activeFilter === 'pending' ? 'No open suggestions' : 'No suggestions yet'}</Text>
              <Text style={styles.emptySub}>Tap the lightbulb to suggest a new task for this group.</Text>
              <TouchableOpacity activeOpacity={0.85} onPress={() => setSuggestOpen(true)} style={styles.emptyBtn}>
                <Text style={styles.emptyBtnText}>Suggest a Task</Text>
              </TouchableOpacity>
            </View>
          ) : (
            filtered.map(p => (
              <ProposalCard
                key={p.id}
                proposal={p}
                isModerator={isModerator}
                acting={!!acting[p.id]}
                onApprove={() => setApproveTarget(p)}
                onReject={() => handleReject(p)}
              />
            ))
          )}
        </ScrollView>
      )}

      <SuggestSheet visible={suggestOpen} onClose={() => setSuggestOpen(false)} onSubmit={handleSuggest} />
      <ApproveSheet
        visible={!!approveTarget}
        proposal={approveTarget}
        onClose={() => setApproveTarget(null)}
        onSubmit={(ep, note) => handleApprove(approveTarget!, ep, note)}
      />
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  topBar: { height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, backgroundColor: C.bg },
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  topBarBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  topBarTitle: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.primary, letterSpacing: -0.4 },
  newBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  filterRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingBottom: 14 },
  filterChip: { paddingHorizontal: 18, paddingVertical: 8, borderRadius: 999, backgroundColor: C.surfaceContainer },
  filterChipActive: { backgroundColor: C.primary },
  filterChipText: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13, color: C.onSurfaceVariant },
  filterChipTextActive: { color: C.white },
  countLabel: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.stone500, marginLeft: 'auto' as any },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  listContent: { paddingHorizontal: 20, paddingTop: 4, gap: 16 },
  emptyState: { paddingTop: 60, alignItems: 'center', gap: 12 },
  emptyTitle: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 18, color: C.onSurfaceVariant },
  emptySub: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.stone500, textAlign: 'center', maxWidth: 280, lineHeight: 20 },
  emptyBtn: { marginTop: 8, backgroundColor: C.primary, paddingHorizontal: 28, paddingVertical: 12, borderRadius: 12 },
  emptyBtnText: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.white },
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
