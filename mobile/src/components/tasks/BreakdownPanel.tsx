/**
 * BreakdownPanel — "Why was this assigned?" score visualisation.
 *
 * Shows a horizontal bar per candidate, scaled to their final pipeline score
 * (lower = better chance of being assigned). The winner bar is highlighted.
 * Only the current user's row expands to show per-component details.
 */
import React, { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
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
  candidates: Candidate[];
}

interface Props {
  breakdown: BreakdownData;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function prefLabel(mult: number): string {
  if (mult <= 0.85) return 'Prefer ×0.8';
  if (mult >= 1.15) return 'Avoid ×1.2';
  return 'Neutral ×1.0';
}

function affinityLabel(mult: number): string {
  if (mult <= 0.9) return 'High history ×0.88';
  if (mult >= 1.1) return 'Low history ×1.12';
  return 'No adjustment';
}

// ── Component ────────────────────────────────────────────────────────────────

export default function BreakdownPanel({ breakdown }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [fairnessExpanded, setFairnessExpanded] = useState(false);

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

  // Max score for bar scaling
  const maxScore = Math.max(...breakdown.candidates.map((c) => c.final_score), 1);

  return (
    <View style={styles.panel}>
      <Text style={styles.panelLabel}>ASSIGNMENT SCORES</Text>
      <Text style={styles.panelSub}>Lower score = higher priority for assignment</Text>

      {breakdown.candidates.map((c) => {
        const barPct = (c.final_score / maxScore) * 100;
        const isExpandable = c.is_me && !!c.components;

        return (
          <View key={c.user_id} style={styles.candidateRow}>
            {/* Avatar + name */}
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
                {c.is_winner && (
                  <Text style={styles.winnerChip}>ASSIGNED</Text>
                )}
              </View>
            </View>

            {/* Bar + score */}
            <View style={styles.barWrap}>
              <View style={styles.barTrack}>
                <View style={[
                  styles.barFill,
                  { width: `${barPct}%` as any },
                  c.is_winner && { backgroundColor: C.secondary },
                  c.is_me && !c.is_winner && { backgroundColor: C.primaryContainer },
                ]} />
              </View>
              <Text style={styles.scoreLabel}>{c.final_score}</Text>
            </View>

            {/* Expandable components (own row only) */}
            {isExpandable && (
              <TouchableOpacity
                onPress={() => setExpanded((v) => !v)}
                style={styles.expandBtn}
                activeOpacity={0.7}
              >
                <Text style={[styles.msIcon, { color: C.primary, fontSize: 14 }]}>
                  {expanded ? 'expand_less' : 'expand_more'}
                </Text>
                <Text style={styles.expandBtnText}>
                  {expanded ? 'Hide breakdown' : 'Show my breakdown'}
                </Text>
              </TouchableOpacity>
            )}

            {isExpandable && expanded && c.components && (
              <View style={styles.componentsCard}>
                {/* Fairness score — expandable sub-breakdown */}
                <TouchableOpacity
                  onPress={() => setFairnessExpanded((v) => !v)}
                  activeOpacity={0.7}
                  style={styles.fairnessHeader}
                >
                  <View style={styles.compLeft}>
                    <Text style={styles.compLabel}>Fairness score</Text>
                    <Text style={styles.compSub}>Blends task count (40%), time burden (35%), points (25%)</Text>
                  </View>
                  <View style={styles.fairnessRight}>
                    <Text style={styles.compValue}>{c.components.stage1_score}</Text>
                    <Text style={[styles.msIcon, { color: C.primary, fontSize: 14 }]}>
                      {fairnessExpanded ? 'expand_less' : 'expand_more'}
                    </Text>
                  </View>
                </TouchableOpacity>
                {fairnessExpanded && (
                  <View style={styles.fairnessSub}>
                    <SubComponentRow label="Task count" value={c.components.tasks_score} weight="40%" />
                    <SubComponentRow label="Time burden" value={c.components.time_score} weight="35%" />
                    <SubComponentRow label="Points" value={c.components.points_score} weight="25%" />
                  </View>
                )}
                <ComponentRow
                  label="Preference"
                  value={prefLabel(c.components.pref_multiplier)}
                  sub="Based on your stated prefer / neutral / avoid"
                />
                <ComponentRow
                  label="History affinity"
                  value={affinityLabel(c.components.affinity_multiplier)}
                  sub="Completion rate for this recurring task (≥3 assignments)"
                />
                <ComponentRow
                  label="Calendar penalty"
                  value={`+${c.components.calendar_penalty}`}
                  sub="Calendar conflicts in the task window (max +50)"
                />
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}

function ComponentRow({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <View style={styles.compRow}>
      <View style={styles.compLeft}>
        <Text style={styles.compLabel}>{label}</Text>
        <Text style={styles.compSub}>{sub}</Text>
      </View>
      <Text style={styles.compValue}>{value}</Text>
    </View>
  );
}

function SubComponentRow({ label, value, weight }: { label: string; value: number; weight: string }) {
  const barPct = value;  // already 0–100
  return (
    <View style={styles.subCompRow}>
      <View style={styles.subCompMeta}>
        <Text style={styles.subCompLabel}>{label}</Text>
        <Text style={styles.subCompWeight}>{weight}</Text>
      </View>
      <View style={styles.subCompBarWrap}>
        <View style={styles.subCompBarTrack}>
          <View style={[styles.subCompBarFill, { width: `${barPct}%` as any }]} />
        </View>
        <Text style={styles.subCompScore}>{value}</Text>
      </View>
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

  expandBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
    alignSelf: 'flex-start',
  },
  expandBtnText: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 11,
    color: C.primary,
  },

  componentsCard: {
    marginTop: 8,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: `${C.primary}22`,
    padding: 12,
    gap: 10,
  },
  fairnessHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  fairnessRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flexShrink: 0,
  },
  fairnessSub: {
    marginTop: 2,
    marginBottom: 2,
    paddingLeft: 8,
    gap: 6,
    borderLeftWidth: 2,
    borderLeftColor: `${C.primary}33`,
  },
  subCompRow: {
    gap: 3,
  },
  subCompMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  subCompLabel: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: C.onSurface,
  },
  subCompWeight: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 10,
    color: C.onSurfaceVariant,
  },
  subCompBarWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  subCompBarTrack: {
    flex: 1,
    height: 4,
    backgroundColor: C.surfaceContainerHigh,
    borderRadius: 2,
    overflow: 'hidden',
  },
  subCompBarFill: {
    height: '100%',
    borderRadius: 2,
    backgroundColor: C.primary,
    opacity: 0.5,
  },
  subCompScore: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    color: C.primary,
    width: 24,
    textAlign: 'right',
  },
  compRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  compLeft: {
    flex: 1,
  },
  compLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: C.onSurface,
  },
  compSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 10,
    color: C.onSurfaceVariant,
    marginTop: 1,
  },
  compValue: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 12,
    color: C.primary,
    flexShrink: 0,
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
