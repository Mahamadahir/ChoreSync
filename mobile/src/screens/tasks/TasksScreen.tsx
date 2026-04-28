import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { taskService } from '../../services/taskService';
import { useAuthStore } from '../../stores/authStore';
import type { TasksStackParamList } from '../../navigation/types';
import type { TaskOccurrence } from '../../types/task';
import { Palette as C } from '../../theme';
import AppHeader from '../../components/common/AppHeader';
import { socketService } from '../../services/MobileSocketService';

type Nav = NativeStackNavigationProp<TasksStackParamList, 'Tasks'>;

const { width: SCREEN_W } = Dimensions.get('window');
const H_PAD = 24;
const CARD_GAP = 12;
const HALF_W = (SCREEN_W - H_PAD * 2 - CARD_GAP) / 2;

// ── Design tokens ─────────────────────────────────────────────

// ── Helpers ───────────────────────────────────────────────────
function todayStart() {
  const d = new Date(); d.setHours(0, 0, 0, 0); return d;
}
function tomorrowStart() {
  const d = todayStart(); d.setDate(d.getDate() + 1); return d;
}

function isOverdue(t: TaskOccurrence) {
  return t.status === 'overdue' || (t.status !== 'completed' && new Date(t.deadline) < new Date());
}
function isDueToday(t: TaskOccurrence) {
  const d = new Date(t.deadline);
  return d >= todayStart() && d < tomorrowStart();
}
function isUpcoming(t: TaskOccurrence) {
  return new Date(t.deadline) >= tomorrowStart() && t.status !== 'completed';
}

function formatDeadline(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (d >= todayStart() && d < tomorrowStart()) {
    return 'Today, ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }
  const yest = new Date(todayStart()); yest.setDate(yest.getDate() - 1);
  if (d >= yest && d < todayStart()) {
    return 'Yesterday, ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }
  if (d >= tomorrowStart() && d < new Date(tomorrowStart().getTime() + 86400000)) {
    return 'Tomorrow';
  }
  const diffDays = Math.round((d.getTime() - todayStart().getTime()) / 86400000);
  if (diffDays > 1 && diffDays <= 6) {
    return d.toLocaleDateString('en-US', { weekday: 'long' });
  }
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function initials(username?: string | null) {
  if (!username) return '?';
  return username.slice(0, 2).toUpperCase();
}

// Cycle icons for small cards
const SMALL_ICONS = [
  'potted_plant', 'inventory_2', 'local_laundry_service',
  'kitchen', 'cleaning_services', 'grass', 'shopping_cart', 'pets',
];

type FilterTab = 'active' | 'upcoming' | 'completed';

// ── Suggestion banner ─────────────────────────────────────────
function SuggestionCard({
  task,
  onAccept,
  onDecline,
}: {
  task: TaskOccurrence;
  onAccept: () => void;
  onDecline: () => void;
}) {
  const msg = (task as any).suggestion_message
    ?? `Should we add "${task.template_name}" to your schedule?`;

  return (
    <View style={styles.suggCard}>
      {/* Watermark icon */}
      <View style={styles.suggWatermark} pointerEvents="none">
        <Text style={[styles.msIcon, { fontSize: 80, color: C.onSurface, opacity: 0.08 }]}>
          magic_button
        </Text>
      </View>

      <View style={styles.suggInner}>
        <View style={styles.suggLabelRow}>
          <Text style={[styles.msIcon, { color: C.tertiary, fontSize: 20 }]}>auto_awesome</Text>
          <Text style={styles.suggLabel}>SMART SUGGESTION</Text>
        </View>
        <Text style={styles.suggText}>{msg}</Text>
        <View style={styles.suggActions}>
          <TouchableOpacity activeOpacity={0.85} onPress={onAccept} style={{ borderRadius: 12, overflow: 'hidden' }}>
            <LinearGradient
              colors={[C.primary, C.primaryContainer]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.suggAcceptBtn}
            >
              <Text style={styles.suggAcceptText}>Accept</Text>
            </LinearGradient>
          </TouchableOpacity>
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={onDecline}
            style={styles.suggDeclineBtn}
          >
            <Text style={styles.suggDeclineText}>Decline</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

// ── Overdue card (half-width, red left border) ────────────────
function OverdueCard({ task, onPress }: { task: TaskOccurrence; onPress: () => void }) {
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.halfCard, styles.overdueCard]}>
      <View style={styles.overdueAccent} />
      <View style={styles.cardContent}>
        <View style={styles.cardHeaderRow}>
          <View style={styles.cardStatusRow}>
            <Text style={[styles.msIcon, { color: C.error, fontSize: 14 }]}>error</Text>
            <Text style={[styles.cardStatusLabel, { color: C.error }]}>OVERDUE</Text>
          </View>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 20 }]}>more_horiz</Text>
        </View>
        <Text style={styles.cardTitle} numberOfLines={2}>{task.template_name}</Text>
        <Text style={styles.cardDesc} numberOfLines={3}>{(task as any).details ?? ''}</Text>
      </View>
      <View style={styles.cardFooter}>
        <View style={styles.avatarStack}>
          <View style={[styles.avatarCircle, { backgroundColor: C.errorContainer }]}>
            <Text style={[styles.avatarInitial, { color: C.error }]}>
              {initials(task.assigned_to_username)}
            </Text>
          </View>
        </View>
        <View style={styles.deadlineRow}>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>calendar_today</Text>
          <Text style={styles.deadlineText}>{formatDeadline(task.deadline)}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── Due today card (half-width) ───────────────────────────────
function DueTodayCard({ task, onPress }: { task: TaskOccurrence; onPress: () => void }) {
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.halfCard, styles.dueTodayCard]}>
      <View style={styles.cardContent}>
        <View style={styles.cardHeaderRow}>
          <View style={styles.cardStatusRow}>
            <Text style={[styles.msIcon, { color: C.primary, fontSize: 14 }]}>event</Text>
            <Text style={[styles.cardStatusLabel, { color: C.primary }]}>DUE TODAY</Text>
          </View>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 20 }]}>more_horiz</Text>
        </View>
        <Text style={styles.cardTitle} numberOfLines={2}>{task.template_name}</Text>
        <Text style={styles.cardDesc} numberOfLines={3}>{(task as any).details ?? ''}</Text>
      </View>
      <View style={styles.cardFooter}>
        <View style={styles.avatarStack}>
          <View style={[styles.avatarCircle, { backgroundColor: C.primaryFixed }]}>
            <Text style={[styles.avatarInitial, { color: C.primary }]}>
              {initials(task.assigned_to_username)}
            </Text>
          </View>
        </View>
        <View style={styles.deadlineRow}>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>schedule</Text>
          <Text style={styles.deadlineText}>{formatDeadline(task.deadline)}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── In-progress card (full-width) ─────────────────────────────
