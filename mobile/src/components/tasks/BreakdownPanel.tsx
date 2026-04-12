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
    pref_multiplier: number;   // e.g. 0.8, 1.0, 1.2
    affinity_multiplier: number;
    calendar_penalty: number;  // ×100
  };
}

interface BreakdownData {
  breakdown_available: boolean;
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
                <ComponentRow
                  label="Fairness score"
                  value={`${c.components.stage1_score}`}
                  sub="Blends task count (40%), difficulty-weighted time (35%), points (25%)"
                />
                <ComponentRow
                  label="Preference"
                  value={prefLabel(c.components.pref_multiplier)}
                  sub="Based on your stated prefer / neutral / avoid"
                />
                <ComponentRow
                  label="History affinity"
                  value={affinityLabel(c.components.affinity_multiplier)}
                  sub="Completion rate for this task template (≥3 assignments)"
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
});
