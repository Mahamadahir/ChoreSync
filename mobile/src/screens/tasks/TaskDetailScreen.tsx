import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { taskService } from '../../services/taskService';
import { groupService } from '../../services/groupService';
import BreakdownPanel from '../../components/tasks/BreakdownPanel';
import { useAuthStore } from '../../stores/authStore';
import type { TaskDetailScreenProps } from '../../navigation/types';
import type { TaskOccurrence, TaskStatus } from '../../types/task';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<any>;

// ── Design tokens ─────────────────────────────────────────────

// TaskOccurrence covers all fields; alias for clarity
type TaskDetail = TaskOccurrence;

// ── Status config ─────────────────────────────────────────────
const STATUS_CONFIG: Record<TaskStatus, { label: string; bg: string; fg: string }> = {
  pending:     { label: 'Pending',     bg: C.surfaceContainerHigh,  fg: C.onSurfaceVariant },
  in_progress: { label: 'In Progress', bg: C.secondaryContainer,    fg: C.onSecondaryContainer },
  snoozed:     { label: 'Snoozed',     bg: C.surfaceContainerHigh,  fg: C.onSurfaceVariant },
  completed:   { label: 'Complete',    bg: C.secondary,             fg: C.white },
  overdue:     { label: 'Overdue',     bg: C.errorContainer,        fg: C.onErrorContainer },
  reassigned:  { label: 'Reassigned',  bg: C.primaryFixed,          fg: C.primary },
  suggested:   { label: 'Suggested',   bg: C.primaryFixed,          fg: C.primary },
};

// ── Date formatting ───────────────────────────────────────────
function formatDeadline(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const isTomorrow =
    d.getFullYear() === tomorrow.getFullYear() &&
    d.getMonth() === tomorrow.getMonth() &&
    d.getDate() === tomorrow.getDate();

  const timeStr = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  if (isToday) return `Today, ${timeStr}`;
  if (isTomorrow) return `Tomorrow, ${timeStr}`;
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) + ` · ${timeStr}`;
}

function isOverdue(iso: string): boolean {
  return new Date(iso) < new Date();
}

// ── Assignee initials ─────────────────────────────────────────
function getInitials(task: TaskDetail): string {
  if (!task.assigned_to_id) return '?';
  if (task.assignee_first_name || task.assignee_last_name) {
    return [task.assignee_first_name?.[0], task.assignee_last_name?.[0]]
      .filter(Boolean).join('').toUpperCase();
  }
  return task.assigned_to_username?.[0]?.toUpperCase() ?? '?';
}

function getDisplayName(task: TaskDetail): string {
  if (!task.assigned_to_id) return 'Unassigned';
  if (task.assignee_first_name || task.assignee_last_name) {
    const last = task.assignee_last_name?.[0] ? `${task.assignee_last_name[0]}.` : '';
    return `${task.assignee_first_name ?? ''} ${last}`.trim();
  }
  return task.assigned_to_username ?? '—';
}

// ── Hero gradient colours (cycle by template_id) ──────────────
const HERO_GRADIENTS: [string, string][] = [
  [C.primaryLight, C.primary],
  ['#6b8f60', '#496640'],
  ['#b07a3a', '#7f521f'],
  ['#8fa8a5', '#496640'],
];
function heroGradient(id: number): [string, string] {
  return HERO_GRADIENTS[id % HERO_GRADIENTS.length];
}

// ── Snooze modal ──────────────────────────────────────────────
const SNOOZE_OPTIONS = [
  { label: '1 hour',         offsetH: 1  },
  { label: '4 hours',        offsetH: 4  },
  { label: 'Tomorrow 9 AM',  offsetH: -1 }, // special case
];