function InProgressCard({ task, onPress }: { task: TaskOccurrence; onPress: () => void }) {
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={styles.wideCard}>
      <View style={styles.wideCardInner}>
        {/* Left content */}
        <View style={styles.wideCardLeft}>
          <View style={styles.cardStatusRow}>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 14 }]}>check_circle</Text>
            <Text style={[styles.cardStatusLabel, { color: C.secondary }]}>IN PROGRESS</Text>
          </View>
          <Text style={styles.cardTitle} numberOfLines={2}>{task.template_name}</Text>
          <Text style={styles.cardDesc} numberOfLines={2}>{(task as any).details ?? ''}</Text>
        </View>

        {/* Status panel */}
        <View style={styles.inProgressPanel}>
          <View style={styles.inProgressPanelHeader}>
            <Text style={styles.inProgressPanelLabel}>STATUS</Text>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 18 }]}>pending_actions</Text>
          </View>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: '50%' }]} />
          </View>
          <Text style={styles.inProgressPanelSub}>Assigned to you</Text>
        </View>
      </View>

      <View style={[styles.cardFooter, styles.wideCardFooter]}>
        <View style={styles.avatarStack}>
          <View style={[styles.avatarCircle, { backgroundColor: C.secondaryContainer }]}>
            <Text style={[styles.avatarInitial, { color: C.onSecondaryContainer }]}>
              {initials(task.assigned_to_username)}
            </Text>
          </View>
        </View>
        <View style={styles.wideFooterRight}>
          <View style={styles.deadlineRow}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>calendar_month</Text>
            <Text style={styles.deadlineText}>{formatDeadline(task.deadline)}</Text>
          </View>
          <TouchableOpacity activeOpacity={0.7} onPress={onPress}>
            <Text style={styles.updateBtn}>UPDATE</Text>
          </TouchableOpacity>
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── Small upcoming card (half-width) ──────────────────────────
function SmallCard({
  task,
  idx,
  onPress,
}: {
  task: TaskOccurrence;
  idx: number;
  onPress: () => void;
}) {
  const icon = SMALL_ICONS[idx % SMALL_ICONS.length];
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.halfCard, styles.smallCard]}>
      <View style={styles.smallCardTop}>
        <Text style={[styles.cardStatusLabel, { color: C.onSurfaceVariant, opacity: 0.6 }]}>
          UPCOMING
        </Text>
        <Text style={styles.smallCardTitle} numberOfLines={2}>{task.template_name}</Text>
      </View>
      <View style={styles.smallCardBottom}>
        <Text style={[styles.msIcon, { color: C.stone400, fontSize: 24 }]}>{icon}</Text>
        <Text style={styles.smallCardDate}>{formatDeadline(task.deadline)}</Text>
      </View>
    </TouchableOpacity>
  );
}

