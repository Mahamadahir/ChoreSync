import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
import { useNotificationStore } from '../../stores/notificationStore';
import { notificationService } from '../../services/notificationService';
import { taskService } from '../../services/taskService';
import type { Notification, NotificationType } from '../../types/notification';
import { Palette as C } from '../../theme';
import AppHeader from '../../components/common/AppHeader';

// ── Design tokens ─────────────────────────────────────────────

// ── Notification type → display config ────────────────────────
type NotifConfig = {
  icon: string;
  iconFill: boolean;
  accentColor: string;
  iconBg: string;
  label: string;
};

const NOTIF_CONFIG: Record<NotificationType, NotifConfig> = {
  task_swap:              { icon: 'swap_horiz',    iconFill: false, accentColor: C.primary,          iconBg: C.primaryFixed,           label: 'Swap Request'  },
  task_proposal:          { icon: 'assignment_add',iconFill: false, accentColor: C.tertiary,         iconBg: C.tertiaryFixed,          label: 'New Proposal'  },
  badge_earned:           { icon: 'emoji_events',  iconFill: true,  accentColor: C.secondary,        iconBg: C.secondaryContainer,     label: 'Milestone Met' },
  deadline_reminder:      { icon: 'notifications', iconFill: false, accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Reminder'      },
  task_assigned:          { icon: 'assignment',    iconFill: false, accentColor: C.primary,          iconBg: C.primaryFixed,           label: 'Task Assigned' },
  emergency_reassignment: { icon: 'crisis_alert',  iconFill: false, accentColor: C.primary,          iconBg: C.primaryFixed,           label: 'Emergency'     },
  marketplace_claim:      { icon: 'storefront',    iconFill: false, accentColor: C.secondary,        iconBg: C.secondaryContainer,     label: 'Marketplace'   },
  group_invite:           { icon: 'group_add',     iconFill: false, accentColor: C.secondary,        iconBg: C.secondaryContainer,     label: 'Group Invite'  },
  task_suggestion:        { icon: 'magic_button',  iconFill: true,  accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Sync Assistant'},
  suggestion_pattern:     { icon: 'magic_button',  iconFill: true,  accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Sync Assistant'},
  suggestion_availability:{ icon: 'magic_button',  iconFill: true,  accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Sync Assistant'},
  suggestion_preference:  { icon: 'magic_button',  iconFill: true,  accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Sync Assistant'},
  message:                { icon: 'chat',          iconFill: false, accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Message'       },
  suggestion_streak:      { icon: 'magic_button',  iconFill: true,  accentColor: C.onSurfaceVariant, iconBg: C.surfaceContainerHighest,label: 'Sync Assistant'},
  calendar_sync_complete: { icon: 'sync',          iconFill: false, accentColor: C.secondary,        iconBg: C.secondaryContainer,     label: 'Calendar Sync' },
};

// ── Helpers ───────────────────────────────────────────────────
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function groupByRecency(list: Notification[]) {
  const visible = list.filter((n) => !n.dismissed);
  const recent: Notification[] = [];
  const earlier: Notification[] = [];
  visible.forEach((n) => {
    const diffH = (Date.now() - new Date(n.created_at).getTime()) / 3600000;
    if (diffH < 3) recent.push(n);
    else earlier.push(n);
  });
  return { recent, earlier };
}

// ── Notification card ─────────────────────────────────────────
function NotifCard({
  notif,
  onMarkRead,
  onDismiss,
  onSwapAccept,
  onSwapDecline,
  onNavigate,
}: {
  notif: Notification;
  onMarkRead: (id: string | number) => void;
  onDismiss: (id: string | number) => void;
  onSwapAccept: (notif: Notification) => void;
  onSwapDecline: (notif: Notification) => void;
  onNavigate: (notif: Notification) => void;
}) {
  const cfg = NOTIF_CONFIG[notif.type] ?? NOTIF_CONFIG.deadline_reminder;
  const isUnread = !notif.read;

  function handleCardPress() {
    if (isUnread) onMarkRead(notif.id);
    onNavigate(notif);
  }

  return (
    <TouchableOpacity
      activeOpacity={0.88}
      onPress={handleCardPress}
      style={[
        styles.card,
        isUnread ? styles.cardUnread : styles.cardRead,
      ]}
    >
      {/* Left accent bar for unread */}
      {isUnread && <View style={[styles.accentBar, { backgroundColor: cfg.accentColor }]} />}

      {/* Icon circle */}
      <View style={[styles.iconCircle, { backgroundColor: cfg.iconBg }]}>
        <Text
          style={[
            styles.msIcon,
            {
              color: cfg.accentColor,
              fontSize: 22,
            },
          ]}
        >
          {cfg.icon}
        </Text>
      </View>

      {/* Body */}
      <View style={styles.cardBody}>
        {/* Type label + time */}
        <View style={styles.cardMeta}>
          <Text
            style={[
              styles.cardLabel,
              { color: isUnread ? cfg.accentColor : C.onSurfaceVariant },
              !isUnread && styles.cardLabelRead,
            ]}
          >
            {cfg.label.toUpperCase()}
          </Text>
          <Text style={[styles.cardTime, !isUnread && styles.cardTimeMuted]}>
            {timeAgo(notif.created_at)}
          </Text>
        </View>

        {/* Content */}
        <Text style={[styles.cardContent, !isUnread && styles.cardContentRead]}>
          {notif.content || notif.title}
        </Text>

        {/* Actions for swap requests */}
        {notif.type === 'task_swap' && isUnread && (
          <View style={styles.actionRow}>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => onSwapAccept(notif)}
              style={styles.btnAccept}
            >
              <LinearGradient
                colors={[C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.btnAcceptGradient}
              >
                <Text style={styles.btnAcceptText}>Accept</Text>
              </LinearGradient>
            </TouchableOpacity>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => onSwapDecline(notif)}
              style={styles.btnDecline}
            >
              <Text style={styles.btnDeclineText}>Decline</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Review link for proposals */}
        {notif.type === 'task_proposal' && isUnread && (
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => { onMarkRead(notif.id); onNavigate(notif); }}
            style={styles.reviewRow}
          >
            <Text style={[styles.reviewText, { color: C.tertiary }]}>Review Details</Text>
            <Text style={[styles.msIcon, { color: C.tertiary, fontSize: 18, marginLeft: 4 }]}>
              arrow_forward
            </Text>
          </TouchableOpacity>
        )}

        {/* "View" link for assistant suggestions */}
        {(notif.type === 'task_suggestion' ||
          notif.type === 'suggestion_pattern' ||
          notif.type === 'suggestion_availability' ||
          notif.type === 'suggestion_preference' ||
          notif.type === 'suggestion_streak') && (
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => { onMarkRead(notif.id); onNavigate(notif); }}
            style={{ marginTop: 10 }}
          >
            <Text style={styles.viewScheduleText}>View Tasks</Text>
          </TouchableOpacity>
        )}
      </View>
    </TouchableOpacity>
  );
}

// ── Section divider ───────────────────────────────────────────
function Divider({ label }: { label: string }) {
  return (
    <View style={styles.dividerRow}>
      <View style={styles.dividerLine} />
      <Text style={styles.dividerLabel}>{label.toUpperCase()}</Text>
      <View style={styles.dividerLine} />
    </View>
  );
}

// ── Household momentum card ───────────────────────────────────
function MomentumCard({ pct }: { pct: number }) {
  return (
    <View style={styles.momentumCard}>
      <View style={styles.momentumHeader}>
        <View>
          <Text style={styles.momentumTitle}>Household Momentum</Text>
          <Text style={styles.momentumSub}>Daily chores nearly complete</Text>
        </View>
        <Text style={styles.momentumPct}>{pct}%</Text>
      </View>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${pct}%` as any }]} />
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function NotificationsScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const { notifications, setNotifications, markRead: storeMarkRead, markUnread: storeMarkUnread, dismiss: storeDismiss } =
    useNotificationStore();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setLoadError(null);
    try {
      const res = await notificationService.list();
      setNotifications(res.data.results ?? res.data);
    } catch {
      setLoadError('Could not load notifications. Pull down to retry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [setNotifications]);

  useEffect(() => { load(); }, [load]);

  const handleMarkRead = useCallback(async (id: string | number) => {
    storeMarkRead(id); // optimistic
    try {
      await notificationService.markRead(id);
    } catch {
      storeMarkUnread(id); // revert on failure
    }
  }, [storeMarkRead, storeMarkUnread]);

  const handleMarkAll = useCallback(async () => {
    if (markingAll) return;
    setMarkingAll(true);
    // Optimistic update — mark all read in store immediately
    notifications.filter((n) => !n.read).forEach((n) => storeMarkRead(n.id));
    try {
      await notificationService.markAllRead();
    } catch {
      // Silent — optimistic update stays; not worth reverting
    } finally {
      setMarkingAll(false);
    }
  }, [notifications, storeMarkRead, markingAll]);

  const handleSwapAccept = useCallback(async (notif: Notification) => {
    if (!notif.task_swap_id) {
      handleMarkRead(notif.id);
      return;
    }
    try {
      await taskService.respondSwap(notif.task_swap_id, true);
      storeDismiss(notif.id);
      Alert.alert('Accepted', 'You accepted the swap request.');
    } catch {
      Alert.alert('Error', 'Could not process the swap. Please try again.');
    }
  }, [handleMarkRead, storeDismiss]);

  const handleSwapDecline = useCallback(async (notif: Notification) => {
    if (!notif.task_swap_id) {
      storeDismiss(notif.id);
      return;
    }
    try {
      await taskService.respondSwap(notif.task_swap_id, false);
      storeDismiss(notif.id);
    } catch {
      Alert.alert('Error', 'Could not decline the swap. Please try again.');
    }
  }, [storeDismiss]);

  // Navigate to the most relevant screen for a notification type.
  const handleCardNavigate = useCallback((notif: Notification) => {
    try {
      const type = notif.type;

      // Task-centric: go to task detail if we have an occurrence ID
      if (
        (type === 'task_assigned' || type === 'deadline_reminder' ||
         type === 'emergency_reassignment' || type === 'marketplace_claim' ||
         type === 'task_swap') &&
        notif.task_occurrence_id
      ) {
        navigation.navigate('TasksTab', {
          screen: 'TaskDetail',
          params: { taskId: notif.task_occurrence_id },
        });
        return;
      }

      // Proposal: open the dedicated Proposals screen
      if (type === 'task_proposal' && notif.group_id) {
        navigation.navigate('GroupsTab', {
          screen: 'Proposals',
          params: { groupId: notif.group_id },
        });
        return;
      }

      // Message: open group detail on the chat tab
      if (type === 'message' && notif.group_id) {
        navigation.navigate('GroupsTab', {
          screen: 'GroupDetail',
          params: { groupId: notif.group_id, initialTab: 'chat' },
        });
        return;
      }

      // Group invite: open invitation accept/decline screen
      if (type === 'group_invite') {
        const inviteMatch = notif.action_url?.match(/^\/invitations\/(\d+)$/);
        if (inviteMatch) {
          navigation.navigate('GroupsTab', {
            screen: 'Invitation',
            params: { invitationId: Number(inviteMatch[1]) },
          });
          return;
        }
        if (notif.group_id) {
          navigation.navigate('GroupsTab', {
            screen: 'GroupDetail',
            params: { groupId: notif.group_id, initialTab: 'people' },
          });
        }
        return;
      }

      // Suggestions: open tasks list
      if (type.startsWith('suggestion_')) {
        navigation.navigate('TasksTab', { screen: 'Tasks' });
        return;
      }

      // Badge earned → profile/stats
      if (type === 'badge_earned') {
        (navigation as any).navigate('Profile');
        return;
      }

      // Calendar sync complete → calendar tab
      if (type === 'calendar_sync_complete') {
        navigation.navigate('CalendarTab', { screen: 'CalendarMain' });
        return;
      }
    } catch {
      // Ignore navigation errors (deleted entity, stale ID, etc.)
    }
  }, [navigation]);

  const { recent, earlier } = groupByRecency(notifications);
  const unreadCount = notifications.filter((n) => !n.read && !n.dismissed).length;

  // Momentum: derive from pending notifications count (rough estimate)
  const totalVisible = notifications.filter((n) => !n.dismissed).length;
  const readCount = notifications.filter((n) => n.read && !n.dismissed).length;
  const momentumPct = totalVisible > 0 ? Math.round((readCount / totalVisible) * 100) : 85;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      <AppHeader />

      <ScrollView
        showsVerticalScrollIndicator={false}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={C.primary}
          />
        }
      >
        {/* ── Header ──────────────────────────────── */}
        <View style={styles.pageHeader}>
          <View style={styles.pageHeaderTop}>
            <Text style={styles.pageTitle}>Activity</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <TouchableOpacity
                activeOpacity={0.7}
                onPress={handleMarkAll}
                disabled={markingAll || unreadCount === 0}
              >
                <Text
                  style={[
                    styles.markAllText,
                    unreadCount === 0 && styles.markAllDisabled,
                  ]}
                >
                  Mark all read
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                activeOpacity={0.7}
                onPress={() => navigation.navigate('NotificationPreferences')}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              >
                <Text style={[styles.headerIcon, { color: C.onSurfaceVariant }]}>settings</Text>
              </TouchableOpacity>
            </View>
          </View>
          <Text style={styles.pageSubtitle}>
            Stay in sync with your household's rhythm.
          </Text>
        </View>

        {/* ── Feed ────────────────────────────────── */}
        {loading ? (
          <View style={styles.centered}>
            <ActivityIndicator color={C.primary} size="large" />
          </View>
        ) : loadError ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, styles.emptyIcon]}>cloud_off</Text>
            <Text style={styles.emptyTitle}>Could not load</Text>
            <Text style={styles.emptySub}>{loadError}</Text>
          </View>
        ) : notifications.filter((n) => !n.dismissed).length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, styles.emptyIcon]}>notifications_none</Text>
            <Text style={styles.emptyTitle}>You're all caught up!</Text>
            <Text style={styles.emptySub}>No new activity right now.</Text>
          </View>
        ) : (
          <View style={styles.feed}>
            {/* Recent notifications */}
            {recent.map((n) => (
              <NotifCard
                key={n.id}
                notif={n}
                onMarkRead={handleMarkRead}
                onDismiss={storeDismiss}
                onSwapAccept={handleSwapAccept}
                onSwapDecline={handleSwapDecline}
                onNavigate={handleCardNavigate}
              />
            ))}

            {/* Divider between recent and older */}
            {recent.length > 0 && earlier.length > 0 && (
              <Divider label="Earlier Today" />
            )}
            {recent.length === 0 && earlier.length > 0 && (
              <Divider label="Earlier" />
            )}

            {/* Earlier notifications */}
            {earlier.map((n) => (
              <NotifCard
                key={n.id}
                notif={n}
                onMarkRead={handleMarkRead}
                onDismiss={storeDismiss}
                onSwapAccept={handleSwapAccept}
                onSwapDecline={handleSwapDecline}
                onNavigate={handleCardNavigate}
              />
            ))}
          </View>
        )}

        {/* ── Household Momentum ──────────────────── */}
        {!loading && <MomentumCard pct={momentumPct} />}

        <View style={{ height: 32 }} />
      </ScrollView>
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },


  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 24, paddingTop: 8 },

  // Header
  pageHeader: { marginBottom: 28 },
  pageHeaderTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  pageTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 36,
    color: C.onSurface,
    letterSpacing: -1,
  },
  markAllText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: C.secondary,
    textDecorationLine: 'underline',
    textDecorationStyle: 'solid',
  },
  markAllDisabled: { opacity: 0.35 },
  headerIcon: { fontFamily: 'MaterialSymbols', fontSize: 22 },
  pageSubtitle: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 14,
    color: C.onSurfaceVariant,
    opacity: 0.8,
  },

  // Feed
  feed: { gap: 12 },
  centered: { paddingVertical: 60, alignItems: 'center' },
  emptyState: { paddingVertical: 60, alignItems: 'center', gap: 8 },
  emptyIcon: { fontSize: 48, color: C.outlineVariant },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16,
    color: C.onSurfaceVariant,
  },
  emptySub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.onSurfaceVariant,
    opacity: 0.6,
  },

  // Notification card
  card: {
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    gap: 16,
    overflow: 'hidden',
    position: 'relative',
  },
  cardUnread: {
    backgroundColor: C.surfaceContainerLowest,
    shadowColor: '#1b1c1a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 2,
  },
  cardRead: {
    backgroundColor: C.surfaceContainerLow,
  },
  accentBar: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    width: 5,
    borderTopLeftRadius: 16,
    borderBottomLeftRadius: 16,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  cardBody: { flex: 1 },
  cardMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  cardLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10,
    letterSpacing: 1.2,
  },
  cardLabelRead: { opacity: 0.5 },
  cardTime: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 11,
    color: C.onSurfaceVariant,
  },
  cardTimeMuted: { opacity: 0.6 },
  cardContent: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 14,
    lineHeight: 21,
    color: C.onSurface,
  },
  cardContentRead: { opacity: 0.7 },

  // Swap action buttons
  actionRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
  },
  btnAccept: {
    borderRadius: 999,
    overflow: 'hidden',
  },
  btnAcceptGradient: {
    paddingHorizontal: 22,
    paddingVertical: 10,
    borderRadius: 999,
  },
  btnAcceptText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13,
    color: C.white,
  },
  btnDecline: {
    paddingHorizontal: 22,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: C.surfaceContainer,
  },
  btnDeclineText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },

  // Proposal review link
  reviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
  },
  reviewText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13,
  },

  // Assistant view link
  viewScheduleText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12,
    color: C.onSurface,
    borderBottomWidth: 2,
    borderBottomColor: `${C.primary}33`,
    alignSelf: 'flex-start',
    paddingBottom: 2,
  },

  // Divider
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 8,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: C.surfaceContainerHighest,
  },
  dividerLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 10,
    color: C.onSurfaceVariant,
    opacity: 0.4,
    letterSpacing: 2,
  },

  // Household momentum card
  momentumCard: {
    marginTop: 28,
    padding: 24,
    borderRadius: 20,
    backgroundColor: C.surfaceContainer,
    borderWidth: 1,
    borderColor: `${C.surfaceContainerHighest}4d`,
  },
  momentumHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 16,
  },
  momentumTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16,
    color: C.onSurface,
    marginBottom: 4,
  },
  momentumSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },
  momentumPct: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 28,
    color: C.secondary,
    letterSpacing: -1,
  },
  progressTrack: {
    height: 12,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 6,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: C.secondary,
    borderRadius: 6,
  },

  // Shared
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
    color: C.onSurface,
  },
});
