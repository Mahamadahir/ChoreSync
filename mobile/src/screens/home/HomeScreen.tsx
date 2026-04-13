import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { useNavigation } from '@react-navigation/native';
import { taskService } from '../../services/taskService';
import { groupService } from '../../services/groupService';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';
import { notificationService } from '../../services/notificationService';
import { api } from '../../services/api';
import { useAppForegroundRefresh } from '../../hooks/useAppForegroundRefresh';
import type { TaskOccurrence } from '../../types/task';
import type { Group } from '../../types/group';
import { Palette as C } from '../../theme';
import AppHeader from '../../components/common/AppHeader';

const { width: SCREEN_W } = Dimensions.get('window');
const H_PAD = 24;
const GROUP_CHIP_W = 116;

// ── Design tokens ─────────────────────────────────────────────

// ── Helpers ───────────────────────────────────────────────────
function greeting(name: string): string {
  const h = new Date().getHours();
  const salutation = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  return `${salutation}, ${name} 👋`;
}

function todayStart() {
  const d = new Date(); d.setHours(0, 0, 0, 0); return d;
}
function tomorrowStart() {
  const d = todayStart(); d.setDate(d.getDate() + 1); return d;
}
function isDueToday(iso: string) {
  const d = new Date(iso);
  return d >= todayStart() && d < tomorrowStart();
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
}

const GROUP_ICONS = ['home', 'apartment', 'cottage', 'cabin', 'house', 'domain', 'villa'];
function groupIcon(idx: number) { return GROUP_ICONS[idx % GROUP_ICONS.length]; }

// ── Stat card ─────────────────────────────────────────────────
function StatCard({
  icon, iconFill = true, iconColor, value, label, labelColor,
}: {
  icon: string; iconFill?: boolean; iconColor: string;
  value: number | string; label: string; labelColor: string;
}) {
  return (
    <View style={styles.statCard}>
      <Text
        style={[
          styles.msIcon,
          {
            color: iconColor, fontSize: 28, marginBottom: 6,
          },
        ]}
      >
        {icon}
      </Text>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={[styles.statLabel, { color: labelColor }]}>{label}</Text>
    </View>
  );
}

// ── Today task row ─────────────────────────────────────────────
function TodayTaskRow({
  task,
  onPress,
}: {
  task: TaskOccurrence;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress} style={styles.taskRow}>
      <View style={styles.taskRowLeft}>
        <View style={styles.taskCheckCircle} />
        <View style={styles.taskRowText}>
          <Text style={styles.taskRowName} numberOfLines={1}>{task.template_name}</Text>
          <Text style={styles.taskRowGroup} numberOfLines={1}>{task.group_name}</Text>
        </View>
      </View>
      <View style={styles.taskTimePill}>
        <Text style={styles.taskTimeText}>{formatTime(task.deadline)}</Text>
      </View>
    </TouchableOpacity>
  );
}

const SUGGESTION_TYPES = new Set([
  'suggestion_pattern',
  'suggestion_availability',
  'suggestion_preference',
  'suggestion_streak',
]);

const SUGGESTION_LABEL: Record<string, string> = {
  suggestion_pattern:      'Pattern detected',
  suggestion_availability: 'Availability insight',
  suggestion_preference:   'Preference suggestion',
  suggestion_streak:       'Streak suggestion',
};