// ── Pending card (half-width, generic) ────────────────────────
function PendingCard({ task, onPress }: { task: TaskOccurrence; onPress: () => void }) {
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.halfCard, styles.pendingCard]}>
      <View style={styles.cardContent}>
        <View style={styles.cardHeaderRow}>
          <View style={styles.cardStatusRow}>
            <Text style={[styles.msIcon, { color: C.primary, fontSize: 14 }]}>task_alt</Text>
            <Text style={[styles.cardStatusLabel, { color: C.primary }]}>PENDING</Text>
          </View>
        </View>
        <Text style={styles.cardTitle} numberOfLines={2}>{task.template_name}</Text>
      </View>
      <View style={styles.cardFooter}>
        <View style={styles.deadlineRow}>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>schedule</Text>
          <Text style={styles.deadlineText}>{formatDeadline(task.deadline)}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── Completed card (half-width) ───────────────────────────────
function CompletedCard({ task, onPress }: { task: TaskOccurrence; onPress: () => void }) {
  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={[styles.halfCard, styles.completedCard]}>
      <View style={styles.cardContent}>
        <View style={styles.cardStatusRow}>
          <Text style={[styles.msIcon, { color: C.secondary, fontSize: 14 }]}>check_circle</Text>
          <Text style={[styles.cardStatusLabel, { color: C.secondary }]}>DONE</Text>
        </View>
        <Text style={[styles.cardTitle, styles.cardTitleDone]} numberOfLines={2}>
          {task.template_name}
        </Text>
      </View>
      <View style={styles.cardFooter}>
        <Text style={styles.deadlineText}>
          {task.completed_at
            ? formatDeadline(task.completed_at)
            : formatDeadline(task.deadline)}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

// ── Grid row helper ───────────────────────────────────────────
function GridRow({ left, right }: { left: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={styles.gridRow}>
      {left}
      {right ?? <View style={{ width: HALF_W }} />}
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function TasksScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<Nav>();
  const user = useAuthStore((s) => s.user);

  const [allTasks, setAllTasks] = useState<TaskOccurrence[]>([]);
  const [suggestions, setSuggestions] = useState<TaskOccurrence[]>([]);
  const [pendingSwaps, setPendingSwaps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<FilterTab>('active');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [swapsError, setSwapsError] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setLoadError(null);
    setSwapsError(false);
    try {
      const [allRes, suggRes, swapsRes] = await Promise.allSettled([
        taskService.myTasks(),
        taskService.myTasks({ status: 'suggested' }),
        taskService.pendingSwaps(),
      ]);
      if (allRes.status === 'fulfilled') setAllTasks(allRes.value.data.results ?? allRes.value.data);
      if (suggRes.status === 'fulfilled') setSuggestions(suggRes.value.data.results ?? suggRes.value.data);
      if (swapsRes.status === 'fulfilled') {
        setPendingSwaps(swapsRes.value.data.results ?? swapsRes.value.data ?? []);
      } else {
        setSwapsError(true);
      }
      if (allRes.status === 'rejected') {
        const err = allRes.reason;
        setLoadError(err?.response?.data?.detail ?? 'Could not load tasks. Pull to refresh.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const unsub = socketService.onTaskUpdate((data) => {
      if (data.subtype === 'task_updated') load();
    });
    return unsub;
  }, [load]);

  async function handleAcceptSuggestion(task: TaskOccurrence) {
    try {
      await taskService.acceptSuggestion(task.id);
      setSuggestions((prev) => prev.filter((s) => s.id !== task.id));
      setAllTasks((prev) =>
        prev.map((t) => t.id === task.id ? { ...t, status: 'pending' as any } : t)
      );
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not accept suggestion.');
    }
  }

  async function handleDeclineSuggestion(task: TaskOccurrence) {
    try {
      await taskService.declineSuggestion(task.id);
      setSuggestions((prev) => prev.filter((s) => s.id !== task.id));
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not decline suggestion.');
    }
  }

  // ── Filtered tasks by tab ─────────────────────────────────
  const filteredTasks = useMemo(() => {
    switch (tab) {
      case 'active':
        return allTasks.filter((t) =>
          t.status !== 'completed' && t.status !== 'suggested',
        );
      case 'upcoming':
        return allTasks.filter(
          (t) => t.status === 'pending' && new Date(t.deadline) >= tomorrowStart(),
        );
      case 'completed':
        return allTasks.filter((t) => t.status === 'completed');
    }
  }, [allTasks, tab]);

  // ── Categorise for bento layout ──────────────────────────
  const overdueCards = filteredTasks.filter(isOverdue);
  const dueTodayCards = filteredTasks.filter((t) => !isOverdue(t) && isDueToday(t));
  const inProgressCards = filteredTasks.filter((t) => t.status === 'in_progress' && !isOverdue(t) && !isDueToday(t));
  const upcomingCards = filteredTasks.filter(isUpcoming);
  const completedCards = filteredTasks.filter((t) => t.status === 'completed');

  // Build bento rows
  function buildRows() {
    const rows: React.ReactNode[] = [];
    let k = 0;

    // Overdue + due-today mixed row
    const urgentPool = [...overdueCards, ...dueTodayCards];
    for (let i = 0; i < urgentPool.length; i += 2) {
      const a = urgentPool[i];
      const b = urgentPool[i + 1] ?? null;
      const makeCard = (t: TaskOccurrence) =>
        isOverdue(t)
          ? <OverdueCard key={t.id} task={t} onPress={() => navigation.navigate('TaskDetail', { taskId: t.id })} />
          : <DueTodayCard key={t.id} task={t} onPress={() => navigation.navigate('TaskDetail', { taskId: t.id })} />;
      rows.push(
        <GridRow key={`urgent-${k++}`} left={makeCard(a)} right={b ? makeCard(b) : undefined} />
      );
    }

    // In progress (full-width each)
    inProgressCards.forEach((t) => {
      rows.push(
        <InProgressCard key={t.id} task={t} onPress={() => navigation.navigate('TaskDetail', { taskId: t.id })} />
      );
    });

    // Upcoming small cards
    for (let i = 0; i < upcomingCards.length; i += 2) {
      const a = upcomingCards[i];
      const b = upcomingCards[i + 1] ?? null;
      rows.push(
        <GridRow
          key={`upcoming-${k++}`}
          left={<SmallCard task={a} idx={i} onPress={() => navigation.navigate('TaskDetail', { taskId: a.id })} />}
          right={b ? <SmallCard task={b} idx={i + 1} onPress={() => navigation.navigate('TaskDetail', { taskId: b.id })} /> : undefined}
        />
      );
    }

    // Completed
    for (let i = 0; i < completedCards.length; i += 2) {
      const a = completedCards[i];
      const b = completedCards[i + 1] ?? null;
      rows.push(
        <GridRow
          key={`done-${k++}`}
          left={<CompletedCard task={a} onPress={() => navigation.navigate('TaskDetail', { taskId: a.id })} />}
          right={b ? <CompletedCard task={b} onPress={() => navigation.navigate('TaskDetail', { taskId: b.id })} /> : undefined}
        />
      );
    }

    return rows;
  }

  const bentoRows = buildRows();

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      <AppHeader />

      <ScrollView
        showsVerticalScrollIndicator={false}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.primary} />
        }
      >
        {/* ── Smart Suggestion ─────────────────── */}
        {suggestions.length > 0 && (
          <SuggestionCard
            task={suggestions[0]}
            onAccept={() => handleAcceptSuggestion(suggestions[0])}
            onDecline={() => handleDeclineSuggestion(suggestions[0])}
          />
        )}

        {/* ── Incoming swap requests ─────────────── */}
        {swapsError && (
          <TouchableOpacity onPress={() => load()} activeOpacity={0.7}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 4 }}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 16 }]}>sync_problem</Text>
            <Text style={{ fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.onSurfaceVariant }}>
              Couldn't load swap requests · Tap to retry
            </Text>
          </TouchableOpacity>
        )}
        {!swapsError && pendingSwaps.length > 0 && (
          <View style={{ marginBottom: 8 }}>
            <Text style={styles.sectionTitle}>Swap Requests ({pendingSwaps.length})</Text>
            {pendingSwaps.map((swap: any) => (
              <View
                key={swap.id}
                style={{
                  backgroundColor: C.surfaceContainerLowest,
                  borderRadius: 12,
                  padding: 14,
                  marginBottom: 8,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <Text style={{ fontFamily: 'MaterialSymbols', fontSize: 22, color: C.primary }}>
                  swap_horiz
                </Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurface }}>
                    {swap.task?.template_name ?? 'Task swap request'}
                  </Text>
                  <Text style={{ fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.stone500 }}>
                    From {swap.from_user?.username ?? 'a group member'}
                    {swap.reason ? ` · ${swap.reason}` : ''}
                  </Text>
                </View>
                <TouchableOpacity
                  activeOpacity={0.8}
                  onPress={async () => {
                    try {
                      await taskService.respondSwap(swap.id, true);
                      setPendingSwaps((prev) => prev.filter((s) => s.id !== swap.id));
                      Alert.alert('Accepted', 'You accepted the swap request.');
                    } catch (e: any) {
                      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not accept swap.');
                    }
                  }}
                  style={{
                    backgroundColor: C.primary,
                    borderRadius: 8,
                    paddingHorizontal: 12,
                    paddingVertical: 6,
                  }}
                >
                  <Text style={{ color: '#fff', fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13 }}>
                    Accept
                  </Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* ── Filter header ────────────────────── */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Tasks</Text>
          <View style={styles.filterPill}>
            {(['active', 'upcoming', 'completed'] as FilterTab[]).map((t) => (
              <TouchableOpacity
                key={t}
                activeOpacity={0.75}
                onPress={() => setTab(t)}
                style={[styles.filterOption, tab === t && styles.filterOptionActive]}
              >
                <Text
                  style={[
                    styles.filterOptionText,
                    tab === t ? styles.filterOptionTextActive : styles.filterOptionTextInactive,
                  ]}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* ── Bento grid ───────────────────────── */}
        {loading ? (
          <View style={styles.centered}>
            <ActivityIndicator color={C.primary} size="large" />
          </View>
        ) : loadError ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, styles.emptyIcon]}>error</Text>
            <Text style={styles.emptyTitle}>{loadError}</Text>
          </View>
        ) : bentoRows.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, styles.emptyIcon]}>task_alt</Text>
            <Text style={styles.emptyTitle}>
              {tab === 'active' ? 'No active tasks.' : tab === 'upcoming' ? 'Nothing upcoming.' : 'No completed tasks yet.'}
            </Text>
          </View>
        ) : (
          <View style={styles.bento}>
            {bentoRows}
          </View>
        )}

        <View style={{ height: 120 }} />
      </ScrollView>

      {/* ── FAB ───────────────────────────────── */}
      <LinearGradient
        colors={[C.primary, C.primaryContainer]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.fab, { bottom: insets.bottom + 88 }]}
      >
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.fabInner}
          onPress={() => Alert.alert('Add Task', 'Use the AI Assistant to add tasks via natural language!')}
        >
          <Text style={[styles.msIcon, { color: C.white, fontSize: 28 }]}>add</Text>
        </TouchableOpacity>
      </LinearGradient>
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },

  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: H_PAD, paddingTop: 8, gap: 24 },

  // Suggestion card
  suggCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 20,
    padding: 20,
    overflow: 'hidden',
    position: 'relative',
  },
  suggWatermark: {
    position: 'absolute', top: 0, right: 0,
    padding: 16,
  },
  suggInner: { gap: 12 },
  suggLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  suggLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 11, color: C.onSurfaceVariant, letterSpacing: 1.2,
  },
  suggText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16, color: C.onSurface, lineHeight: 24,
  },
  suggActions: { flexDirection: 'row', gap: 12, paddingTop: 4 },
  suggAcceptBtn: {
    paddingHorizontal: 22, paddingVertical: 10, borderRadius: 14,
  },
  suggAcceptText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.white,
  },
  suggDeclineBtn: {
    backgroundColor: C.surfaceContainerHighest,
    paddingHorizontal: 22, paddingVertical: 10, borderRadius: 14,
  },
  suggDeclineText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurfaceVariant,
  },

  // Section header
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 30, color: C.onSurface, letterSpacing: -0.8,
  },
  filterPill: {
    flexDirection: 'row',
    backgroundColor: C.surfaceContainerHigh,
    borderRadius: 999, padding: 4, gap: 2,
  },
  filterOption: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 999,
  },
  filterOptionActive: {
    backgroundColor: C.surfaceContainerLowest,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 1,
  },
  filterOptionText: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 12 },
  filterOptionTextActive: { color: C.primary, fontFamily: 'PlusJakartaSans-Bold' },
  filterOptionTextInactive: { color: C.onSurfaceVariant },

  // Bento
  bento: { gap: CARD_GAP },
  gridRow: { flexDirection: 'row', gap: CARD_GAP },

  // Shared card base
  halfCard: {
    width: HALF_W,
    borderRadius: 18,
    padding: 18,
    minHeight: 180,
    justifyContent: 'space-between',
    overflow: 'hidden',
  },
  cardContent: { flex: 1, gap: 8 },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  cardStatusLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10, letterSpacing: 1.2,
  },
  cardTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 17, color: C.onSurface, lineHeight: 23,
  },
  cardTitleDone: {
    textDecorationLine: 'line-through', color: C.onSurfaceVariant,
  },
  cardDesc: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13, color: C.onSurfaceVariant, lineHeight: 18,
  },
  cardFooter: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 12, marginTop: 4,
  },

  // Overdue card
  overdueCard: {
    backgroundColor: C.surfaceContainerLowest,
    borderWidth: 0,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  overdueAccent: {
    position: 'absolute', left: 0, top: 0, bottom: 0,
    width: 4,
    backgroundColor: C.error,
    borderTopLeftRadius: 18,
    borderBottomLeftRadius: 18,
  },

  // Due today card
  dueTodayCard: {
    backgroundColor: C.surfaceContainer,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },

  // Pending card
  pendingCard: {
    backgroundColor: C.surfaceContainerLow,
  },

  // Completed card
  completedCard: {
    backgroundColor: C.surfaceContainerHighest,
    opacity: 0.7,
  },

  // Small card
  smallCard: {
    backgroundColor: C.surfaceContainerLow,
    minHeight: 140,
    justifyContent: 'space-between',
  },
  smallCardTop: { gap: 8 },
  smallCardTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15, color: C.onSurface, lineHeight: 21,
  },
  smallCardBottom: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  smallCardDate: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13, color: C.onSurfaceVariant,
  },

  // Wide in-progress card
  wideCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 18,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
    gap: 16,
  },
  wideCardInner: {
    flexDirection: 'row',
    gap: 16,
    alignItems: 'flex-start',
  },
  wideCardLeft: { flex: 1, gap: 6 },
  inProgressPanel: {
    backgroundColor: C.surfaceContainer,
    borderRadius: 14,
    padding: 14,
    minWidth: 120,
    gap: 8,
    justifyContent: 'center',
  },
  inProgressPanelHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  inProgressPanelLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 1,
  },
  progressTrack: {
    height: 10,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 5,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: C.secondary,
    borderRadius: 5,
  },
  inProgressPanelSub: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 11, color: C.onSurfaceVariant,
  },
  wideCardFooter: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: `${C.outlineVariant}33`,
    paddingTop: 14,
    marginTop: 0,
  },
  wideFooterRight: {
    flexDirection: 'row', alignItems: 'center', gap: 16,
  },
  updateBtn: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12, color: C.primary, letterSpacing: 1,
  },

  // Avatars
  avatarStack: { flexDirection: 'row' },
  avatarCircle: {
    width: 30, height: 30, borderRadius: 15,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: C.bg,
  },
  avatarInitial: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 12,
  },
  deadlineRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  deadlineText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 11, color: C.onSurfaceVariant,
  },

  // Loading / empty
  centered: { paddingVertical: 60, alignItems: 'center' },
  emptyState: { paddingVertical: 60, alignItems: 'center', gap: 8 },
  emptyIcon: { fontSize: 48, color: C.outlineVariant },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15, color: C.onSurfaceVariant,
  },

  // FAB
  fab: {
    position: 'absolute', right: 24,
    width: 56, height: 56, borderRadius: 16,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3, shadowRadius: 12, elevation: 8,
    overflow: 'hidden',
  },
  fabInner: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
