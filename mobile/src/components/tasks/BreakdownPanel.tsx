/**
 * BreakdownPanel — "Why was this assigned?" score visualisation.
 *
 * Shows a horizontal bar per candidate, scaled to their final pipeline score
 * (lower = better chance of being assigned). The winner bar is highlighted.
 * Only the current user's row expands to show per-component details.
 */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Palette as C } from '../../theme';

// ── Types ────────────────────────────────────────────────────────────────────

interface Candidate {
  user_id: string;
  username: string;
  is_winner: boolean;
  final_score: number;  // already ×100 integer
  is_me: boolean;
  components?: {
    stage1_score: number;      // ×100
    tasks_score: number;       // ×100 normalised task count component
    time_score: number;        // ×100 normalised time burden component
    points_score: number;      // ×100 normalised points component
    pref_multiplier: number;   // e.g. 0.8, 1.0, 1.2
    affinity_multiplier: number;
    calendar_penalty: number;  // ×100
  };
}

interface BreakdownData {
  breakdown_available: boolean;
  assigned_via?: 'emergency_cover';
  covered_by?: string | null;
  original_assignee?: string | null;
  template_name: string;
  assigned_at?: string;
  winner_id?: string;
  tiebreaker_used?: boolean;
  tiebreaker_reason?: 'no_prior_assignments' | 'least_recently_assigned' | 'joined_most_recently' | null;
  candidates: Candidate[];
}