// ── Smart Suggestion Card ─────────────────────────────────────
function SuggestionCard({
  title,
  content,
  onDismiss,
  onView,
}: {
  title: string;
  content: string;
  onDismiss: () => void;
  onView: () => void;
}) {
  return (
    <View style={styles.suggCard}>
      <View style={styles.suggLeft}>
        <View style={styles.suggIconWrap}>
          <Text style={[styles.msIcon, { color: C.tertiary, fontSize: 22 }]}>auto_awesome</Text>
        </View>
        <View style={styles.suggText}>
          <Text style={styles.suggTitle} numberOfLines={1}>{title}</Text>
          <Text style={styles.suggBody} numberOfLines={2}>{content}</Text>
        </View>
      </View>
      <View style={styles.suggActions}>
        <TouchableOpacity activeOpacity={0.7} onPress={onView} style={styles.suggViewBtn}>
          <Text style={styles.suggViewText}>View</Text>
        </TouchableOpacity>
        <TouchableOpacity activeOpacity={0.7} onPress={onDismiss} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={[styles.msIcon, { color: C.outline, fontSize: 18 }]}>close</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const user = useAuthStore((s) => s.user);

  useAppForegroundRefresh(); // re-fetch notifications whenever app comes back to foreground

  const [todayTasks, setTodayTasks] = useState<TaskOccurrence[]>([]);
  const [allGroups, setAllGroups] = useState<Group[]>([]);
  const [stats, setStats] = useState<{ streak: number; points: number; done_this_week: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    const results = await Promise.allSettled([
      taskService.myTasks(),
      groupService.list(),
      api.get('/api/users/me/stats/'),
    ]);

    // Tasks
    if (results[0].status === 'fulfilled') {
      const all: TaskOccurrence[] = results[0].value.data.results ?? results[0].value.data;
      setTodayTasks(
        all
          .filter((t) => isDueToday(t.deadline) && t.status !== 'completed')
          .sort((a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime()),
      );
    }

    // Groups
    if (results[1].status === 'fulfilled') {
      setAllGroups(results[1].value.data.results ?? results[1].value.data);
    }

    // Stats endpoint returns a per-household array; aggregate across all households.
    if (results[2].status === 'fulfilled') {
      const raw = results[2].value.data;
      const list: any[] = Array.isArray(raw) ? raw : (raw?.results ?? [raw]);
      const aggregated = list.reduce(
        (acc, s) => ({
          streak: Math.max(acc.streak, s.current_streak_days ?? 0),
          points: acc.points + (s.total_points ?? 0),
          done_this_week: acc.done_this_week + (s.tasks_completed_this_week ?? 0),
        }),
        { streak: 0, points: 0, done_this_week: 0 },
      );
      setStats(aggregated);
    }

    // Surface any partial failures so the user knows something went wrong
    const failed = results.filter((r) => r.status === 'rejected').length;
    if (failed > 0) {
      Alert.alert('Some data failed to load', 'Pull down to retry.');
    }

    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Household pulse from first group + today's tasks
  const primaryGroup = allGroups[0] ?? null;
  const householdTasks = useMemo(() => {
    if (!primaryGroup) return { done: 0, total: 0 };
    // We only have today tasks loaded; use member_count as a rough denominator
    const groupTodayTasks = todayTasks.filter((t) => t.group_id === primaryGroup.id);
    const done = groupTodayTasks.filter((t) => t.status === 'completed').length;
    return { done, total: Math.max(groupTodayTasks.length, 1) };
  }, [primaryGroup, todayTasks]);

  const displayName = user?.first_name || user?.username || 'there';

  // Smart suggestion card — most recent unread suggestion notification
  const { notifications, dismiss: storeDismiss } = useNotificationStore();
  const suggestionNotif = notifications.find(
    (n) => !n.read && !n.dismissed && SUGGESTION_TYPES.has(n.type),
  ) ?? null;

  async function handleDismissSuggestion() {
    if (!suggestionNotif) return;
    storeDismiss(suggestionNotif.id);
    notificationService.dismiss(suggestionNotif.id).catch(() => {});
  }

  function handleViewSuggestion() {
    if (!suggestionNotif?.group_id) return;
    storeDismiss(suggestionNotif.id);
    notificationService.dismiss(suggestionNotif.id).catch(() => {});
    navigation.navigate('GroupsTab', {
      screen: 'GroupDetail',
      params: { groupId: suggestionNotif.group_id, initialTab: 'discover' },
    });
  }

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
        {/* ── Greeting ─────────────────────────── */}
        <View style={styles.heroSection}>
          <Text style={styles.heroGreeting}>{greeting(displayName)}</Text>
          <Text style={styles.heroSub}>
            {todayTasks.length === 0
              ? 'No tasks due today — enjoy your day!'
              : `You have ${todayTasks.length} task${todayTasks.length === 1 ? '' : 's'} due today`}
          </Text>
        </View>

        {/* ── Stats row ────────────────────────── */}
        <View style={styles.statsRow}>
          <StatCard
            icon="local_fire_department"
            iconColor={C.primary}
            value={stats?.streak ?? '—'}
            label="Day Streak"
            labelColor={`${C.primary}b3`}
          />
          <StatCard
            icon="stars"
            iconColor={C.tertiary}
            value={stats?.points ?? '—'}
            label="Points"
            labelColor={`${C.tertiary}b3`}
          />
          <StatCard
            icon="check_circle"
            iconColor={C.secondary}
            value={stats?.done_this_week ?? '—'}
            label="Done This Week"
            labelColor={`${C.secondary}b3`}
          />
        </View>

        {/* ── Smart Suggestion Card ────────────── */}
        {suggestionNotif && (
          <SuggestionCard
            title={SUGGESTION_LABEL[suggestionNotif.type] ?? 'Smart Suggestion'}
            content={suggestionNotif.content}
            onDismiss={handleDismissSuggestion}
            onView={handleViewSuggestion}
          />
        )}

        {/* ── Today's Tasks ────────────────────── */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Today's Tasks</Text>
            <TouchableOpacity
              activeOpacity={0.7}
              onPress={() => navigation.navigate('TasksTab')}
            >
              <Text style={styles.viewAllText}>View All</Text>
            </TouchableOpacity>
          </View>

          {loading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator color={C.primary} size="small" />
            </View>
          ) : todayTasks.length === 0 ? (
            <View style={styles.emptyTasks}>
              <Text style={[styles.msIcon, { color: C.outlineVariant, fontSize: 32 }]}>task_alt</Text>
              <Text style={styles.emptyTasksText}>All caught up for today!</Text>
            </View>
          ) : (
            <View style={styles.taskList}>
              {todayTasks.slice(0, 3).map((t) => (
                <TodayTaskRow
                  key={t.id}
                  task={t}
                  onPress={() => navigation.navigate('TasksTab', {
                    screen: 'TaskDetail', params: { taskId: t.id },
                  })}
                />
              ))}
              {todayTasks.length > 3 && (
                <TouchableOpacity
                  activeOpacity={0.7}
                  onPress={() => navigation.navigate('TasksTab')}
                  style={styles.moreTasksRow}
                >
                  <Text style={styles.moreTasksText}>+{todayTasks.length - 3} more tasks</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>

        {/* ── Household Pulse ──────────────────── */}
        {primaryGroup && (
          <View style={styles.pulseCard}>
            <View style={styles.pulseHeader}>
              <View>
                <Text style={styles.pulseTitle}>Household Pulse</Text>
                <Text style={styles.pulseGroup}>{primaryGroup.name}</Text>
              </View>
              {/* Member initials stack */}
              <View style={styles.memberStack}>
                {Array.from({ length: Math.min(primaryGroup.member_count, 3) }).map((_, i) => (
                  <View
                    key={i}
                    style={[
                      styles.memberBubble,
                      { marginLeft: i === 0 ? 0 : -10, zIndex: 3 - i },
                    ]}
                  >
                    <Text style={styles.memberBubbleText}>
                      {String.fromCharCode(65 + i)}
                    </Text>
                  </View>
                ))}
                {primaryGroup.member_count > 3 && (
                  <View style={[styles.memberBubble, styles.memberOverflow, { marginLeft: -10 }]}>
                    <Text style={styles.memberOverflowText}>+{primaryGroup.member_count - 3}</Text>
                  </View>
                )}
              </View>
            </View>

            <View style={styles.pulseProgressSection}>
              <View style={styles.pulseProgressLabels}>
                <Text style={styles.pulseProgressLabel}>DAILY PROGRESS</Text>
                <Text style={[styles.pulseProgressLabel, { color: C.secondary }]}>
                  {householdTasks.done} of {householdTasks.total} complete
                </Text>
              </View>
              <View style={styles.pulseTrack}>
                <View
                  style={[
                    styles.pulseFill,
                    {
                      width: householdTasks.total > 0
                        ? `${Math.round((householdTasks.done / householdTasks.total) * 100)}%` as any
                        : '0%',
                    },
                  ]}
                />
              </View>
            </View>
          </View>
        )}

        {/* ── Your Groups quick-access ─────────── */}
        {allGroups.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Your Groups</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.groupsScroll}
              style={{ marginHorizontal: -H_PAD }}
            >
              <View style={{ width: H_PAD }} />
              {allGroups.map((g, idx) => (
                <TouchableOpacity
                  key={g.id}
                  activeOpacity={0.85}
                  onPress={() => navigation.navigate('GroupsTab', {
                    screen: 'GroupDetail', params: { groupId: String(g.id) },
                  })}
                  style={[
                    styles.groupChip,
                    idx === 0 && styles.groupChipActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.msIcon,
                      { color: C.primary, fontSize: 28 },
                    ]}
                  >
                    {groupIcon(idx)}
                  </Text>
                  <Text style={styles.groupChipName} numberOfLines={2}>{g.name}</Text>
                </TouchableOpacity>
              ))}
              <View style={{ width: H_PAD }} />
            </ScrollView>
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>

    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },


  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: H_PAD, paddingTop: 12, gap: 28 },

  // Hero greeting
  heroSection: { gap: 6, marginTop: 8 },
  heroGreeting: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 32, color: C.onSurface, letterSpacing: -0.8, lineHeight: 40,
  },
  heroSub: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 16, color: C.onSurfaceVariant, opacity: 0.85,
  },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  statCard: {
    flex: 1,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 18,
    paddingVertical: 18,
    paddingHorizontal: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: `${C.outlineVariant}1a`,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
    gap: 2,
  },
  statValue: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 24, color: C.onSurface, letterSpacing: -0.5,
  },
  statLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, letterSpacing: 1, textAlign: 'center', textTransform: 'uppercase',
  },

  // Section
  section: { gap: 14 },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  sectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 19, color: C.onSurface, letterSpacing: -0.3,
  },
  viewAllText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13, color: C.primary, letterSpacing: 0.5,
  },

  // Task list
  taskList: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 18,
    overflow: 'hidden',
  },
  taskRow: {
    backgroundColor: C.surfaceContainerLowest,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: `${C.outlineVariant}40`,
  },
  taskRowLeft: { flexDirection: 'row', alignItems: 'center', gap: 14, flex: 1 },
  taskCheckCircle: {
    width: 22, height: 22, borderRadius: 11,
    borderWidth: 2, borderColor: C.outlineVariant,
    flexShrink: 0,
  },
  taskRowText: { flex: 1 },
  taskRowName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 14, color: C.onSurface,
  },
  taskRowGroup: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 11, color: C.onSurfaceVariant, marginTop: 2,
  },
  taskTimePill: {
    backgroundColor: C.surfaceContainerHighest,
    paddingHorizontal: 10, paddingVertical: 4,
    borderRadius: 999, marginLeft: 8,
  },
  taskTimeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 0.5,
  },
  moreTasksRow: {
    backgroundColor: C.surfaceContainerLowest,
    paddingHorizontal: 16, paddingVertical: 12,
    alignItems: 'center',
  },
  moreTasksText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12, color: C.primary,
  },

  // Loading / empty
  loadingBox: { paddingVertical: 32, alignItems: 'center' },
  emptyTasks: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 18,
    paddingVertical: 32,
    alignItems: 'center',
    gap: 8,
  },
  emptyTasksText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurfaceVariant,
  },

  // Household pulse
  pulseCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: `${C.outlineVariant}1a`,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
    gap: 18,
  },
  pulseHeader: {
    flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between',
  },
  pulseTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 18, color: C.onSurface, letterSpacing: -0.3,
  },
  pulseGroup: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurfaceVariant, marginTop: 2,
  },
  memberStack: { flexDirection: 'row', alignItems: 'center' },
  memberBubble: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: C.surfaceContainerLow,
  },
  memberBubbleText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 12, color: C.onSecondaryContainer,
  },
  memberOverflow: { backgroundColor: C.surfaceContainerHighest },
  memberOverflowText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10, color: C.onSurfaceVariant,
  },
  pulseProgressSection: { gap: 8 },
  pulseProgressLabels: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  pulseProgressLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10, color: C.onSurfaceVariant, letterSpacing: 1, textTransform: 'uppercase',
  },
  pulseTrack: {
    height: 12, backgroundColor: C.surfaceContainerHighest,
    borderRadius: 6, overflow: 'hidden',
  },
  pulseFill: {
    height: '100%', backgroundColor: C.secondary, borderRadius: 6,
  },

  // Groups scroll
  groupsScroll: { gap: 12, paddingVertical: 4 },
  groupChip: {
    width: GROUP_CHIP_W,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 18,
    paddingVertical: 16, paddingHorizontal: 12,
    alignItems: 'center', gap: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  groupChipActive: {
    borderWidth: 2, borderColor: `${C.primary}1a`,
  },
  groupChipName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12, color: C.onSurface, textAlign: 'center', lineHeight: 16,
  },


  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },

  // Suggestion card
  suggCard: {
    backgroundColor: C.tertiaryFixed,
    borderRadius: 18,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  suggLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  suggIconWrap: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: `${C.tertiary}22`,
    alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  suggText: { flex: 1 },
  suggTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13, color: C.onTertiaryFixed, letterSpacing: 0.2, marginBottom: 2,
  },
  suggBody: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12, color: `${C.onTertiaryFixed}cc`, lineHeight: 17,
  },
  suggActions: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 0 },
  suggViewBtn: {
    backgroundColor: C.tertiary,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 6,
  },
  suggViewText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12, color: C.white,
  },
});
