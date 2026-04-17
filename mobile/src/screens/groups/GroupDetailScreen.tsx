import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
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
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import Constants from 'expo-constants';
import { groupService } from '../../services/groupService';
import { taskService } from '../../services/taskService';
import { tokenStorage } from '../../services/tokenStorage';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';
import type { Group, GroupMember, LeaderboardEntry } from '../../types/group';
import type { TaskOccurrence } from '../../types/task';
import type { GroupDetailScreenProps } from '../../navigation/types';
import { Palette as C } from '../../theme';

// ── Design tokens ─────────────────────────────────────────────

type TabId = 'tasks' | 'people' | 'chat' | 'discover' | 'analytics' | 'settings';
const TABS: { id: TabId; label: string }[] = [
  { id: 'tasks',     label: 'Tasks'     },
  { id: 'people',    label: 'People'    },
  { id: 'chat',      label: 'Chat'      },
  { id: 'discover',  label: 'Discover'  },
  { id: 'analytics', label: 'Analytics' },
  { id: 'settings',  label: 'Settings'  },
];

// ── Helpers ───────────────────────────────────────────────────
function formatDeadline(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const todayStart = new Date(now); todayStart.setHours(0,0,0,0);
  const tomorrowStart = new Date(todayStart); tomorrowStart.setDate(tomorrowStart.getDate()+1);
  const timeStr = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  if (d < now && d >= todayStart) return `Today, ${timeStr}`;
  if (d < now) return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${timeStr}`;
  if (d >= todayStart && d < tomorrowStart) return `Today, ${timeStr}`;
  if (d >= tomorrowStart && d < new Date(tomorrowStart.getTime() + 86400000)) return `Tomorrow, ${timeStr}`;
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function isOverdue(t: TaskOccurrence) {
  return t.status === 'overdue' || (t.status !== 'completed' && new Date(t.deadline) < new Date());
}

function initials(s?: string | null) {
  if (!s) return '?';
  return s.split(' ').slice(0,2).map(w => w[0]?.toUpperCase() ?? '').join('') || s[0].toUpperCase();
}

// Cycle icons + colours for task cards
const TASK_ICON_SETS = [
  { icon: 'cleaning_services', bg: `${C.errorContainer}66`,     fg: C.error     },
  { icon: 'potted_plant',      bg: `${C.secondaryContainer}66`, fg: C.secondary },
  { icon: 'kitchen',           bg: `${C.tertiaryFixed}66`,      fg: C.tertiary  },
  { icon: 'local_laundry_service', bg: `${C.primaryFixed}66`,   fg: C.primary   },
  { icon: 'grass',             bg: `${C.secondaryContainer}66`, fg: C.secondary },
  { icon: 'recycling',         bg: C.surfaceContainerHigh,      fg: C.onSurfaceVariant },
  { icon: 'shopping_cart',     bg: `${C.primaryFixed}66`,       fg: C.primary   },
  { icon: 'auto_delete',       bg: C.surfaceContainer,          fg: C.onSurfaceVariant },
];

// ── Task card (Tasks tab) ─────────────────────────────────────
function GroupTaskCard({
  task,
  idx,
  onComplete,
  onPress,
  completing,
  isAssignedToMe,
}: {
  task: TaskOccurrence;
  idx: number;
  onComplete: () => void;
  onPress: () => void;
  completing: boolean;
  isAssignedToMe: boolean;
}) {
  const iconSet = TASK_ICON_SETS[idx % TASK_ICON_SETS.length];
  const isDone = task.status === 'completed';
  const overdue = isOverdue(task);

  // Status badge
  let badgeBg: string = C.tertiaryFixed;
  let badgeFg: string = C.onTertiaryFixedVariant;
  let badgeLabel = 'PENDING';
  if (isDone) { badgeBg = C.secondaryContainer; badgeFg = C.onSecondaryContainer; badgeLabel = 'DONE'; }
  else if (overdue) { badgeBg = C.errorContainer; badgeFg = C.onErrorContainer; badgeLabel = 'OVERDUE'; }
  else if (task.status === 'in_progress') { badgeBg = C.secondaryContainer; badgeFg = C.onSecondaryContainer; badgeLabel = 'IN PROGRESS'; }
  else if (task.status === 'snoozed') { badgeBg = C.surfaceContainerHigh; badgeFg = C.onSurfaceVariant; badgeLabel = 'SNOOZED'; }

  return (
    <TouchableOpacity
      activeOpacity={0.88}
      onPress={onPress}
      style={[styles.taskCard, isDone && { opacity: 0.6 }]}
    >
      {/* Left: icon + details */}
      <View style={styles.taskCardLeft}>
        <View style={[styles.taskIconBox, { backgroundColor: iconSet.bg }]}>
          <Text style={[styles.msIcon, { color: iconSet.fg, fontSize: 22 }]}>{iconSet.icon}</Text>
        </View>

        <View style={styles.taskCardBody}>
          <View style={styles.taskCardTitleRow}>
            <Text
              style={[styles.taskCardTitle, isDone && styles.taskCardTitleDone]}
              numberOfLines={1}
            >
              {task.template_name}
            </Text>
            <View style={[styles.statusBadge, { backgroundColor: badgeBg }]}>
              <Text style={[styles.statusBadgeText, { color: badgeFg }]}>{badgeLabel}</Text>
            </View>
          </View>

          {isDone ? (
            <Text style={styles.taskCardCompletedBy} numberOfLines={1}>
              Completed by {task.assigned_to_username ?? 'member'}
            </Text>
          ) : (
            <Text style={styles.taskCardAssignee} numberOfLines={1}>
              Assignee:{' '}
              <Text style={styles.taskCardAssigneeName}>
                {task.assigned_to_username ?? 'Unassigned'}
              </Text>
            </Text>
          )}

          <View style={styles.taskCardMeta}>
            <View style={styles.taskCardDeadlineRow}>
              <Text
                style={[
                  styles.msIcon,
                  { fontSize: 14, color: overdue ? C.error : C.onSurfaceVariant },
                ]}
              >
                {overdue ? 'schedule' : 'event'}
              </Text>
              <Text
                style={[
                  styles.taskCardDeadlineText,
                  overdue && { color: C.error },
                ]}
              >
                {formatDeadline(task.deadline)}
              </Text>
            </View>
            {task.photo_proof_required && !isDone && (
              <Text style={[styles.msIcon, { fontSize: 18, color: C.onSurfaceVariant }]}>
                photo_camera
              </Text>
            )}
          </View>
        </View>
      </View>

      {/* Right: check button — only shown to the assigned user */}
      {isAssignedToMe && (
        <TouchableOpacity
          activeOpacity={0.75}
          onPress={onComplete}
          disabled={completing || isDone}
          style={styles.checkBtnWrap}
        >
          {completing ? (
            <ActivityIndicator size="small" color={C.primary} />
          ) : isDone ? (
            <LinearGradient
              colors={[C.primary, C.primaryContainer]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.checkBtnCircle}
            >
              <Text style={[styles.msIcon, { color: C.white, fontSize: 20 }]}>done_all</Text>
            </LinearGradient>
          ) : (
            <View style={styles.checkBtnCircle}>
              <Text style={[styles.msIcon, { color: C.surfaceContainerHighest, fontSize: 20 }]}>check</Text>
            </View>
          )}
        </TouchableOpacity>
      )}
    </TouchableOpacity>
  );
}

// ── Member card (People tab) ─────────────────────────────────
function MemberRow({
  member,
  points,
  isTopRank,
}: {
  member: GroupMember;
  points?: number;
  isTopRank?: boolean;
}) {
  const displayName = [member.first_name, member.last_name].filter(Boolean).join(' ') || member.username;
  const initial = initials(displayName);
  const isMod = member.role === 'moderator';

  return (
    <View style={styles.memberCard}>
      <View style={styles.memberCardLeft}>
        <View style={styles.memberAvatar}>
          <Text style={styles.memberAvatarText}>{initial}</Text>
        </View>
        <View style={styles.memberInfo}>
          <Text style={styles.memberName} numberOfLines={1}>{displayName}</Text>
          <View style={[styles.roleBadge, isMod ? styles.roleBadgeMod : styles.roleBadgeMember]}>
            <Text style={[styles.roleBadgeText, { color: isMod ? '#792f27' : C.onSecondaryContainer }]}>
              {isMod ? 'Mod' : 'Member'}
            </Text>
          </View>
        </View>
      </View>
      {points !== undefined && (
        <View style={styles.memberPointsRight}>
          <Text style={[styles.memberPointsNum, isTopRank && { color: C.primary }]}>
            {points.toLocaleString()}
          </Text>
          <Text style={styles.memberPointsLabel}>Points</Text>
        </View>
      )}
    </View>
  );
}

// ── Leaderboard podium block ─────────────────────────────────
function PodiumBlock({
  entry,
  rank,
  barHeight,
  isFirst,
}: {
  entry: LeaderboardEntry | undefined;
  rank: number;
  barHeight: number;
  isFirst: boolean;
}) {
  const displayName = entry
    ? ([entry.first_name, entry.last_name].filter(Boolean).join(' ') || entry.username)
    : '—';
  const initial = entry ? initials(displayName) : '?';
  const pts = entry ? entry.total_points : 0;

  return (
    <View style={[styles.podiumItem, isFirst && styles.podiumItemCenter]}>
      {isFirst && (
        <Text style={[styles.msIcon, styles.crownIcon]}>workspace_premium</Text>
      )}
      <View style={[styles.podiumAvatar, isFirst ? styles.podiumAvatarFirst : styles.podiumAvatarOther]}>
        <Text style={[styles.podiumAvatarText, isFirst ? { fontSize: 22 } : {}]}>{initial}</Text>
      </View>
      {isFirst ? (
        <LinearGradient
          colors={[C.primary, C.primaryContainer]}
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={[styles.podiumBar, { height: barHeight }]}
        >
          <Text style={styles.podiumRank1Num}>{rank}</Text>
          <Text style={styles.podiumRank1Name} numberOfLines={1}>{displayName}</Text>
          <Text style={styles.podiumRank1Pts}>{pts.toLocaleString()} pts</Text>
        </LinearGradient>
      ) : (
        <View style={[styles.podiumBar, styles.podiumBarOther, { height: barHeight }]}>
          <Text style={styles.podiumOtherNum}>{rank}</Text>
          <Text style={styles.podiumOtherName} numberOfLines={1}>{displayName}</Text>
          <Text style={styles.podiumOtherPts}>{pts} pts</Text>
        </View>
      )}
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function GroupDetailScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<GroupDetailScreenProps['route']>();
  const { groupId, initialTab } = route.params;
  const user = useAuthStore((s) => s.user);
  const tabBadge = useNotificationStore((s) => s.tabBadge);

  const VALID_TABS: TabId[] = ['tasks', 'people', 'chat', 'discover', 'analytics', 'settings'];
  const resolvedInitialTab: TabId =
    initialTab && (VALID_TABS as string[]).includes(initialTab) ? (initialTab as TabId) : 'tasks';

  const [group, setGroup] = useState<Group | null>(null);
  const [tasks, setTasks] = useState<TaskOccurrence[]>([]);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [completing, setCompleting] = useState<Record<number, boolean>>({});
  const [activeTab, setActiveTab] = useState<TabId>(resolvedInitialTab);

  // Analytics state
  const [groupStats, setGroupStats] = useState<any>(null);
  const [assignmentMatrix, setAssignmentMatrix] = useState<Record<string, number> | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // ── Chat state ────────────────────────────────────────────────
  type ChatMsg = {
    id: number;
    group_id: string;
    sender_id: string | null;
    username: string;
    body: string;
    sent_at: string;
    read_by: { user_id: string; username: string; seen_at: string }[];
    all_read: boolean;
  };
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatDisconnected, setChatDisconnected] = useState(false);
  // KAV offset = height of everything above the chat area (topBar + hero + tabs)
  const [chatKvOffset, setChatKvOffset] = useState(0);
  const [receiptModal, setReceiptModal] = useState<{ visible: boolean; msg: ChatMsg | null }>({ visible: false, msg: null });
  const flatListRef = useRef<ScrollView>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const myUserId = String(user?.id ?? '');

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    const [grpRes, tasksRes, membersRes, lbRes] = await Promise.allSettled([
      groupService.get(groupId),
      groupService.tasks(groupId),
      groupService.members(groupId),
      groupService.leaderboard(groupId),
    ]);

    if (grpRes.status === 'fulfilled') setGroup(grpRes.value.data);
    if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data.results ?? tasksRes.value.data);
    if (membersRes.status === 'fulfilled') setMembers(membersRes.value.data.results ?? membersRes.value.data);
    if (lbRes.status === 'fulfilled') setLeaderboard(lbRes.value.data.results ?? lbRes.value.data);

    const failed = [grpRes, tasksRes, membersRes, lbRes].filter((r) => r.status === 'rejected').length;
    if (failed > 0) {
      Alert.alert('Some sections failed to load', 'Pull down to retry.');
    }

    setLoading(false);
    setRefreshing(false);
  }, [groupId]);

  useEffect(() => { load(); }, [load]);

  // ── Load chat history + connect WS when Chat tab becomes active ──
  useEffect(() => {
    if (activeTab !== 'chat') return;

    let destroyed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    const reconnectAttempts = { count: 0 };

    function clearTimer() {
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    }

    async function fetchHistory() {
      setChatLoading(true);
      try {
        const res = await groupService.messages(groupId);
        const msgs: ChatMsg[] = res.data;
        setChatMessages(msgs);
        const unread = msgs
          .filter(m => m.sender_id !== null && m.sender_id !== myUserId)
          .map(m => m.id);
        if (unread.length) groupService.markRead(groupId, unread).catch(() => {});
      } catch { /* ignore */ }
      setChatLoading(false);
    }

    async function connectSocket() {
      if (destroyed) return;
      const token = await tokenStorage.getAccess();
      if (!token || destroyed) return;

      const baseUrl = (Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000')
        .replace(/^http/, 'ws');
      const ws = new WebSocket(`${baseUrl}/ws/chores/?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.count = 0;
        setChatDisconnected(false);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);

          if (data.type === 'chat_message' && data.group_id === groupId) {
            const msg: ChatMsg = {
              id: data.id,
              group_id: data.group_id,
              sender_id: data.sender_id,
              username: data.username,
              body: data.body,
              sent_at: data.sent_at,
              read_by: [],
              all_read: false,
            };
            setChatMessages(prev => [...prev, msg]);
            if (data.sender_id !== myUserId) {
              groupService.markRead(groupId, [data.id]).catch(() => {});
              ws.send(JSON.stringify({ type: 'mark_read', group_id: groupId, message_ids: [data.id] }));
            }
          }

          if (data.type === 'receipts_update') {
            setChatMessages(prev => prev.map(m => {
              if (!data.message_ids.includes(m.id)) return m;
              if (data.user_id === myUserId) return m;
              const alreadyHas = m.read_by.some(r => r.user_id === data.user_id);
              const newReadBy = alreadyHas
                ? m.read_by
                : [...m.read_by, { user_id: data.user_id, username: data.username, seen_at: data.seen_at }];
              return { ...m, read_by: newReadBy };
            }));
          }
        } catch { /* ignore malformed frames */ }
      };

      ws.onerror = () => ws.close();

      ws.onclose = () => {
        if (destroyed) return;
        setChatDisconnected(true);
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.count), 30000);
        reconnectAttempts.count += 1;
        reconnectTimer = setTimeout(async () => {
          // Backfill any missed messages before reconnecting
          await fetchHistory();
          connectSocket();
        }, delay);
      };
    }

    fetchHistory().then(() => connectSocket());

    return () => {
      destroyed = true;
      clearTimer();
      wsRef.current?.close();
      wsRef.current = null;
      setChatDisconnected(false);
    };
  }, [activeTab, groupId]);  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleComplete(task: TaskOccurrence) {
    setCompleting((p) => ({ ...p, [task.id]: true }));
    try {
      await taskService.complete(task.id);
      setTasks((prev) =>
        prev.map((t) => t.id === task.id ? { ...t, status: 'completed' as any } : t)
      );
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not complete task.');
    } finally {
      setCompleting((p) => ({ ...p, [task.id]: false }));
    }
  }

  async function handleLeaveGroup() {
    Alert.alert(
      'Leave Group',
      `Are you sure you want to leave "${group?.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Leave',
          style: 'destructive',
          onPress: async () => {
            try {
              await groupService.leave(groupId);
              navigation.goBack();
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not leave group.');
            }
          },
        },
      ],
    );
  }

  function sendChatMessage() {
    const body = chatInput.trim();
    if (!body) return;
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      Alert.alert('Not connected', 'Chat is not connected. Pull down to refresh and try again.');
      return;
    }
    wsRef.current.send(JSON.stringify({ type: 'chat_message', group_id: groupId, body }));
    setChatInput('');
  }

  // Load analytics lazily when the tab is first opened
  useEffect(() => {
    if (activeTab !== 'analytics' || groupStats !== null) return;
    let cancelled = false;
    (async () => {
      setAnalyticsLoading(true);
      try {
        const [statsRes, matrixRes] = await Promise.allSettled([
          groupService.stats(groupId),
          groupService.assignmentMatrix(groupId),
        ]);
        if (cancelled) return;
        if (statsRes.status === 'fulfilled') setGroupStats(statsRes.value.data);
        if (matrixRes.status === 'fulfilled') setAssignmentMatrix(matrixRes.value.data);
      } finally {
        if (!cancelled) setAnalyticsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [activeTab, groupId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Milestone stats
  const activeTasks = tasks.filter((t) => t.status !== 'completed');
  const completedTasks = tasks.filter((t) => t.status === 'completed');
  const milestonePct = tasks.length > 0
    ? Math.round((completedTasks.length / tasks.length) * 100)
    : 0;

  // Points lookup
  const pointsMap = useMemo(() => {
    const m: Record<string, number> = {};
    leaderboard.forEach((e) => { m[e.user_id] = e.total_points; });
    return m;
  }, [leaderboard]);

  // ── Render tab content ───────────────────────────────────
  function renderTasks() {
    if (loading) return <ActivityIndicator color={C.primary} size="large" style={{ paddingVertical: 40 }} />;

    return (
      <View style={styles.tabContent}>
        {/* Header */}
        <View style={styles.tasksSectionHeader}>
          <View style={styles.tasksSectionLeft}>
            <Text style={styles.tasksSectionTitle}>Active Tasks</Text>
            <View style={styles.taskCountBadge}>
              <Text style={styles.taskCountText}>{activeTasks.length}</Text>
            </View>
          </View>
          {/* Moderators always see New Task; members in restricted groups see Suggest Task */}
          {(group?.my_role === 'moderator' || !group?.task_proposal_voting_required) ? (
            <TouchableOpacity
              activeOpacity={0.7}
              onPress={() => navigation.navigate('TaskAuthor', { groupId })}
              style={styles.newTaskBtn}
            >
              <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>add_circle</Text>
              <Text style={styles.newTaskBtnText}>New Task</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              activeOpacity={0.7}
              onPress={() => navigation.navigate('Proposals', { groupId, myRole: group?.my_role ?? 'member' })}
              style={styles.newTaskBtn}
            >
              <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>lightbulb</Text>
              <Text style={styles.newTaskBtnText}>Suggest Task</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Task cards */}
        {tasks.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, { fontSize: 48, color: C.outlineVariant }]}>assignment</Text>
            <Text style={styles.emptyTitle}>No tasks yet.</Text>
            <Text style={styles.emptySub}>Add recurring tasks in Settings to get started.</Text>
          </View>
        ) : (
          <View style={styles.taskCardList}>
            {/* Active first, then completed */}
            {[...activeTasks, ...completedTasks].map((t, idx) => (
              <GroupTaskCard
                key={t.id}
                task={t}
                idx={idx}
                onComplete={() => handleComplete(t)}
                onPress={() => navigation.navigate('TaskDetail', { taskId: t.id })}
                completing={!!completing[t.id]}
                isAssignedToMe={String(t.assigned_to_id) === myUserId}
              />
            ))}
          </View>
        )}

        {/* Weekly Milestone */}
        <View style={styles.milestoneCard}>
          <View style={styles.milestoneHeader}>
            <Text style={styles.milestoneTitle}>Weekly Milestone</Text>
            <Text style={styles.milestonePct}>{milestonePct}%</Text>
          </View>
          <View style={styles.milestoneTrack}>
            <View style={[styles.milestoneFill, { width: `${milestonePct}%` as any }]} />
          </View>
          <Text style={styles.milestoneSub}>
            {milestonePct >= 80
              ? `Great progress! You're on track to earn a badge this week.`
              : `${completedTasks.length} of ${tasks.length} tasks complete — keep going!`}
          </Text>
        </View>
      </View>
    );
  }

  function renderChat() {
    function formatMsgTime(iso: string) {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function TickIcon({ msg }: { msg: ChatMsg }) {
      if (!msg.read_by || msg.read_by.length === 0) {
        // Single grey tick — sent
        return <Text style={[styles.msIcon, styles.chatTickIcon, { color: C.stone500 }]}>done</Text>;
      }
      if (msg.all_read) {
        // Double green tick — everyone read
        return <Text style={[styles.msIcon, styles.chatTickIcon, { color: '#22c55e' }]}>done_all</Text>;
      }
      // Double grey tick — some read
      return <Text style={[styles.msIcon, styles.chatTickIcon, { color: C.outlineVariant }]}>done_all</Text>;
    }

    if (chatLoading) {
      return (
        <View style={[styles.chatRoot, { alignItems: 'center', justifyContent: 'center' }]}>
          <ActivityIndicator color={C.primary} />
        </View>
      );
    }

    return (
      <KeyboardAvoidingView
        style={styles.chatRoot}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? chatKvOffset : 0}
      >
        {chatDisconnected && (
          <View style={styles.chatReconnectBanner}>
            <ActivityIndicator size="small" color={C.onSurfaceVariant} style={{ marginRight: 8 }} />
            <Text style={styles.chatReconnectText}>Reconnecting…</Text>
          </View>
        )}

        <ScrollView
          ref={flatListRef}
          style={styles.chatScroll}
          contentContainerStyle={styles.chatList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
          keyboardShouldPersistTaps="handled"
        >
          {chatMessages.length === 0 ? (
            <View style={{ alignItems: 'center', paddingVertical: 48 }}>
              <Text style={[styles.msIcon, { fontSize: 40, color: C.outlineVariant }]}>chat_bubble</Text>
              <Text style={styles.emptyTitle}>No messages yet</Text>
              <Text style={styles.emptySub}>Say hello to your group!</Text>
            </View>
          ) : chatMessages.map((msg) => {
            const isMine = msg.sender_id === myUserId;
            return (
              <Pressable
                key={msg.id}
                onLongPress={() => setReceiptModal({ visible: true, msg })}
                style={[styles.chatBubbleRow, isMine ? styles.chatBubbleRowSelf : styles.chatBubbleRowOther]}
              >
                <View style={[styles.chatBubble, isMine ? styles.chatBubbleSelf : styles.chatBubbleOther]}>
                  {!isMine && <Text style={styles.chatSenderName}>{msg.username}</Text>}
                  <Text style={[styles.chatBubbleText, isMine && styles.chatBubbleTextSelf]}>
                    {msg.body}
                  </Text>
                  <View style={styles.chatBubbleMeta}>
                    <Text style={[styles.chatBubbleTime, isMine && styles.chatBubbleTimeSelf]}>
                      {formatMsgTime(msg.sent_at)}
                    </Text>
                    {isMine && <TickIcon msg={msg} />}
                  </View>
                </View>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* Input row — lifted by the outer KeyboardAvoidingView */}
        <View style={[styles.chatInputRow, { paddingBottom: insets.bottom || 12 }]}>
          <TextInput
            style={styles.chatInput}
            value={chatInput}
            onChangeText={setChatInput}
            placeholder="Type a message…"
            placeholderTextColor={C.stone500}
            onSubmitEditing={sendChatMessage}
            returnKeyType="send"
            multiline={false}
          />
          <TouchableOpacity
            activeOpacity={0.8}
            onPress={sendChatMessage}
            style={styles.chatSendBtn}
          >
            <Text style={[styles.msIcon, { color: C.white, fontSize: 22 }]}>send</Text>
          </TouchableOpacity>
        </View>

        {/* Receipt modal */}
        <Modal
          visible={receiptModal.visible}
          transparent
          animationType="fade"
          onRequestClose={() => setReceiptModal({ visible: false, msg: null })}
        >
          <Pressable
            style={styles.modalOverlay}
            onPress={() => setReceiptModal({ visible: false, msg: null })}
          >
            <View style={styles.receiptModalCard}>
              <Text style={styles.receiptModalTitle}>Read by</Text>
              {receiptModal.msg?.read_by?.length === 0 ? (
                <Text style={styles.receiptModalEmpty}>No one has read this yet</Text>
              ) : (
                receiptModal.msg?.read_by.map((r) => (
                  <View key={r.user_id} style={styles.receiptModalRow}>
                    <View style={styles.receiptModalAvatar}>
                      <Text style={styles.receiptModalAvatarText}>
                        {r.username[0]?.toUpperCase() ?? '?'}
                      </Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.receiptModalName}>{r.username}</Text>
                      <Text style={styles.receiptModalTime}>
                        {new Date(r.seen_at).toLocaleString([], {
                          month: 'short', day: 'numeric',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </Text>
                    </View>
                    <Text style={[styles.msIcon, { color: '#22c55e', fontSize: 18 }]}>done_all</Text>
                  </View>
                ))
              )}
            </View>
          </Pressable>
        </Modal>
      </KeyboardAvoidingView>
    );
  }

  function renderPeople() {
    if (loading) return <ActivityIndicator color={C.primary} size="large" style={{ paddingVertical: 40 }} />;

    // Build sorted leaderboard for podium (top 3)
    const sorted = [...leaderboard].sort((a, b) => b.total_points - a.total_points);
    const first  = sorted[0];
    const second = sorted[1];
    const third  = sorted[2];

    // Member list sorted by points
    const sortedMembers = [...members].sort((a, b) => {
      const pa = leaderboard.find(e => e.user_id === a.user_id)?.total_points ?? 0;
      const pb = leaderboard.find(e => e.user_id === b.user_id)?.total_points ?? 0;
      return pb - pa;
    });

    return (
      <View style={styles.tabContent}>

        {/* ── Leaderboard Podium ─────────────────── */}
        {leaderboard.length > 0 && (
          <View style={styles.podiumSection}>
            <Text style={styles.peopleSectionTitle}>Weekly Leaderboard</Text>
            <View style={styles.podiumRow}>
              <PodiumBlock entry={second} rank={2} barHeight={96}  isFirst={false} />
              <PodiumBlock entry={first}  rank={1} barHeight={128} isFirst={true}  />
              <PodiumBlock entry={third}  rank={3} barHeight={80}  isFirst={false} />
            </View>
          </View>
        )}

        {/* ── Member List ────────────────────────── */}
        <View style={styles.peopleSection}>
          <View style={styles.peopleSectionHeader}>
            <Text style={styles.peopleSectionTitle}>Group Members</Text>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => navigation.navigate('InviteMember', { groupId, groupType: group?.group_type })}
              style={styles.invitePillBtn}
            >
              <Text style={[styles.msIcon, { color: C.primary, fontSize: 18 }]}>group_add</Text>
              <Text style={styles.invitePillBtnText}>Invite Member</Text>
            </TouchableOpacity>
          </View>

          {sortedMembers.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={[styles.msIcon, { fontSize: 40, color: C.outlineVariant }]}>group</Text>
              <Text style={styles.emptyTitle}>No members loaded.</Text>
            </View>
          ) : (
            <View style={styles.memberList}>
              {sortedMembers.map((m, idx) => {
                const lbEntry = leaderboard.find(e => e.user_id === m.user_id);
                const isTopRank = idx === 0;
                return (
                  <MemberRow
                    key={m.user_id}
                    member={m}
                    points={lbEntry?.total_points}
                    isTopRank={isTopRank}
                  />
                );
              })}
            </View>
          )}
        </View>

        {/* ── Danger zone ────────────────────────── */}
        <View style={styles.dangerZone}>
          <TouchableOpacity activeOpacity={0.7} onPress={handleLeaveGroup}>
            <Text style={styles.leaveBtnText}>Leave Group</Text>
          </TouchableOpacity>
          <Text style={styles.leaveSubText}>Leaving will remove your points for this group</Text>
        </View>

      </View>
    );
  }

  function renderDiscover() {
    return (
      <View style={styles.tabContent}>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate('Marketplace', { groupId })}
          style={styles.discoverCard}
        >
          <Text style={[styles.msIcon, { color: C.primary, fontSize: 28 }]}>storefront</Text>
          <View style={styles.discoverCardText}>
            <Text style={styles.discoverCardTitle}>Task Marketplace</Text>
            <Text style={styles.discoverCardSub}>Browse and claim tasks listed by members</Text>
          </View>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 20 }]}>chevron_right</Text>
        </TouchableOpacity>

        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate('Proposals', { groupId, myRole: group?.my_role ?? 'member' })}
          style={styles.discoverCard}
        >
          <Text style={[styles.msIcon, { color: C.tertiary, fontSize: 28 }]}>assignment_add</Text>
          <View style={styles.discoverCardText}>
            <Text style={styles.discoverCardTitle}>Task Suggestions</Text>
            <Text style={styles.discoverCardSub}>{group?.my_role === 'moderator' ? 'Review and approve member suggestions' : 'Suggest new tasks for the group'}</Text>
          </View>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 20 }]}>chevron_right</Text>
        </TouchableOpacity>
      </View>
    );
  }

  function renderAnalytics() {
    if (analyticsLoading) return <ActivityIndicator color={C.primary} size="large" style={{ paddingVertical: 40 }} />;
    if (!groupStats) return (
      <View style={[styles.tabContent, styles.emptyState]}>
        <Text style={[styles.msIcon, { fontSize: 40, color: C.outlineVariant }]}>bar_chart</Text>
        <Text style={styles.emptyTitle}>No analytics yet</Text>
        <Text style={styles.emptySub}>Complete some tasks to see group stats.</Text>
      </View>
    );

    const memberMap: Record<string, string> = {};
    members.forEach((m) => { memberMap[String(m.user_id)] = m.username; });

    const matrixSorted = assignmentMatrix
      ? Object.entries(assignmentMatrix).sort((a, b) => a[1] - b[1])
      : [];

    return (
      <View style={styles.tabContent}>

        {/* ── Summary cards ─────────────────────── */}
        <View style={styles.analyticsGrid}>
          <View style={styles.analyticsCard}>
            <Text style={styles.analyticsCardBig}>{Math.round(groupStats.completion_rate * 100)}%</Text>
            <Text style={styles.analyticsCardLabel}>COMPLETION RATE</Text>
          </View>
          <View style={styles.analyticsCard}>
            <Text style={[styles.analyticsCardBig, { color: C.secondary }]}>{groupStats.completed_tasks}</Text>
            <Text style={styles.analyticsCardLabel}>COMPLETED</Text>
          </View>
          <View style={styles.analyticsCard}>
            <Text style={styles.analyticsCardBig}>{groupStats.resolved_tasks}</Text>
            <Text style={styles.analyticsCardLabel}>TOTAL DUE</Text>
          </View>
          {groupStats.most_completed_task && (
            <View style={[styles.analyticsCard, { alignItems: 'flex-start' }]}>
              <Text style={styles.analyticsCardLabel}>TOP TASK</Text>
              <Text style={styles.analyticsCardName} numberOfLines={2}>{groupStats.most_completed_task.name}</Text>
              <Text style={styles.analyticsCardSub}>{groupStats.most_completed_task.count}× completed</Text>
            </View>
          )}
        </View>

        {/* ── Workload distribution ──────────────── */}
        <Text style={styles.analyticsSectionTitle}>Workload Distribution</Text>
        <View style={[styles.analyticsTable, { marginBottom: 24 }]}>
          {groupStats.fairness_distribution.map((row: any, idx: number) => (
            <View key={row.user_id} style={styles.analyticsTableRow}>
              <View style={styles.analyticsRankBadge}>
                <Text style={styles.analyticsRankText}>{idx + 1}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.analyticsRowName}>{row.username}</Text>
                <View style={styles.analyticsRowMeta}>
                  <Text style={styles.analyticsMetaText}>✅ {row.total_tasks_completed}</Text>
                  <Text style={styles.analyticsMetaText}>⭐ {row.total_points} pts</Text>
                  <Text style={styles.analyticsMetaText}>🔥 {row.current_streak_days}d</Text>
                </View>
              </View>
              {/* On-time bar */}
              <View style={styles.analyticsBar}>
                <View style={[styles.analyticsBarFill, {
                  width: `${Math.round(row.on_time_completion_rate * 100)}%` as any,
                  backgroundColor: C.secondary,
                }]} />
              </View>
              <Text style={styles.analyticsBarPct}>{Math.round(row.on_time_completion_rate * 100)}%</Text>
            </View>
          ))}
        </View>

        {/* ── Assignment priority matrix ─────────── */}
        {matrixSorted.length > 0 && (
          <>
            <Text style={styles.analyticsSectionTitle}>Assignment Priority</Text>
            <Text style={styles.analyticsSectionSub}>Lower score = next in line. Blends task count (40%), time (35%), points (25%).</Text>
            <View style={[styles.analyticsTable, { marginBottom: 24 }]}>
              {matrixSorted.map(([uid, score]) => {
                const barColor = score < 0.4 ? C.secondary : score < 0.7 ? C.tertiary : C.primary;
                return (
                  <View key={uid} style={styles.analyticsTableRow}>
                    <Text style={styles.analyticsMatrixName} numberOfLines={1}>
                      {memberMap[uid] ?? uid.slice(0, 8)}
                    </Text>
                    <View style={[styles.analyticsBar, { flex: 1, marginHorizontal: 10 }]}>
                      <View style={[styles.analyticsBarFill, {
                        width: `${Math.round(score * 100)}%` as any,
                        backgroundColor: barColor,
                      }]} />
                    </View>
                    <Text style={styles.analyticsBarPct}>{Math.round(score * 100)}</Text>
                  </View>
                );
              })}
            </View>
          </>
        )}
      </View>
    );
  }

  function renderSettings() {
    return (
      <View style={styles.tabContent}>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate('GroupSettings', { groupId })}
          style={styles.discoverCard}
        >
          <Text style={[styles.msIcon, { color: C.primary, fontSize: 28 }]}>settings</Text>
          <View style={styles.discoverCardText}>
            <Text style={styles.discoverCardTitle}>Group Settings</Text>
            <Text style={styles.discoverCardSub}>Name, fairness, photo proof, recurring tasks</Text>
          </View>
          <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 20 }]}>chevron_right</Text>
        </TouchableOpacity>

        <View style={styles.dangerZone}>
          <TouchableOpacity activeOpacity={0.7} onPress={handleLeaveGroup}>
            <Text style={styles.leaveBtnText}>Leave Group</Text>
          </TouchableOpacity>
          <Text style={styles.leaveSubText}>Leaving will remove your points for this group</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.stone500 }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle} numberOfLines={1}>
            {group?.name ?? 'Group'}
          </Text>
        </View>
        <View style={styles.topBarRight}>
          <TouchableOpacity
            activeOpacity={0.7}
            style={styles.topBarBtn}
            onPress={() => navigation.navigate('GroupSettings', { groupId })}
          >
            <Text style={[styles.msIcon, { color: C.stone500 }]}>more_vert</Text>
          </TouchableOpacity>
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => navigation.navigate('Profile')}
            style={styles.topBarAvatar}
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
      </View>

      {/* ── Hero + Tabs (always a plain View — no flex:0 ScrollView hack) ── */}
      <View
        style={styles.heroTabsContainer}
        onLayout={e => setChatKvOffset(insets.top + 56 + e.nativeEvent.layout.height)}
      >
        {/* ── Group Hero ───────────────────────── */}
        <View style={styles.heroSection}>
          <View style={styles.heroIconRow}>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 20 }]}>cottage</Text>
            <Text style={styles.heroCategory}>HOUSEHOLD GROUP</Text>
          </View>
          <Text style={styles.heroTitle}>{group?.name ?? '…'}</Text>

          {/* Members row */}
          <View style={styles.heroMeta}>
            <View style={styles.heroAvatars}>
              {Array.from({ length: Math.min(group?.member_count ?? 0, 3) }).map((_, i) => (
                <View
                  key={i}
                  style={[styles.heroAvatarCircle, { marginLeft: i === 0 ? 0 : -6 }]}
                >
                  <Text style={styles.heroAvatarInitial}>
                    {String.fromCharCode(65 + i)}
                  </Text>
                </View>
              ))}
              {(group?.member_count ?? 0) > 3 && (
                <View style={[styles.heroAvatarCircle, styles.heroAvatarOverflow, { marginLeft: -6 }]}>
                  <Text style={styles.heroAvatarOverflowText}>
                    +{(group?.member_count ?? 0) - 3}
                  </Text>
                </View>
              )}
            </View>
            <Text style={styles.heroMemberCount}>{group?.member_count ?? 0} Members</Text>
            {group?.my_role === 'moderator' && (
              <View style={styles.modPill}>
                <Text style={styles.modPillText}>MODERATOR</Text>
              </View>
            )}
          </View>
        </View>

        {/* ── Tabs ─────────────────────────────── */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabsScroll}
          style={styles.tabsRow}
        >
          {TABS.map((tab) => {
            const badge = activeTab !== tab.id ? tabBadge(groupId, tab.id) : 0;
            return (
              <TouchableOpacity
                key={tab.id}
                activeOpacity={0.85}
                onPress={() => setActiveTab(tab.id)}
                style={activeTab === tab.id ? styles.tabActive : styles.tabInactive}
              >
                {activeTab === tab.id ? (
                  <LinearGradient
                    colors={[C.primary, C.primaryContainer]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                    style={styles.tabActiveGradient}
                  >
                    <Text style={styles.tabActiveText}>{tab.label}</Text>
                  </LinearGradient>
                ) : (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                    <Text style={styles.tabInactiveText}>{tab.label}</Text>
                    {badge > 0 && (
                      <View style={styles.tabBadge}>
                        <Text style={styles.tabBadgeText}>{badge}</Text>
                      </View>
                    )}
                  </View>
                )}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* ── Content area: chat fills remaining height; other tabs scroll ── */}
      {activeTab === 'chat' ? (
        renderChat()
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          style={styles.contentScroll}
          contentContainerStyle={styles.contentScrollContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.primary} />
          }
        >
          {activeTab === 'tasks'     && renderTasks()}
          {activeTab === 'people'    && renderPeople()}
          {activeTab === 'discover'  && renderDiscover()}
          {activeTab === 'analytics' && renderAnalytics()}
          {activeTab === 'settings'  && renderSettings()}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },

  // Top bar
  topBar: {
    height: 56, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', paddingHorizontal: 20, backgroundColor: C.bg,
  },
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  topBarRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  topBarBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.primary,
    letterSpacing: -0.4, flex: 1,
  },
  topBarAvatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: `${C.outlineVariant}33`,
  },
  topBarAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurfaceVariant,
  },
  topBarAvatarImg: {
    width: 36, height: 36, borderRadius: 18,
  },

  // Hero + tabs wrapper (plain View — no flex:0 ScrollView hack needed)
  heroTabsContainer: { paddingHorizontal: 24, paddingTop: 8, backgroundColor: C.bg },
  // Scrollable content for all non-chat tabs
  contentScroll: { flex: 1 },
  contentScrollContent: { paddingHorizontal: 24 },

  // Hero
  heroSection: { marginBottom: 24, gap: 6 },
  heroIconRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  heroCategory: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 10,
    color: C.secondary, letterSpacing: 2, textTransform: 'uppercase',
  },
  heroTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 32,
    color: C.onSurface, letterSpacing: -0.8, lineHeight: 38,
  },
  heroMeta: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 },
  heroAvatars: { flexDirection: 'row', alignItems: 'center' },
  heroAvatarCircle: {
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: C.bg,
  },
  heroAvatarInitial: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 9, color: C.onSecondaryContainer,
  },
  heroAvatarOverflow: { backgroundColor: C.surfaceContainerHighest },
  heroAvatarOverflowText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 9, color: C.onSurfaceVariant,
  },
  heroMemberCount: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.onSurfaceVariant,
  },
  modPill: {
    backgroundColor: C.secondaryContainer, paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 999,
  },
  modPillText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9,
    color: C.onSecondaryContainer, letterSpacing: 1,
  },

  // Tabs
  tabsRow: { marginBottom: 24, marginHorizontal: -24 },
  tabsScroll: { paddingHorizontal: 24, gap: 8 },
  tabActive: { borderRadius: 999, overflow: 'hidden' },
  tabActiveGradient: {
    paddingHorizontal: 22, paddingVertical: 11, borderRadius: 999,
  },
  tabActiveText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.white,
  },
  tabInactive: {
    paddingHorizontal: 22, paddingVertical: 11,
    borderRadius: 999, backgroundColor: C.surfaceContainer,
  },
  tabInactiveText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurfaceVariant,
  },
  tabBadge: {
    minWidth: 16, height: 16, paddingHorizontal: 4,
    borderRadius: 8, backgroundColor: C.error,
    alignItems: 'center', justifyContent: 'center',
  },
  tabBadgeText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10, color: C.white,
    lineHeight: 14,
  },

  // Tab content wrapper
  tabContent: { gap: 16 },

  // Tasks tab
  tasksSectionHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  tasksSectionLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tasksSectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 18, color: C.onSurface,
  },
  taskCountBadge: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center',
  },
  taskCountText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 12, color: C.onSurfaceVariant,
  },
  newTaskBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  newTaskBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 13, color: C.primary,
  },
  taskCardList: { gap: 12 },

  // Task card
  taskCard: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 18, padding: 18,
    flexDirection: 'row', alignItems: 'center', gap: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05, shadowRadius: 8, elevation: 1,
  },
  taskCardLeft: { flex: 1, flexDirection: 'row', alignItems: 'flex-start', gap: 14 },
  taskIconBox: {
    width: 48, height: 48, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  taskCardBody: { flex: 1, gap: 3 },
  taskCardTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  taskCardTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface,
  },
  taskCardTitleDone: {
    textDecorationLine: 'line-through', color: C.onSurfaceVariant,
  },
  statusBadge: {
    paddingHorizontal: 7, paddingVertical: 2, borderRadius: 999,
  },
  statusBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9, letterSpacing: 0.5,
  },
  taskCardAssignee: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.onSurfaceVariant,
  },
  taskCardAssigneeName: {
    fontFamily: 'PlusJakartaSans-SemiBold', color: C.onSurface,
  },
  taskCardCompletedBy: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13,
    color: C.onSurfaceVariant, fontStyle: 'italic',
  },
  taskCardMeta: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 4 },
  taskCardDeadlineRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  taskCardDeadlineText: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 12, color: C.onSurfaceVariant,
  },
  checkBtnWrap: {
    width: 48, height: 48, alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  checkBtnCircle: {
    width: 48, height: 48, borderRadius: 24,
    borderWidth: 2, borderColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
  },

  // Weekly milestone
  milestoneCard: {
    backgroundColor: C.surfaceContainer,
    borderRadius: 18, padding: 22, gap: 10, marginTop: 8,
  },
  milestoneHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  milestoneTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.onSurface,
  },
  milestonePct: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 16, color: C.primary,
  },
  milestoneTrack: {
    height: 12, backgroundColor: C.surfaceContainerHighest, borderRadius: 6, overflow: 'hidden',
  },
  milestoneFill: {
    height: '100%', backgroundColor: C.secondary, borderRadius: 6,
  },
  milestoneSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant, lineHeight: 18,
  },

  // People tab — podium
  podiumSection: { gap: 14 },
  podiumRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 12,
    paddingBottom: 4,
  },
  podiumItem: { alignItems: 'center', flex: 1 },
  podiumItemCenter: { flex: 1.15 },
  crownIcon: {
    fontSize: 24, color: '#f7bb7e', marginBottom: 4,
  },
  podiumAvatar: {
    borderRadius: 999, overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.surfaceContainerHighest,
    borderWidth: 3, borderColor: C.surfaceContainerHighest,
    marginBottom: 8,
  },
  podiumAvatarFirst: {
    width: 64, height: 64,
    borderColor: C.primary,
    backgroundColor: C.secondaryContainer,
  },
  podiumAvatarOther: {
    width: 48, height: 48,
    backgroundColor: C.surfaceContainerHigh,
  },
  podiumAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.onSurface,
  },
  podiumBar: {
    width: '100%', borderTopLeftRadius: 12, borderTopRightRadius: 12,
    alignItems: 'center', justifyContent: 'center', padding: 8, gap: 2,
  },
  podiumBarOther: { backgroundColor: C.surfaceContainerHigh },
  podiumRank1Num: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 24, color: C.white,
  },
  podiumRank1Name: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11, color: C.white,
    textAlign: 'center',
  },
  podiumRank1Pts: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 10, color: 'rgba(255,255,255,0.8)',
  },
  podiumOtherNum: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 18, color: C.stone500,
  },
  podiumOtherName: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10, color: C.onSurface,
    textAlign: 'center',
  },
  podiumOtherPts: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 10, color: C.stone500,
  },

  // People tab — member list
  peopleSection: { gap: 12 },
  peopleSectionHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  peopleSectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 18, color: C.onSurface,
  },
  invitePillBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 999, borderWidth: 2, borderColor: `${C.primary}33`,
  },
  invitePillBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 13, color: C.primary,
  },
  memberList: { gap: 10 },
  memberCard: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16, borderRadius: 16,
    backgroundColor: C.surfaceContainerLow,
  },
  memberCardLeft: { flexDirection: 'row', alignItems: 'center', gap: 14, flex: 1 },
  memberAvatar: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
  },
  memberAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 17, color: C.onSecondaryContainer,
  },
  memberInfo: { flex: 1, gap: 4 },
  memberName: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurface,
  },
  roleBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999,
  },
  roleBadgeMember: { backgroundColor: C.secondaryContainer },
  roleBadgeMod: { backgroundColor: C.primaryFixed },
  roleBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9, letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  memberPointsRight: { alignItems: 'flex-end', gap: 1 },
  memberPointsNum: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 18, color: C.stone500,
  },
  memberPointsLabel: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 9,
    color: C.stone500, letterSpacing: 0.5, textTransform: 'uppercase',
  },

  // Danger zone
  dangerZone: {
    marginTop: 24, paddingTop: 24,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: C.surfaceContainerHighest,
    alignItems: 'center', gap: 6,
  },
  leaveBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.error,
  },
  leaveSubText: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 11,
    color: C.stone500, textAlign: 'center', maxWidth: 200, lineHeight: 17,
  },

  // Discover tab
  discoverCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    padding: 18, borderRadius: 18,
    backgroundColor: C.surfaceContainerLow,
  },
  discoverCardText: { flex: 1 },
  discoverCardTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface,
  },
  discoverCardSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant, marginTop: 2,
  },

  // Empty / loading
  emptyState: { paddingVertical: 48, alignItems: 'center', gap: 8 },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurfaceVariant,
  },
  emptySub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant,
    opacity: 0.7, textAlign: 'center',
  },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },

  // Chat tab
  chatReconnectBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.surfaceContainerHigh,
    borderRadius: 10,
    paddingVertical: 6,
    paddingHorizontal: 14,
    marginBottom: 8,
  },
  chatReconnectText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurfaceVariant,
  },
  chatRoot: {
    flex: 1,
    backgroundColor: C.bg,
  },
  chatScroll: { flex: 1 },
  chatList: { flexGrow: 1, padding: 16, gap: 8 },
  chatBubbleRow: { flexDirection: 'row', marginBottom: 4 },
  chatBubbleRowSelf: { justifyContent: 'flex-end' },
  chatBubbleRowOther: { justifyContent: 'flex-start' },
  chatBubble: {
    maxWidth: '78%', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10,
  },
  chatBubbleSelf: {
    backgroundColor: C.primaryFixed,
    borderBottomRightRadius: 4,
  },
  chatBubbleOther: {
    backgroundColor: C.surfaceContainerLowest,
    borderBottomLeftRadius: 4,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  chatSenderName: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11,
    color: C.primary, marginBottom: 3,
  },
  chatBubbleText: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 14,
    color: C.onSurface, lineHeight: 20,
  },
  chatBubbleTextSelf: { color: C.onSurface },
  chatBubbleMeta: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'flex-end', gap: 4, marginTop: 4,
  },
  chatBubbleTime: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 10, color: C.stone500,
  },
  chatBubbleTimeSelf: { color: C.onSurfaceVariant },
  chatTickIcon: { fontSize: 14 },
  chatInputRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 16, paddingTop: 12,
    borderTopWidth: 1, borderTopColor: C.outlineVariant,
    backgroundColor: C.bg,
  },
  chatInput: {
    flex: 1, height: 44, borderRadius: 22,
    backgroundColor: C.surfaceContainerLow,
    paddingHorizontal: 16, paddingVertical: 0,
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 14, color: C.onSurface,
  },
  chatSendBtn: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },

  // Receipt modal
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center', alignItems: 'center', padding: 32,
  },
  receiptModalCard: {
    backgroundColor: C.surfaceContainerLowest, borderRadius: 20,
    padding: 24, width: '100%', maxWidth: 340, gap: 14,
  },
  receiptModalTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 17, color: C.onSurface,
  },
  receiptModalEmpty: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.stone500,
  },
  receiptModalRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
  },
  receiptModalAvatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center', justifyContent: 'center',
  },
  receiptModalAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurfaceVariant,
  },
  receiptModalName: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurface,
  },
  receiptModalTime: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 11, color: C.stone500, marginTop: 1,
  },

  // ── Analytics tab ──────────────────────────────────────────────
  analyticsGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 24,
  },
  analyticsCard: {
    width: '47.5%',
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 16, padding: 16,
    alignItems: 'center',
  },
  analyticsCardBig: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 32, color: C.primary, letterSpacing: -1,
  },
  analyticsCardLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10, color: C.onSurfaceVariant,
    letterSpacing: 1, marginTop: 4,
    textAlign: 'center',
  },
  analyticsCardName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 14, color: C.onSurface, marginTop: 4,
  },
  analyticsCardSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11, color: C.onSurfaceVariant, marginTop: 2,
  },
  analyticsSectionTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 13, color: C.onSurface,
    letterSpacing: 0.4, marginBottom: 8,
  },
  analyticsSectionSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12, color: C.onSurfaceVariant, marginBottom: 10,
    lineHeight: 18,
  },
  analyticsTable: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 16, overflow: 'hidden',
  },
  analyticsTableRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.outlineVariant,
  },
  analyticsRankBadge: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  analyticsRankText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11, color: C.onSurfaceVariant,
  },
  analyticsRowName: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurface,
  },
  analyticsRowMeta: { flexDirection: 'row', gap: 8, marginTop: 2, flexWrap: 'wrap' },
  analyticsMetaText: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 11, color: C.onSurfaceVariant,
  },
  analyticsBar: {
    width: 56, height: 6,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 3, overflow: 'hidden', flexShrink: 0,
  },
  analyticsBarFill: {
    height: '100%', borderRadius: 3,
  },
  analyticsBarPct: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11,
    color: C.onSurfaceVariant, width: 28, textAlign: 'right', flexShrink: 0,
  },
  analyticsMatrixName: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13, color: C.onSurface,
    width: 90, flexShrink: 0,
  },
});
