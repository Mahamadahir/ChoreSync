import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  RefreshControl,
  ActionSheetIOS,
  Platform,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { GroupsStackParamList } from '../../navigation/types';
import { groupService } from '../../services/groupService';
import { useAuthStore } from '../../stores/authStore';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<GroupsStackParamList, 'TaskTemplateDetail'>;
type Route = RouteProp<GroupsStackParamList, 'TaskTemplateDetail'>;

type Preference = 'prefer' | 'neutral' | 'avoid';

// ── Helpers ───────────────────────────────────────────────────
const CATEGORY_ICONS: Record<string, string> = {
  cleaning: 'cleaning_services',
  cooking: 'skillet',
  laundry: 'local_laundry_service',
  maintenance: 'build',
  other: 'category',
};

function recurrenceLabel(t: any): string {
  if (!t) return '—';
  switch (t.recurring_choice) {
    case 'weekly': {
      const days = (t.days_of_week as string[] | null);
      const dayLabel = days && days.length
        ? days.map((d: string) => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')
        : '';
      return dayLabel ? `Weekly · ${dayLabel}` : 'Weekly';
    }
    case 'monthly': return 'Monthly';
    case 'every_n_days': return t.recur_value ? `Every ${t.recur_value}d` : 'Recurring';
    case 'custom': {
      const days = t.days_of_week as string[] | null;
      return days?.length ? days.map((d: string) => d.charAt(0).toUpperCase() + d.slice(1)).join(', ') : 'Custom';
    }
    case 'none': return 'One-off';
    default: return '—';
  }
}

function difficultyLabel(d: number): string {
  if (d <= 1) return 'Easy';
  if (d === 2) return 'Low';
  if (d === 3) return 'Medium';
  if (d === 4) return 'Hard';
  return 'Expert';
}

function formatDeadline(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
}

function occurrenceStatusColor(status: string) {
  if (status === 'completed') return { bg: C.secondaryContainer, text: C.secondary };
  if (status === 'overdue') return { bg: C.errorContainer, text: C.error };
  return { bg: C.tertiaryFixed, text: C.onTertiaryFixed };
}

function occurrenceStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// ── Design tokens ──────────────────────────────────────────────

export default function TaskTemplateDetailScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { templateId, groupId } = route.params;
  const insets = useSafeAreaInsets();
  const authUser = useAuthStore((s) => s.user);

  const [template, setTemplate] = useState<any>(null);
  const [occurrences, setOccurrences] = useState<any[]>([]);
  const [preference, setPreference] = useState<Preference>('neutral');
  const [isModerator, setIsModerator] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [prefSaving, setPrefSaving] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [favourite, setFavourite] = useState(false);

  async function loadAll() {
    try {
      const [templateRes, prefsRes, tasksRes, membersRes] = await Promise.allSettled([
        groupService.getTemplate(templateId),
        groupService.myPreferences(groupId),
        groupService.tasks(groupId),
        groupService.members(groupId),
      ]);

      if (templateRes.status === 'fulfilled') {
        setTemplate(templateRes.value.data);
      }

      if (prefsRes.status === 'fulfilled') {
        const match = prefsRes.value.data.find((p: any) => p.template_id === templateId || +p.template_id === templateId);
        if (match) {
          setPreference(match.preference as Preference);
          setFavourite(match.preference === 'prefer');
        }
      }

      if (tasksRes.status === 'fulfilled') {
        const all: any[] = tasksRes.value.data;
        const filtered = all
          .filter((o: any) => o.template_id === templateId || +o.template_id === templateId)
          .filter((o: any) => o.status === 'pending' || o.status === 'snoozed')
          .sort((a: any, b: any) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime())
          .slice(0, 3);
        setOccurrences(filtered);
      }

      if (membersRes.status === 'fulfilled') {
        const me = membersRes.value.data.find(
          (m: any) => m.user_id === String(authUser?.id) || m.username === authUser?.username
        );
        setIsModerator(me?.role === 'moderator' || me?.role === 'admin');
      }
    } catch {}
  }

  useEffect(() => {
    setLoading(true);
    loadAll().finally(() => setLoading(false));
  }, [templateId]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadAll();
    setRefreshing(false);
  }, [templateId]);

  async function handleSetPreference(pref: Preference) {
    if (prefSaving) return;
    setPrefSaving(true);
    const prev = preference;
    setPreference(pref);
    if (pref === 'prefer') setFavourite(true);
    else setFavourite(false);
    try {
      await groupService.setPreference(templateId, pref);
    } catch {
      setPreference(prev);
      setFavourite(prev === 'prefer');
    } finally {
      setPrefSaving(false);
    }
  }

  async function handleToggleFavourite() {
    const newPref: Preference = favourite ? 'neutral' : 'prefer';
    await handleSetPreference(newPref);
  }

  function navigateToEdit() {
    navigation.navigate('TaskAuthor', { groupId, templateId });
  }

  function showOverflow() {
    if (Platform.OS === 'ios') {
      const options = isModerator
        ? ['Edit template', 'Delete template', 'Cancel']
        : ['Cancel'];
      ActionSheetIOS.showActionSheetWithOptions(
        { options, destructiveButtonIndex: isModerator ? 1 : undefined, cancelButtonIndex: options.length - 1 },
        (idx) => {
          if (isModerator && idx === 0) navigateToEdit();
          if (isModerator && idx === 1) confirmDelete();
        }
      );
    } else {
      if (!isModerator) return;
      Alert.alert('Template options', undefined, [
        { text: 'Edit template', onPress: navigateToEdit },
        { text: 'Delete template', style: 'destructive', onPress: confirmDelete },
        { text: 'Cancel', style: 'cancel' },
      ]);
    }
  }

  function confirmDelete() {
    Alert.alert(
      'Delete template?',
      `"${template?.name}" and all its future occurrences will be removed.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete', style: 'destructive',
          onPress: async () => {
            try {
              await groupService.deleteTemplate(templateId);
              navigation.goBack();
            } catch {
              Alert.alert('Error', 'Could not delete the template. Try again.');
            }
          },
        },
      ]
    );
  }

  if (loading) {
    return (
      <SafeAreaView style={s.safe} edges={['top']}>
        <View style={s.centered}>
          <ActivityIndicator color={C.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  if (!template) {
    return (
      <SafeAreaView style={s.safe} edges={['top']}>
        <View style={s.centered}>
          <Text style={s.errorMsg}>Template not found.</Text>
          <TouchableOpacity onPress={() => navigation.goBack()} style={s.backFallback}>
            <Text style={s.backFallbackText}>Go back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const categoryIcon = CATEGORY_ICONS[template.category] ?? 'category';
  const categoryLabel = template.category.charAt(0).toUpperCase() + template.category.slice(1);

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      {/* Blobs */}
      <View style={[s.blob, s.blobTopRight]} />
      <View style={[s.blob, s.blobBottomLeft]} />

      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity style={s.iconBtn} onPress={() => navigation.goBack()} activeOpacity={0.8}>
          <Text style={s.headerIcon}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>Task Detail</Text>
        <TouchableOpacity style={s.iconBtn} onPress={showOverflow} activeOpacity={0.8}>
          <Text style={[s.headerIcon, { color: 'rgba(27,28,26,0.55)' }]}>more_vert</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.scrollContent, { paddingBottom: 100 + insets.bottom }]}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
      >

        {/* ── Section 1: Identity ───────────────────────────── */}
        <View style={s.card}>
          {/* Chips row */}
          <View style={s.chipsRow}>
            <View style={[s.chip, { backgroundColor: C.tertiaryFixed }]}>
              <Text style={[s.chipIcon, { color: C.tertiary }]}>{categoryIcon}</Text>
              <Text style={[s.chipText, { color: C.onTertiaryFixed }]}>{categoryLabel}</Text>
            </View>

            <View style={[s.chip, { backgroundColor: template.importance === 'core' ? C.primaryFixed : C.surfaceContainerHighest }]}>
              <Text style={[s.chipText, { color: template.importance === 'core' ? C.primary : C.onSurfaceVariant }]}>
                {template.importance === 'core' ? 'Core' : 'Additional'}
              </Text>
            </View>

            {template.photo_proof_required && (
              <View style={[s.chip, { backgroundColor: '#fff3e0' }]}>
                <Text style={[s.chipIcon, { color: '#e6821e' }]}>photo_camera</Text>
                <Text style={[s.chipText, { color: '#e6821e' }]}>Photo required</Text>
              </View>
            )}
          </View>

          {/* Name */}
          <Text style={s.templateName}>{template.name}</Text>

          {/* Description */}
          {!!template.details && (
            <Text style={s.templateDetails}>{template.details}</Text>
          )}
        </View>

        {/* ── Section 2: Schedule / Effort ─────────────────── */}
        <View style={[s.card, { padding: 0, overflow: 'hidden' }]}>
          <View style={s.statRow}>
            {/* Schedule */}
            <View style={s.statTile}>
              <Text style={s.statIcon}>schedule</Text>
              <Text style={s.statValue}>{recurrenceLabel(template)}</Text>
              <Text style={s.statLabel}>SCHEDULE</Text>
            </View>

            <View style={s.statDivider} />

            {/* Duration */}
            <View style={s.statTile}>
              <Text style={s.statIcon}>timer</Text>
              <Text style={s.statValue}>{template.estimated_mins ?? '—'} min</Text>
              <Text style={s.statLabel}>DURATION</Text>
            </View>

            <View style={s.statDivider} />

            {/* Difficulty */}
            <View style={s.statTile}>
              <View style={s.dotsRow}>
                {[1, 2, 3, 4, 5].map(i => (
                  <View
                    key={i}
                    style={[s.dot, { backgroundColor: i <= (template.difficulty ?? 1) ? C.primary : C.surfaceContainerHighest }]}
                  />
                ))}
              </View>
              <Text style={s.statValue}>{difficultyLabel(template.difficulty ?? 1)}</Text>
              <Text style={s.statLabel}>DIFFICULTY</Text>
            </View>
          </View>
        </View>

        {/* ── Section 3: My Preference ──────────────────────── */}
        <View style={s.card}>
          <Text style={s.sectionTitle}>My Preference</Text>
          <Text style={s.sectionSub}>Affects how often you're assigned this task</Text>

          <View style={s.prefSegment}>
            {/* Prefer */}
            <TouchableOpacity
              style={[s.prefBtn, preference === 'prefer' && { backgroundColor: C.secondary }]}
              onPress={() => handleSetPreference('prefer')}
              disabled={prefSaving}
              activeOpacity={0.8}
            >
              <Text style={[s.prefBtnText, preference === 'prefer' && { color: '#fff' }]}>
                Prefer
              </Text>
            </TouchableOpacity>

            {/* Neutral */}
            <TouchableOpacity
              style={[s.prefBtn, preference === 'neutral' && { backgroundColor: '#e6821e' }]}
              onPress={() => handleSetPreference('neutral')}
              disabled={prefSaving}
              activeOpacity={0.8}
            >
              {preference === 'neutral' && (
                <View style={[s.neutralDot, { backgroundColor: '#fff' }]} />
              )}
              <Text style={[s.prefBtnText, preference === 'neutral' && { color: '#fff' }]}>
                Neutral
              </Text>
            </TouchableOpacity>

            {/* Avoid */}
            <TouchableOpacity
              style={[s.prefBtn, preference === 'avoid' && { backgroundColor: C.error }]}
              onPress={() => handleSetPreference('avoid')}
              disabled={prefSaving}
              activeOpacity={0.8}
            >
              <Text style={[s.prefBtnText, preference === 'avoid' && { color: '#fff' }]}>
                Avoid
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* ── Section 4: Upcoming ───────────────────────────── */}
        <View>
          <Text style={s.looseSectionTitle}>Upcoming</Text>

          {occurrences.length === 0 ? (
            <View style={s.emptyState}>
              <Text style={s.emptyIcon}>event_busy</Text>
              <Text style={s.emptyText}>No upcoming occurrences</Text>
            </View>
          ) : (
            <View style={s.occurrenceList}>
              {occurrences.map((occ) => {
                const isMe = occ.assigned_to_id === String(authUser?.id);
                const statusColors = occurrenceStatusColor(occ.status);
                const initials = isMe
                  ? 'ME'
                  : (occ.assigned_to_username ?? '?').slice(0, 2).toUpperCase();

                return (
                  <View key={occ.id} style={s.occurrenceRow}>
                    <View style={s.occurrenceLeft}>
                      {/* Avatar */}
                      <View style={[s.avatar, isMe && { backgroundColor: `${C.primaryContainer}30` }]}>
                        <Text style={[s.avatarText, isMe && { color: C.primary }]}>{initials}</Text>
                      </View>
                      <View>
                        <Text style={s.occurrenceDate}>{formatDeadline(occ.deadline)}</Text>
                        <Text style={s.occurrenceName}>
                          {isMe ? 'You' : (occ.assigned_to_username ?? 'Unassigned')}
                        </Text>
                      </View>
                    </View>

                    <View style={[s.statusChip, { backgroundColor: statusColors.bg }]}>
                      <Text style={[s.statusChipText, { color: statusColors.text }]}>
                        {occurrenceStatusLabel(occ.status)}
                      </Text>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </View>

        {/* ── Section 5: History (collapsible) ─────────────── */}
        <View style={s.historySection}>
          <TouchableOpacity
            style={s.historyHeader}
            onPress={() => setHistoryExpanded(v => !v)}
            activeOpacity={0.7}
          >
            <Text style={[s.looseSectionTitle, { opacity: historyExpanded ? 1 : 0.5, marginBottom: 0 }]}>History</Text>
            <Text style={[s.headerIcon, { color: historyExpanded ? C.onSurface : 'rgba(27,28,26,0.35)', fontSize: 22 }]}>
              {historyExpanded ? 'expand_less' : 'expand_more'}
            </Text>
          </TouchableOpacity>

          {historyExpanded && (
            <View style={s.historyEmpty}>
              <Text style={s.emptyIcon}>history</Text>
              <Text style={s.emptyText}>No history available yet</Text>
            </View>
          )}
        </View>

      </ScrollView>

      {/* ── Bottom action bar ─────────────────────────────── */}
      <View style={[s.bottomBar, { paddingBottom: insets.bottom + 16 }]}>
        <TouchableOpacity onPress={handleToggleFavourite} disabled={prefSaving} activeOpacity={0.88}>
          <LinearGradient
            colors={favourite ? [C.secondary, C.secondaryLight] : [C.primary, C.primaryContainer]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={s.actionBtn}
          >
            <Text style={[s.actionBtnIcon, { fontVariant: ['small-caps'] as any }]}>
              {favourite ? 'star' : 'star'}
            </Text>
            <Text style={s.actionBtnText}>
              {favourite ? "Favourited" : "Mark as Favourite"}
            </Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },

  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  errorMsg: { fontFamily: 'PlusJakartaSans_500Medium', fontSize: 14, color: C.onSurfaceVariant, marginBottom: 16 },
  backFallback: { paddingHorizontal: 20, paddingVertical: 10, backgroundColor: C.surfaceContainer, borderRadius: 12 },
  backFallbackText: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 14, color: C.primary },

  // Blobs
  blob: { position: 'absolute', borderRadius: 999 },
  blobTopRight: { top: -40, right: -40, width: 180, height: 180, backgroundColor: C.primaryFixed, opacity: 0.28 },
  blobBottomLeft: { bottom: -60, left: -60, width: 220, height: 220, backgroundColor: '#caecbc', opacity: 0.18 },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    height: 60,
  },
  iconBtn: {
    width: 40, height: 40,
    borderRadius: 20,
    backgroundColor: C.surfaceContainer,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.primary,
  },
  headerTitle: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 18,
    color: C.onSurface,
  },

  // Scroll
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 20, paddingTop: 8, gap: 16 },

  // Card
  card: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#1b1c1a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },

  // Chips
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  chipIcon: { fontFamily: 'MaterialSymbols', fontSize: 13 },
  chipText: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 11, letterSpacing: 0.5 },

  // Identity
  templateName: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 26,
    color: '#1e1b18',
    letterSpacing: -0.5,
    marginBottom: 8,
  },
  templateDetails: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: '#837570',
    lineHeight: 20,
  },

  // Stat row
  statRow: {
    flexDirection: 'row',
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20,
    paddingVertical: 20,
  },
  statTile: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingHorizontal: 4,
  },
  statDivider: { width: 1, backgroundColor: `${C.outlineVariant}40`, marginVertical: 8 },
  statIcon: { fontFamily: 'MaterialSymbols', fontSize: 22, color: C.primary, marginBottom: 2 },
  statValue: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 13, color: C.onSurface, textAlign: 'center' },
  statLabel: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 1.2, textAlign: 'center' },

  dotsRow: { flexDirection: 'row', gap: 3, marginBottom: 2 },
  dot: { width: 8, height: 8, borderRadius: 4 },

  // Preference
  sectionTitle: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 15, color: C.onSurface, marginBottom: 2 },
  sectionSub: { fontFamily: 'PlusJakartaSans_500Medium', fontSize: 12, color: C.onSurfaceVariant, marginBottom: 14 },

  prefSegment: {
    flexDirection: 'row',
    backgroundColor: C.surfaceContainer,
    borderRadius: 14,
    padding: 4,
    gap: 4,
  },
  prefBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 4,
  },
  prefBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },
  neutralDot: { width: 7, height: 7, borderRadius: 3.5 },

  // Upcoming
  looseSectionTitle: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 20,
    color: C.onSurface,
    marginBottom: 10,
    letterSpacing: -0.3,
  },
  occurrenceList: { gap: 10 },
  occurrenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 14,
    padding: 14,
  },
  occurrenceLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: {
    width: 40, height: 40,
    borderRadius: 20,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 13, color: C.onSurfaceVariant },
  occurrenceDate: { fontFamily: 'PlusJakartaSans_700Bold', fontSize: 14, color: C.onSurface },
  occurrenceName: { fontFamily: 'PlusJakartaSans_500Medium', fontSize: 12, color: C.onSurfaceVariant, marginTop: 1 },

  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  statusChipText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 10,
    letterSpacing: 0.6,
  },

  // Empty state
  emptyState: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 14,
    padding: 28,
    alignItems: 'center',
    gap: 8,
  },
  emptyIcon: { fontFamily: 'MaterialSymbols', fontSize: 32, color: C.onSurfaceVariant, opacity: 0.4 },
  emptyText: { fontFamily: 'PlusJakartaSans_500Medium', fontSize: 13, color: C.onSurfaceVariant },

  // History
  historySection: { borderTopWidth: 1, borderTopColor: `${C.outlineVariant}30`, paddingTop: 16 },
  historyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 0,
  },
  historyEmpty: {
    marginTop: 12,
    padding: 20,
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 12,
    alignItems: 'center',
    gap: 6,
  },

  // Bottom bar
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 20,
    paddingTop: 12,
    backgroundColor: 'rgba(251,249,245,0.88)',
    borderTopWidth: 1,
    borderTopColor: `${C.outlineVariant}20`,
  },
  actionBtn: {
    height: 54,
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.25,
    shadowRadius: 14,
    elevation: 6,
  },
  actionBtnIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 22,
    color: '#fff',
  },
  actionBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 16,
    color: '#fff',
    letterSpacing: 0.2,
  },

  onSurface: { color: C.onSurface },
  onSurfaceVariant: { color: C.onSurfaceVariant },
});