function SnoozeModal({
  visible,
  onClose,
  onSnooze,
}: {
  visible: boolean;
  onClose: () => void;
  onSnooze: (isoDate: string) => Promise<void>;
}) {
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(false);

  async function pick(offsetH: number) {
    const now = new Date();
    let target: Date;
    if (offsetH === -1) {
      target = new Date(now);
      target.setDate(target.getDate() + 1);
      target.setHours(9, 0, 0, 0);
    } else {
      target = new Date(now.getTime() + offsetH * 3600 * 1000);
    }
    setLoading(true);
    try {
      await onSnooze(target.toISOString());
      onClose();
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={ss.backdrop} activeOpacity={1} onPress={onClose} />
      <View style={[ss.sheet, { paddingBottom: insets.bottom + 16 }]}>
        <View style={ss.handle} />
        <Text style={ss.sheetTitle}>Snooze until…</Text>
        {SNOOZE_OPTIONS.map((o) => (
          <TouchableOpacity
            key={o.label}
            activeOpacity={0.85}
            onPress={() => pick(o.offsetH)}
            disabled={loading}
            style={ss.snoozeOption}
          >
            <Text style={[ss.msIcon, { color: C.primary, fontSize: 20, marginRight: 12 }]}>schedule</Text>
            <Text style={ss.snoozeOptionText}>{o.label}</Text>
            {loading && <ActivityIndicator size="small" color={C.primary} style={{ marginLeft: 'auto' }} />}
          </TouchableOpacity>
        ))}
      </View>
    </Modal>
  );
}

// ── Swap modal (with member picker) ──────────────────────────
type GroupMember = { user_id: string; username: string };

function SwapModal({
  visible,
  onClose,
  onSwap,
  members,
}: {
  visible: boolean;
  onClose: () => void;
  onSwap: (toUserId: string | null, reason: string) => Promise<void>;
  members: GroupMember[];
}) {
  const insets = useSafeAreaInsets();
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSwap() {
    setLoading(true);
    try {
      await onSwap(selectedUserId, reason.trim());
      setSelectedUserId(null);
      setReason('');
      onClose();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not request swap.');
    } finally {
      setLoading(false);
    }
  }

  const options: GroupMember[] = [
    { user_id: '', username: 'Anyone (open request)' },
    ...members,
  ];

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={ss.backdrop} activeOpacity={1} onPress={onClose} />
      <View style={[ss.sheet, { paddingBottom: insets.bottom + 16 }]}>
        <View style={ss.handle} />
        <Text style={ss.sheetTitle}>Swap Task</Text>
        <Text style={ss.sheetSub}>Choose who to swap with, or leave as an open request.</Text>

        {/* Member picker */}
        <View style={ss.pickerList}>
          {options.map((m) => {
            const selected = (selectedUserId ?? '') === m.user_id;
            return (
              <TouchableOpacity
                key={m.user_id}
                activeOpacity={0.8}
                onPress={() => setSelectedUserId(m.user_id || null)}
                style={[ss.pickerRow, selected && ss.pickerRowSelected]}
              >
                <View style={[ss.pickerAvatar, selected && { backgroundColor: C.primary }]}>
                  <Text style={[ss.pickerAvatarText, selected && { color: C.white }]}>
                    {m.username.slice(0, 2).toUpperCase()}
                  </Text>
                </View>
                <Text style={[ss.pickerName, selected && { color: C.primary, fontFamily: 'PlusJakartaSans-Bold' }]}>
                  {m.username}
                </Text>
                {selected && (
                  <Text style={[ss.msIcon, { color: C.primary, fontSize: 18, marginLeft: 'auto' }]}>check_circle</Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>

        <TextInput
          style={ss.swapInput}
          value={reason}
          onChangeText={setReason}
          placeholder="Reason (optional)..."
          placeholderTextColor={`${C.onSurfaceVariant}70`}
          multiline
          numberOfLines={2}
        />
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={handleSwap}
          disabled={loading}
          style={{ borderRadius: 999, overflow: 'hidden' }}
        >
          <LinearGradient
            colors={[C.primary, C.primaryContainer]}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={ss.actionBtnGradient}
          >
            {loading
              ? <ActivityIndicator color={C.white} size="small" />
              : <Text style={ss.actionBtnText}>Send Swap Request</Text>
            }
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

// ── Marketplace modal (with bonus points + balance) ───────────
function MarketplaceModal({
  visible,
  onClose,
  onList,
  myPoints,
  taskName,
}: {
  visible: boolean;
  onClose: () => void;
  onList: (bonusPoints: number) => Promise<void>;
  myPoints: number;
  taskName: string;
}) {
  const insets = useSafeAreaInsets();
  const [bonusInput, setBonusInput] = useState('0');
  const [loading, setLoading] = useState(false);

  const bonus = Math.max(0, parseInt(bonusInput || '0', 10) || 0);
  const overBalance = bonus > myPoints;

  async function handleList() {
    if (overBalance) return;
    setLoading(true);
    try {
      await onList(bonus);
      setBonusInput('0');
      onClose();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not list task.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={ss.backdrop} activeOpacity={1} onPress={onClose} />
      <View style={[ss.sheet, { paddingBottom: insets.bottom + 16 }]}>
        <View style={ss.handle} />
        <Text style={ss.sheetTitle}>List on Marketplace</Text>
        <Text style={ss.sheetSub}>{taskName}</Text>

        <View style={ss.balanceRow}>
          <Text style={[ss.msIcon, { fontSize: 18, color: C.tertiary }]}>stars</Text>
          <Text style={ss.balanceText}>Your balance: <Text style={{ color: C.tertiary, fontFamily: 'PlusJakartaSans-Bold' }}>{myPoints} pts</Text></Text>
        </View>

        <Text style={ss.inputLabel}>Bonus points to offer (from your balance)</Text>
        <TextInput
          style={[ss.swapInput, { minHeight: 48, marginBottom: 4 }]}
          value={bonusInput}
          onChangeText={(v) => setBonusInput(v.replace(/[^0-9]/g, ''))}
          placeholder="0"
          placeholderTextColor={`${C.onSurfaceVariant}70`}
          keyboardType="number-pad"
        />
        {overBalance && (
          <Text style={ss.balanceError}>⚠ You only have {myPoints} pts</Text>
        )}
        <View style={{ height: 12 }} />
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={handleList}
          disabled={loading || overBalance}
          style={[{ borderRadius: 999, overflow: 'hidden' }, overBalance && { opacity: 0.4 }]}
        >
          <LinearGradient
            colors={[C.primary, C.primaryContainer]}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={ss.actionBtnGradient}
          >
            {loading
              ? <ActivityIndicator color={C.white} size="small" />
              : <Text style={ss.actionBtnText}>List Task{bonus > 0 ? ` (+${bonus} pts)` : ''}</Text>
            }
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function TaskDetailScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<Nav>();
  const route = useRoute<TaskDetailScreenProps['route']>();
  const { taskId } = route.params;
  const currentUser = useAuthStore((s) => s.user);
  const myUserId = String(currentUser?.id ?? '');

  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [acceptingEmergency, setAcceptingEmergency] = useState(false);
  const [triggeringEmergency, setTriggeringEmergency] = useState(false);
  const [prefNudge, setPrefNudge] = useState<{ visible: boolean; templateId: number | null; saving: boolean }>({
    visible: false, templateId: null, saving: false,
  });
  const [showSnooze, setShowSnooze] = useState(false);
  const [showSwap, setShowSwap] = useState(false);
  const [showMarketplace, setShowMarketplace] = useState(false);
  const [groupMembers, setGroupMembers] = useState<GroupMember[]>([]);
  const [myPoints, setMyPoints] = useState(0);
  const [breakdown, setBreakdown] = useState<any>(null);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [breakdownLoading, setBreakdownLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await taskService.getTask(taskId);
      const t = res.data;
      setTask(t);
      // Load group members and leaderboard for swap picker + points balance
      if (t.group_id) {
        const [membersRes, lbRes] = await Promise.allSettled([
          groupService.members(t.group_id),
          groupService.leaderboard(t.group_id),
        ]);
        if (membersRes.status === 'fulfilled') {
          const all = membersRes.value.data.results ?? membersRes.value.data;
          // Exclude self from swap targets
          setGroupMembers(
            all.filter((m: any) => String(m.user_id) !== myUserId)
                .map((m: any) => ({ user_id: String(m.user_id), username: m.username }))
          );
        }
        if (lbRes.status === 'fulfilled') {
          const lb = lbRes.value.data.results ?? lbRes.value.data;
          const me = lb.find((r: any) => String(r.user_id) === myUserId);
          setMyPoints(me?.total_points ?? 0);
        }
      }
    } catch {
      Alert.alert('Error', 'Could not load task details.');
      navigation.goBack();
    } finally {
      setLoading(false);
    }
  }, [taskId, myUserId]);

  useEffect(() => { load(); }, [load]);
  // Re-fetch when navigating back to this screen so emergency status stays current
  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function handleComplete() {
    if (!task) return;
    setCompleting(true);
    try {
      await taskService.complete(task.id);
      setTask((t) => t ? { ...t, status: 'completed' } : t);
      // Show preference nudge after successful completion
      setPrefNudge({ visible: true, templateId: task.template_id, saving: false });
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not complete task.');
    } finally {
      setCompleting(false);
    }
  }

  async function handlePrefNudge(preference: 'prefer' | 'neutral' | 'avoid') {
    if (!prefNudge.templateId) return;
    setPrefNudge((p) => ({ ...p, saving: true }));
    try {
      await groupService.setPreference(prefNudge.templateId, preference);
    } catch {
      // Best-effort — silently ignore failures
    } finally {
      setPrefNudge({ visible: false, templateId: null, saving: false });
    }
  }

  async function handleSnooze(isoDate: string) {
    if (!task) return;
    try {
      await taskService.snooze(task.id, isoDate);
      setTask((t) => t ? { ...t, status: 'snoozed' } : t);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not snooze task.');
    }
  }

  async function handleSwap(toUserId: string | null, reason: string) {
    if (!task) return;
    const payload: { to_user_id?: string; reason?: string } = {};
    if (toUserId) payload.to_user_id = toUserId;
    if (reason) payload.reason = reason;
    await taskService.createSwap(task.id, payload);
    Alert.alert('Swap Requested', toUserId ? 'Your swap request has been sent.' : 'Posted as an open request to the group.');
  }

  async function handleUploadProof() {
    if (!task) return;
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission required', 'Allow access to your photo library to upload proof.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    const formData = new FormData();
    formData.append('photo', {
      uri: asset.uri,
      name: asset.fileName ?? 'proof.jpg',
      type: asset.mimeType ?? 'image/jpeg',
    } as any);
    try {
      await taskService.uploadProof(task.id, formData);
      setTask((t) => t ? { ...t, photo_proof: asset.uri } : t);
      Alert.alert('Uploaded', 'Photo proof submitted successfully.');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not upload photo proof.');
    }
  }

  async function handleMarketplace(bonusPoints: number) {
    if (!task) return;
    await taskService.listMarketplace(task.id, bonusPoints);
    setTask((t) => t ? { ...t, on_marketplace: true } : t);
    Alert.alert('Listed!', `Your task is now on the marketplace${bonusPoints > 0 ? ` with +${bonusPoints} bonus points` : ''}.`);
  }

  async function handleCancelListing() {
    if (!task?.marketplace_listing_id) return;
    Alert.alert('Remove Listing', 'Remove this task from the marketplace?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          try {
            await groupService.cancelListing(task.marketplace_listing_id!);
            setTask((t) => t ? { ...t, on_marketplace: false, marketplace_listing_id: null } : t);
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Could not remove listing.');
          }
        },
      },
    ]);
  }

  function confirmEmergencyReassign() {
    Alert.alert(
      'Emergency Reassignment',
      'This will unassign the task and notify everyone in the group. Use this only if you genuinely cannot complete it.\n\nYou can do this at most 3 times per month.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Trigger Emergency',
          style: 'destructive',
          onPress: handleEmergencyReassign,
        },
      ],
    );
  }

  async function handleEmergencyReassign() {
    if (!task) return;
    setTriggeringEmergency(true);
    try {
      const res = await taskService.emergencyReassign(task.id);
      setTask(res.data);
      Alert.alert('Emergency Sent', 'All group members have been notified and can now accept the task.');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not trigger emergency reassignment.');
    } finally {
      setTriggeringEmergency(false);
    }
  }

  async function handleAcceptEmergency() {
    if (!task) return;
    Alert.alert(
      'Accept Task',
      `Are you sure you want to take over "${task.template_name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Accept',
          onPress: async () => {
            setAcceptingEmergency(true);
            try {
              const res = await taskService.acceptEmergency(task.id);
              setTask(res.data);
              Alert.alert('Task Accepted', `"${task.template_name}" is now assigned to you.`);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not accept the task.');
            } finally {
              setAcceptingEmergency(false);
            }
          },
        },
      ],
    );
  }

  async function loadBreakdown() {
    if (!task) return;
    if (breakdown !== null) {
      setShowBreakdown((v) => !v);
      return;
    }
    setShowBreakdown(true);
    setBreakdownLoading(true);
    try {
      const res = await taskService.assignmentBreakdown(task.id);
      setBreakdown(res.data);
    } catch {
      setBreakdown({ breakdown_available: false, candidates: [], template_name: task.template_name });
    } finally {
      setBreakdownLoading(false);
    }
  }

  if (loading || !task) {
    return (
      <View style={[styles.root, styles.centered, { paddingTop: insets.top }]}>
        <StatusBar barStyle="dark-content" backgroundColor={C.bg} />
        <ActivityIndicator color={C.primary} size="large" />
      </View>
    );
  }

  const statusCfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
  const isDone = task.status === 'completed';
  const isAssignedToMe = String(task.assigned_to_id) === myUserId;
  const isOpenEmergency = task.reassignment_reason === 'emergency' && !task.assigned_to_id;
  const isOriginalAssignee = String(task.original_assignee_id) === myUserId;
  const description = task.template_details ?? null;
  const difficulty = task.difficulty ?? 1;
  const points = task.points_earned ?? 25;
  const [gradFrom, gradTo] = heroGradient(task.template_id ?? task.id);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.primary }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>ChoreSync</Text>
        </View>
        <TouchableOpacity activeOpacity={0.7} style={styles.topBarBtn}>
          <Text style={[styles.msIcon, { color: C.primary }]}>more_vert</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* ── Hero ────────────────────────────────── */}
        <View style={styles.heroSection}>
          {/* Status chip */}
          <View style={[styles.statusChip, { backgroundColor: statusCfg.bg }]}>
            <Text style={[styles.statusChipText, { color: statusCfg.fg }]}>
              {statusCfg.label.toUpperCase()}
            </Text>
          </View>

          {/* Title */}
          <Text style={styles.heroTitle}>{task.template_name}</Text>

          {/* Hero visual */}
          <LinearGradient
            colors={[gradFrom, gradTo]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.heroImage}
          >
            {/* Decorative circles */}
            <View style={styles.heroBlobA} />
            <View style={styles.heroBlobB} />
            {/* Central icon */}
            <Text style={[styles.msIcon, styles.heroIcon]}>
              {isDone ? 'task_alt' : 'cleaning_services'}
            </Text>
            {/* Group badge */}
            <View style={styles.heroGroupBadge}>
              <Text style={[styles.msIcon, { color: C.white, fontSize: 14 }]}>group</Text>
              <Text style={styles.heroGroupText} numberOfLines={1}>{task.group_name}</Text>
            </View>
          </LinearGradient>
        </View>

        {/* ── Bento Info Grid ──────────────────────── */}
        <View style={styles.bentoGrid}>
          {/* Deadline */}
          <View style={styles.bentoCell}>
            <Text style={[styles.msIcon, { color: C.primary, fontSize: 22, marginBottom: 8 }]}>
              calendar_today
            </Text>
            <Text style={styles.bentoCellLabel}>DEADLINE</Text>
            <Text
              style={[
                styles.bentoCellValue,
                isOverdue(task.deadline) && !isDone && { color: C.onErrorContainer },
              ]}
              numberOfLines={2}
            >
              {formatDeadline(task.deadline)}
            </Text>
          </View>

          {/* Assignee */}
          <View style={styles.bentoCell}>
            <View style={styles.assigneeAvatar}>
              <Text style={styles.assigneeInitials}>{getInitials(task)}</Text>
            </View>
            <Text style={styles.bentoCellLabel}>ASSIGNEE</Text>
            <Text style={styles.bentoCellValue} numberOfLines={1}>{getDisplayName(task)}</Text>
          </View>

          {/* Points */}
          <View style={styles.bentoCell}>
            <Text
              style={[
                styles.msIcon,
                { fontSize: 22, color: C.tertiary, marginBottom: 8 },
              ]}
            >
              stars
            </Text>
            <Text style={styles.bentoCellLabel}>POINTS</Text>
            <Text style={styles.bentoCellValue}>+{points} XP</Text>
          </View>

          {/* Difficulty */}
          <View style={styles.bentoCell}>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 22, marginBottom: 8 }]}>
              fitness_center
            </Text>
            <Text style={styles.bentoCellLabel}>DIFFICULTY</Text>
            <View style={styles.difficultyDots}>
              {Array.from({ length: 5 }).map((_, i) => (
                <View
                  key={i}
                  style={[
                    styles.difficultyDot,
                    { backgroundColor: i < difficulty ? C.secondary : C.surfaceContainerHighest },
                  ]}
                />
              ))}
            </View>
          </View>
        </View>

        {/* ── Description ─────────────────────────── */}
        {description ? (
          <View style={styles.descSection}>
            <Text style={styles.descLabel}>TASK DESCRIPTION</Text>
            <Text style={styles.descBody}>{description}</Text>
          </View>
        ) : null}

        {/* ── Estimated time ──────────────────────── */}
        {task.estimated_mins ? (
          <View style={styles.estRow}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 18 }]}>schedule</Text>
            <Text style={styles.estText}>Estimated {task.estimated_mins} min</Text>
          </View>
        ) : null}

        {/* ── Why Assigned? ────────────────────────── */}
        {task.assigned_to_id && (
          <View style={styles.whyAssignedSection}>
            <TouchableOpacity
              onPress={loadBreakdown}
              activeOpacity={0.8}
              style={styles.whyAssignedToggle}
            >
              <Text style={[styles.msIcon, { color: C.primary, fontSize: 18 }]}>analytics</Text>
              <Text style={styles.whyAssignedText}>Why was this assigned?</Text>
              {breakdownLoading ? (
                <ActivityIndicator size="small" color={C.primary} style={{ marginLeft: 'auto' }} />
              ) : (
                <Text style={[styles.msIcon, { color: C.primary, fontSize: 18, marginLeft: 'auto' }]}>
                  {showBreakdown ? 'expand_less' : 'expand_more'}
                </Text>
              )}
            </TouchableOpacity>
            {showBreakdown && breakdown && (
              <View style={{ paddingHorizontal: 16, paddingBottom: 16 }}>
                <BreakdownPanel breakdown={breakdown} />
              </View>
            )}
          </View>
        )}

        {/* ── Open Emergency Banner ────────────────── */}
        {isOpenEmergency && !isOriginalAssignee && (
          <View style={styles.emergencyBanner}>
            <Text style={[styles.msIcon, { color: C.onErrorContainer, fontSize: 22 }]}>crisis_alert</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.emergencyBannerTitle}>Needs Emergency Cover</Text>
              <Text style={styles.emergencyBannerSub}>
                This task needs someone to take over. Be the first to accept it.
              </Text>
            </View>
          </View>
        )}

        {/* ── Primary Action ───────────────────────── */}
        <View style={styles.primaryActionWrap}>
          {isDone ? (
            <View style={styles.completedBanner}>
              <Text style={[styles.msIcon, { color: C.secondary, fontSize: 26 }]}>check_circle</Text>
              <Text style={styles.completedText}>Task Completed!</Text>
            </View>
          ) : isOpenEmergency && !isOriginalAssignee ? (
            /* Accept emergency — shown to all group members except original assignee */
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={handleAcceptEmergency}
              disabled={acceptingEmergency}
              style={{ borderRadius: 16, overflow: 'hidden' }}
            >
              <LinearGradient
                colors={[C.primaryContainer, C.primary]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.primaryBtn}
              >
                {acceptingEmergency ? (
                  <ActivityIndicator color={C.white} size="small" />
                ) : (
                  <>
                    <Text style={[styles.msIcon, { color: C.white, fontSize: 26 }]}>volunteer_activism</Text>
                    <Text style={styles.primaryBtnText}>Accept Task</Text>
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>
          ) : isAssignedToMe ? (
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={handleComplete}
              disabled={completing}
              style={{ borderRadius: 16, overflow: 'hidden' }}
            >
              <LinearGradient
                colors={[C.primaryContainer, C.primary]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.primaryBtn}
              >
                {completing ? (
                  <ActivityIndicator color={C.white} size="small" />
                ) : (
                  <>
                    <Text style={[styles.msIcon, { color: C.white, fontSize: 26 }]}>check_circle</Text>
                    <Text style={styles.primaryBtnText}>Mark Complete</Text>
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>
          ) : (
            <View style={[styles.completedBanner, { backgroundColor: C.surfaceContainerHigh }]}>
              <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 22 }]}>person</Text>
              <Text style={[styles.completedText, { color: C.onSurfaceVariant, fontSize: 15 }]}>
                Assigned to {task.assigned_to_username ?? 'someone else'}
              </Text>
            </View>
          )}
        </View>

        {/* ── Secondary Actions (assigned user only) ── */}
        {!isDone && isAssignedToMe && (
          <View style={styles.secondaryActions}>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => setShowSnooze(true)}
              style={styles.secBtn}
            >
              <Text style={[styles.msIcon, { fontSize: 16, color: C.onSurfaceVariant }]}>snooze</Text>
              <Text style={styles.secBtnText}>Snooze</Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => setShowSwap(true)}
              style={styles.secBtn}
            >
              <Text style={[styles.msIcon, { fontSize: 16, color: C.onSurfaceVariant }]}>swap_horiz</Text>
              <Text style={styles.secBtnText}>Swap Task</Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              onPress={task.on_marketplace ? handleCancelListing : () => setShowMarketplace(true)}
              style={styles.secBtn}
            >
              <Text style={[styles.msIcon, { fontSize: 16, color: task.on_marketplace ? C.error : C.onSurfaceVariant }]}>
                {task.on_marketplace ? 'remove_shopping_cart' : 'storefront'}
              </Text>
              <Text style={[styles.secBtnText, task.on_marketplace && { color: C.error }]}>
                {task.on_marketplace ? 'Remove Listing' : 'Marketplace'}
              </Text>
            </TouchableOpacity>

            {task.photo_proof_required && !task.photo_proof && (
              <TouchableOpacity activeOpacity={0.85} onPress={handleUploadProof} style={styles.secBtn}>
                <Text style={[styles.msIcon, { fontSize: 16, color: C.primary }]}>photo_camera</Text>
                <Text style={[styles.secBtnText, { color: C.primary }]}>Upload Proof</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              activeOpacity={0.85}
              onPress={confirmEmergencyReassign}
              disabled={triggeringEmergency}
              style={[styles.secBtn, { borderColor: `${C.error}30` }]}
            >
              {triggeringEmergency
                ? <ActivityIndicator size="small" color={C.error} />
                : <Text style={[styles.msIcon, { fontSize: 16, color: C.error }]}>crisis_alert</Text>
              }
              <Text style={[styles.secBtnText, { color: C.error }]}>Emergency</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* ── Modals ────────────────────────────────── */}
      <SnoozeModal
        visible={showSnooze}
        onClose={() => setShowSnooze(false)}
        onSnooze={handleSnooze}
      />
      <SwapModal
        visible={showSwap}
        onClose={() => setShowSwap(false)}
        onSwap={handleSwap}
        members={groupMembers}
      />
      <MarketplaceModal
        visible={showMarketplace}
        onClose={() => setShowMarketplace(false)}
        onList={handleMarketplace}
        myPoints={myPoints}
        taskName={task.template_name}
      />

      {/* ── Post-completion preference nudge ─── */}
      <Modal
        visible={prefNudge.visible}
        transparent
        animationType="slide"
        onRequestClose={() => setPrefNudge((p) => ({ ...p, visible: false }))}
      >
        <TouchableOpacity
          style={ss.backdrop}
          activeOpacity={1}
          onPress={() => setPrefNudge((p) => ({ ...p, visible: false }))}
        />
        <View style={[ss.sheet, { paddingBottom: insets.bottom + 20 }]}>
          <View style={ss.handle} />
          <Text style={ss.sheetTitle}>How was this task?</Text>
          <Text style={ss.sheetSub}>{task.template_name} — your answer shapes future assignments.</Text>
          <View style={nudgeStyles.optRow}>
            {([
              { value: 'prefer' as const, emoji: '👍', label: 'Enjoyed it' },
              { value: 'neutral' as const, emoji: '😐', label: 'Neutral'    },
              { value: 'avoid'  as const, emoji: '👎', label: 'Disliked'   },
            ]).map((opt) => (
              <TouchableOpacity
                key={opt.value}
                activeOpacity={0.8}
                disabled={prefNudge.saving}
                onPress={() => handlePrefNudge(opt.value)}
                style={nudgeStyles.optBtn}
              >
                <Text style={nudgeStyles.optEmoji}>{opt.emoji}</Text>
                <Text style={nudgeStyles.optLabel}>{opt.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity
            onPress={() => setPrefNudge((p) => ({ ...p, visible: false }))}
            style={nudgeStyles.skipBtn}
          >
            <Text style={nudgeStyles.skipText}>Skip</Text>
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}

// ── Shared sheet / modal styles ───────────────────────────────
const ss = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  sheet: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: C.surfaceContainerLowest,
    borderTopLeftRadius: 28, borderTopRightRadius: 28,
    paddingTop: 12, paddingHorizontal: 24,
  },
  handle: {
    width: 40, height: 4,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  sheetTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 22, color: C.onSurface, letterSpacing: -0.4, marginBottom: 6,
  },
  sheetSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13, color: C.onSurfaceVariant, marginBottom: 20,
  },
  snoozeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.outlineVariant,
  },
  snoozeOptionText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 15, color: C.onSurface,
  },
  swapInput: {
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 14,
    paddingHorizontal: 14, paddingVertical: 12,
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 14, color: C.onSurface,
    marginBottom: 16,
    textAlignVertical: 'top',
    minHeight: 72,
  },
  actionBtnGradient: {
    paddingVertical: 16, alignItems: 'center',
    justifyContent: 'center', borderRadius: 999,
  },
  actionBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15, color: C.white,
  },
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24, color: C.onSurface,
  },
  // Member picker
  pickerList: {
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 14,
    overflow: 'hidden' as const,
    marginBottom: 14,
    maxHeight: 200,
  },
  pickerRow: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.outlineVariant,
  },
  pickerRowSelected: { backgroundColor: `${C.primary}14` },
  pickerAvatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center' as const, justifyContent: 'center' as const,
  },
  pickerAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12, color: C.onSurfaceVariant,
  },
  pickerName: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 14, color: C.onSurface,
  },
  // Marketplace modal
  balanceRow: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: 6,
    marginBottom: 14,
    backgroundColor: C.tertiaryFixed,
    borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 8,
  },
  balanceText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurface,
  },
  inputLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12, color: C.onSurfaceVariant,
    marginBottom: 6, letterSpacing: 0.4,
  },
  balanceError: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 12, color: C.onErrorContainer,
    marginBottom: 4,
  },
});

const nudgeStyles = StyleSheet.create({
  optRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
    justifyContent: 'center',
  },
  optBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 16,
    borderRadius: 16,
    backgroundColor: C.surfaceContainerHighest,
    gap: 6,
  },
  optEmoji: { fontSize: 28 },
  optLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12, color: C.onSurface,
  },
  skipBtn: { alignItems: 'center', paddingVertical: 8 },
  skipText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurfaceVariant,
  },
});

// ── Screen styles ─────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  centered: { alignItems: 'center', justifyContent: 'center' },

  // Top bar
  topBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    backgroundColor: C.bg,
  },
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  topBarBtn: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
  },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22, color: C.primary, letterSpacing: -0.5,
  },

  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 24, paddingTop: 8 },

  // Hero
  heroSection: { marginBottom: 28 },
  statusChip: {
    alignSelf: 'flex-start',
    paddingHorizontal: 14, paddingVertical: 5,
    borderRadius: 999, marginBottom: 14,
  },
  statusChipText: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 11, letterSpacing: 1.2,
  },
  heroTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 34, color: C.onSurface, letterSpacing: -1,
    lineHeight: 40, marginBottom: 20,
  },
  heroImage: {
    width: '100%', height: 200,
    borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
    position: 'relative',
  },
  heroBlobA: {
    position: 'absolute', top: -30, right: -30,
    width: 160, height: 160, borderRadius: 80,
    backgroundColor: 'rgba(255,255,255,0.1)',
  },
  heroBlobB: {
    position: 'absolute', bottom: -40, left: -20,
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: 'rgba(0,0,0,0.08)',
  },
  heroIcon: {
    fontSize: 64,
    color: 'rgba(255,255,255,0.85)',
  },
  heroGroupBadge: {
    position: 'absolute', bottom: 14, left: 16,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(0,0,0,0.25)',
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 999,
  },
  heroGroupText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12, color: C.white,
  },

  // Bento grid
  bentoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 28,
  },
  bentoCell: {
    width: '47.5%',
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 18,
    padding: 18,
    minHeight: 110,
    justifyContent: 'space-between',
  },
  bentoCellLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10, color: C.onSurfaceVariant,
    letterSpacing: 1.2, marginBottom: 4,
  },
  bentoCellValue: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15, color: C.onSurface, lineHeight: 20,
  },
  assigneeAvatar: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 8,
  },
  assigneeInitials: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16, color: C.onSecondaryContainer,
  },
  difficultyDots: { flexDirection: 'row', gap: 5, marginTop: 4 },
  difficultyDot: { width: 10, height: 10, borderRadius: 5 },

  // Description
  descSection: { marginBottom: 24 },
  descLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10, color: C.onSurfaceVariant,
    letterSpacing: 1.2, marginBottom: 10,
  },
  descBody: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 16, color: C.onSurfaceVariant,
    lineHeight: 26,
  },

  // Estimated time
  estRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginBottom: 16,
  },
  estText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurfaceVariant,
  },

  // Why assigned
  whyAssignedSection: {
    marginBottom: 16,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: `${C.primary}22`,
    overflow: 'hidden',
    backgroundColor: C.surfaceContainerLowest,
  },
  whyAssignedToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  whyAssignedText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: C.primary,
  },

  // Emergency banner
  emergencyBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: C.errorContainer,
    borderRadius: 14,
    paddingHorizontal: 16, paddingVertical: 14,
    marginBottom: 16,
  },
  emergencyBannerTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 14, color: C.onErrorContainer,
  },
  emergencyBannerSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12, color: C.onErrorContainer, opacity: 0.8, marginTop: 2,
  },

  // Primary action
  primaryActionWrap: { marginBottom: 20 },
  primaryBtn: {
    height: 64, borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center',
    gap: 12,
  },
  primaryBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 18, color: C.white,
  },
  completedBanner: {
    height: 64, borderRadius: 16,
    backgroundColor: C.secondaryContainer,
    flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center',
    gap: 12,
  },
  completedText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 18, color: C.secondary,
  },

  // Secondary actions
  secondaryActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    justifyContent: 'center',
  },
  secBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingHorizontal: 18, paddingVertical: 12,
    borderRadius: 999,
    backgroundColor: C.surfaceContainer,
    borderWidth: 1,
    borderColor: `${C.outlineVariant}26`,
  },
  secBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13, color: C.onSurfaceVariant,
  },

  // Shared
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24, color: C.onSurface,
  },
});