interface Props {
  breakdown: BreakdownData;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function buildReasons(me: Candidate, others: Candidate[], breakdown: BreakdownData): string[] {
  const comp = me.components!;
  const reasons: string[] = [];

  // Tiebreaker — scores were equal, explain what broke the tie
  if (breakdown.tiebreaker_used && me.is_winner) {
    if (breakdown.tiebreaker_reason === 'no_prior_assignments')
      reasons.push("All members had equal workloads — you were selected because you haven't been assigned a task yet");
    else if (breakdown.tiebreaker_reason === 'least_recently_assigned')
      reasons.push("All members had equal workloads — you were selected because you haven't had a task assigned in the longest time");
    else
      reasons.push("All members had equal workloads — you were selected as the most recently joined member");
    return reasons;
  }

  const avgOtherTasks = others.length
    ? others.reduce((s, c) => s + (c.components?.tasks_score ?? comp.tasks_score), 0) / others.length
    : comp.tasks_score;
  const avgOtherTime = others.length
    ? others.reduce((s, c) => s + (c.components?.time_score ?? comp.time_score), 0) / others.length
    : comp.time_score;

  if (comp.tasks_score < avgOtherTasks * 0.9)
    reasons.push("You've completed fewer tasks than others in the group recently");
  else if (comp.tasks_score <= avgOtherTasks * 1.1)
    reasons.push("Your workload is similar to the rest of the group");

  if (comp.time_score < avgOtherTime * 0.85)
    reasons.push("You've spent less time on tasks than others recently");

  if (comp.pref_multiplier <= 0.85)
    reasons.push("You marked this type of task as preferred");
  else if (comp.pref_multiplier >= 1.15)
    reasons.push("Note: you marked this type of task as something to avoid");

  if (comp.affinity_multiplier <= 0.9)
    reasons.push("You have a strong completion history with this task");
  else if (comp.affinity_multiplier >= 1.1)
    reasons.push("Others tend to complete this task more consistently than you");

  if (comp.calendar_penalty === 0)
    reasons.push("Your calendar is free during the task window");
  else if (comp.calendar_penalty >= 25)
    reasons.push("You have some calendar conflicts during the task window — still the best available option");

  return reasons;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function BreakdownPanel({ breakdown }: Props) {
  if (breakdown.assigned_via === 'emergency_cover') {
    return (
      <View style={styles.emergencyCard}>
        <View style={styles.emergencyHeader}>
          <Text style={[styles.msIcon, { color: C.error, fontSize: 20 }]}>crisis_alert</Text>
          <Text style={styles.emergencyTitle}>Emergency Cover</Text>
        </View>
        <Text style={styles.emergencyBody}>
          {breakdown.original_assignee
            ? `${breakdown.original_assignee} requested emergency cover and `
            : 'The original assignee requested emergency cover. '}
          {breakdown.covered_by
            ? `${breakdown.covered_by} volunteered to take over.`
            : 'a group member volunteered to take over.'}
        </Text>
        <Text style={styles.emergencyNote}>
          This task was not assigned by the fairness pipeline — no score breakdown is available.
        </Text>
      </View>
    );
  }

  if (!breakdown.breakdown_available || breakdown.candidates.length === 0) {
    return (
      <View style={styles.unavailable}>
        <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 16 }]}>info</Text>
        <Text style={styles.unavailableText}>
          Score history unavailable for assignments made before this feature was added.
        </Text>
      </View>
    );
  }

  const maxScore = Math.max(...breakdown.candidates.map((c) => c.final_score), 1);
  const me = breakdown.candidates.find((c) => c.is_me);
  const others = breakdown.candidates.filter((c) => !c.is_me);
  const reasons = me?.components ? buildReasons(me, others, breakdown) : [];

  return (
    <View style={styles.panel}>
      <Text style={styles.panelLabel}>RELATIVE WORKLOAD</Text>

      {breakdown.candidates.map((c) => {
        const barPct = (c.final_score / maxScore) * 100;
        return (
          <View key={c.user_id} style={styles.candidateRow}>
            <View style={styles.candidateMeta}>
              <View style={[
                styles.avatar,
                c.is_winner && { backgroundColor: C.secondary },
                c.is_me && !c.is_winner && { backgroundColor: C.primaryContainer },
              ]}>
                <Text style={[
                  styles.avatarText,
                  c.is_winner && { color: C.white },
                  c.is_me && !c.is_winner && { color: C.primary },
                ]}>
                  {c.username[0].toUpperCase()}
                </Text>
              </View>
              <View style={styles.nameWrap}>
                <Text style={styles.candidateName} numberOfLines={1}>
                  {c.username}{c.is_me ? ' (you)' : ''}
                </Text>
                {c.is_winner && <Text style={styles.winnerChip}>ASSIGNED</Text>}
              </View>
            </View>
            <View style={styles.barWrap}>
              <View style={styles.barTrack}>
                <View style={[
                  styles.barFill,
                  { width: `${barPct}%` as any },
                  c.is_winner && { backgroundColor: C.secondary },
                  c.is_me && !c.is_winner && { backgroundColor: C.primaryContainer },
                ]} />
              </View>
            </View>
          </View>
        );
      })}

      {reasons.length > 0 && (
        <View style={styles.reasonsCard}>
          <Text style={styles.reasonsTitle}>WHY YOU?</Text>
          {reasons.map((r, i) => (
            <View key={i} style={styles.reasonRow}>
              <Text style={[styles.msIcon, { color: C.secondary, fontSize: 14 }]}>check_circle</Text>
              <Text style={styles.reasonText}>{r}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  panel: {
    marginTop: 8,
    marginBottom: 4,
  },
  panelLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 1,
    color: C.onSurfaceVariant,
    marginBottom: 2,
  },
  panelSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
    marginBottom: 12,
  },

  candidateRow: {
    marginBottom: 10,
  },
  candidateMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  avatar: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 11,
    color: C.onSurfaceVariant,
  },
  nameWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  candidateName: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: C.onSurface,
  },
  winnerChip: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 9,
    letterSpacing: 0.8,
    color: C.white,
    backgroundColor: C.secondary,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },

  barWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  barTrack: {
    flex: 1,
    height: 8,
    backgroundColor: C.surfaceContainerHigh,
    borderRadius: 4,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 4,
    backgroundColor: C.surfaceContainerHighest,
  },
  scoreLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12,
    color: C.onSurfaceVariant,
    width: 28,
    textAlign: 'right',
  },

  reasonsCard: {
    marginTop: 12,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 10,
    borderLeftWidth: 3,
    borderLeftColor: C.secondary,
    padding: 12,
    gap: 8,
  },
  reasonsTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 0.8,
    color: C.onSurfaceVariant,
    marginBottom: 2,
  },
  reasonRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  reasonText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurface,
    lineHeight: 18,
    flex: 1,
  },

  msIcon: {
    fontFamily: 'MaterialSymbols',
  },

  unavailable: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
    padding: 12,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 10,
  },
  unavailableText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurfaceVariant,
    flex: 1,
  },

  emergencyCard: {
    padding: 14,
    backgroundColor: `${C.error}12`,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: `${C.error}44`,
    gap: 6,
  },
  emergencyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  emergencyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13,
    color: C.error,
  },
  emergencyBody: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurface,
    lineHeight: 18,
  },
  emergencyNote: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurfaceVariant,
    marginTop: 2,
  },
});
