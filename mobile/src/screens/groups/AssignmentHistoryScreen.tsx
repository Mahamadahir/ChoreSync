import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { GroupsStackParamList } from '../../navigation/types';
import { api } from '../../services/api';
import { Palette as C } from '../../theme';
import BreakdownPanel from '../../components/tasks/BreakdownPanel';

type Nav = NativeStackNavigationProp<GroupsStackParamList, 'AssignmentHistory'>;
type Route = RouteProp<GroupsStackParamList, 'AssignmentHistory'>;

type HistoryEntry = {
  occurrence_id: number;
  template_id: number;
  template_name: string;
  assigned_at?: string;
  deadline?: string | null;
  occurrence_status: string;
  completed_at?: string | null;
  breakdown_available: boolean;
  assigned_via?: string;
  covered_by?: string | null;
  original_assignee?: string | null;
  winner_id?: string;
  tiebreaker_used?: boolean;
  tiebreaker_reason?: string | null;
  candidates: any[];
};

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function statusColors(status: string) {
  if (status === 'completed') return { bg: C.secondaryContainer, text: C.secondary };
  if (status === 'overdue') return { bg: C.errorContainer, text: C.error };
  return { bg: C.tertiaryFixed, text: C.onTertiaryFixed };
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function assignedViaLabel(entry: HistoryEntry): string {
  if (entry.assigned_via === 'emergency_cover') return 'Emergency cover';
  if (entry.assigned_via === 'streak_suggestion') return 'Streak suggestion';
  if (entry.breakdown_available) return 'Pipeline assigned';
  return 'Assigned';
}

export default function AssignmentHistoryScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { groupId, groupName } = route.params;
  const insets = useSafeAreaInsets();

  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(false);
    try {
      const res = await api.get<HistoryEntry[]>(`/api/groups/${groupId}/my-assignment-history/`);
      setHistory(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError(true);
    }
  }, [groupId]);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  if (loading) {
    return (
      <SafeAreaView style={s.safe} edges={['top']}>
        <View style={s.header}>
          <TouchableOpacity style={s.iconBtn} onPress={() => navigation.goBack()} activeOpacity={0.8}>
            <Text style={s.msIcon}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={s.headerTitle}>Assignment History</Text>
          <View style={s.iconBtn} />
        </View>
        <View style={s.centered}>
          <ActivityIndicator color={C.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.iconBtn} onPress={() => navigation.goBack()} activeOpacity={0.8}>
          <Text style={s.msIcon}>arrow_back</Text>
        </TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={s.headerTitle}>Assignment History</Text>
          {!!groupName && <Text style={s.headerSub}>{groupName}</Text>}
        </View>
        <View style={s.iconBtn} />
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.scrollContent, { paddingBottom: 40 + insets.bottom }]}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
      >
        {error ? (
          <TouchableOpacity onPress={load} activeOpacity={0.7} style={s.errorState}>
            <Text style={[s.msIcon, { color: C.onSurfaceVariant, fontSize: 32, marginBottom: 8 }]}>sync_problem</Text>
            <Text style={s.errorText}>Couldn't load history</Text>
            <Text style={s.retryText}>Tap to retry</Text>
          </TouchableOpacity>
        ) : history.length === 0 ? (
          <View style={s.emptyState}>
            <Text style={[s.msIcon, { fontSize: 40, color: C.onSurfaceVariant, opacity: 0.35, marginBottom: 10 }]}>assignment_turned_in</Text>
            <Text style={s.emptyTitle}>No assignments yet</Text>
            <Text style={s.emptyBody}>Your assignment history will appear here once tasks start being assigned to you.</Text>
          </View>
        ) : (
          <>
            <Text style={s.countLabel}>{history.length} assignment{history.length !== 1 ? 's' : ''}</Text>
            {history.map((entry) => {
              const expanded = expandedId === entry.occurrence_id;
              const sc = statusColors(entry.occurrence_status);
              return (
                <View key={entry.occurrence_id} style={s.card}>
                  {/* Card header — always visible */}
                  <TouchableOpacity
                    onPress={() => setExpandedId(expanded ? null : entry.occurrence_id)}
                    activeOpacity={0.75}
                    style={s.cardHeader}
                  >
                    <View style={s.cardLeft}>
                      <Text style={s.templateName} numberOfLines={1}>{entry.template_name}</Text>
                      <View style={s.metaRow}>
                        <Text style={s.metaText}>{assignedViaLabel(entry)}</Text>
                        <Text style={s.metaDot}>·</Text>
                        <Text style={s.metaText}>{formatDate(entry.assigned_at)}</Text>
                      </View>
                    </View>
                    <View style={s.cardRight}>
                      <View style={[s.statusChip, { backgroundColor: sc.bg }]}>
                        <Text style={[s.statusChipText, { color: sc.text }]}>
                          {statusLabel(entry.occurrence_status)}
                        </Text>
                      </View>
                      <Text style={[s.msIcon, { color: C.onSurfaceVariant, fontSize: 18, marginTop: 4 }]}>
                        {expanded ? 'expand_less' : 'expand_more'}
                      </Text>
                    </View>
                  </TouchableOpacity>

                  {/* Deadline / completed row */}
                  <View style={s.datesRow}>
                    <View style={s.dateChip}>
                      <Text style={[s.msIcon, { fontSize: 13, color: C.onSurfaceVariant }]}>event</Text>
                      <Text style={s.dateLabel}>Due {formatDate(entry.deadline)}</Text>
                    </View>
                    {entry.completed_at && (
                      <View style={s.dateChip}>
                        <Text style={[s.msIcon, { fontSize: 13, color: C.secondary }]}>check_circle</Text>
                        <Text style={[s.dateLabel, { color: C.secondary }]}>Done {formatDate(entry.completed_at)}</Text>
                      </View>
                    )}
                  </View>

                  {/* Breakdown panel — shown when expanded */}
                  {expanded && (
                    <View style={s.breakdownWrap}>
                      <View style={s.divider} />
                      <BreakdownPanel breakdown={entry as any} />
                    </View>
                  )}
                </View>
              );
            })}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },

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
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 20, color: C.primary },
  headerTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 17,
    color: C.onSurface,
  },
  headerSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
    marginTop: 1,
  },

  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingTop: 12, gap: 12 },

  countLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 11,
    letterSpacing: 0.8,
    color: C.onSurfaceVariant,
    textTransform: 'uppercase',
    marginBottom: 4,
  },

  card: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#1b1c1a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    padding: 16,
    paddingBottom: 8,
  },
  cardLeft: { flex: 1, marginRight: 12 },
  templateName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15,
    color: C.onSurface,
    marginBottom: 4,
  },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metaText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurfaceVariant,
  },
  metaDot: { color: C.onSurfaceVariant, fontSize: 12 },

  cardRight: { alignItems: 'flex-end', gap: 2 },
  statusChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  statusChipText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 0.6,
  },

  datesRow: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
    paddingBottom: 14,
    flexWrap: 'wrap',
  },
  dateChip: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  dateLabel: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
  },

  divider: {
    height: 1,
    backgroundColor: `${C.outlineVariant}30`,
    marginHorizontal: 16,
    marginBottom: 14,
  },
  breakdownWrap: { paddingHorizontal: 16, paddingBottom: 16 },

  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorState: { alignItems: 'center', paddingTop: 60 },
  errorText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15,
    color: C.onSurface,
    marginBottom: 4,
  },
  retryText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },

  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 32 },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 17,
    color: C.onSurface,
    marginBottom: 8,
  },
  emptyBody: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 20,
  },
});
