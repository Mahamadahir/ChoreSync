import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { notificationService } from '../../services/notificationService';
import { Palette as C } from '../../theme';

interface Prefs {
  deadline_reminders: boolean;
  task_assigned: boolean;
  task_swap: boolean;
  emergency_reassign: boolean;
  badge_earned: boolean;
  marketplace_activity: boolean;
  smart_suggestions: boolean;
  quiet_hours_enabled: boolean;
  quiet_start: string | null;
  quiet_end: string | null;
}

const DEFAULT_PREFS: Prefs = {
  deadline_reminders: true,
  task_assigned: true,
  task_swap: true,
  emergency_reassign: true,
  badge_earned: true,
  marketplace_activity: true,
  smart_suggestions: true,
  quiet_hours_enabled: false,
  quiet_start: null,
  quiet_end: null,
};

const PREF_LABELS: Record<keyof Omit<Prefs, 'quiet_start' | 'quiet_end'>, { label: string; icon: string }> = {
  deadline_reminders:  { label: 'Deadline reminders',    icon: 'alarm' },
  task_assigned:       { label: 'Task assigned to me',   icon: 'assignment_ind' },
  task_swap:           { label: 'Swap requests',         icon: 'swap_horiz' },
  emergency_reassign:  { label: 'Emergency reassignments', icon: 'emergency' },
  badge_earned:        { label: 'Badges & achievements', icon: 'military_tech' },
  marketplace_activity:{ label: 'Marketplace activity',  icon: 'storefront' },
  smart_suggestions:   { label: 'Smart suggestions',     icon: 'tips_and_updates' },
  quiet_hours_enabled: { label: 'Quiet hours',           icon: 'do_not_disturb' },
};

// ── Inline time picker ───────────────────────────────────────────────────────
function TimeInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (v: string) => void;
}) {
  // Parse HH and MM from "HH:MM" or null
  const parsed = value?.match(/^(\d{1,2}):(\d{2})$/);
  const [hh, setHh] = useState(parsed ? parsed[1].padStart(2, '0') : '00');
  const [mm, setMm] = useState(parsed ? parsed[2] : '00');
  const mmRef = useRef<TextInput>(null);

  // Sync parent state whenever hh/mm is valid
  function commit(h: string, m: string) {
    const hNum = Math.min(23, Math.max(0, parseInt(h, 10) || 0));
    const mNum = Math.min(59, Math.max(0, parseInt(m, 10) || 0));
    const str = `${String(hNum).padStart(2, '0')}:${String(mNum).padStart(2, '0')}`;
    onChange(str);
  }

  function nudge(part: 'h' | 'm', delta: number) {
    if (part === 'h') {
      const next = ((parseInt(hh, 10) || 0) + delta + 24) % 24;
      const s = String(next).padStart(2, '0');
      setHh(s);
      commit(s, mm);
    } else {
      const next = ((parseInt(mm, 10) || 0) + delta + 60) % 60;
      const s = String(next).padStart(2, '0');
      setMm(s);
      commit(hh, s);
    }
  }

  return (
    <View style={tpStyles.wrap}>
      <Text style={tpStyles.label}>{label}</Text>
      <View style={tpStyles.picker}>
        {/* Hours */}
        <View style={tpStyles.unit}>
          <TouchableOpacity onPress={() => nudge('h', 1)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
            <Text style={tpStyles.arrow}>expand_less</Text>
          </TouchableOpacity>
          <TextInput
            style={tpStyles.input}
            value={hh}
            keyboardType="number-pad"
            maxLength={2}
            selectTextOnFocus
            onChangeText={(t) => setHh(t.replace(/\D/g, '').slice(0, 2))}
            onBlur={() => {
              const s = String(Math.min(23, parseInt(hh, 10) || 0)).padStart(2, '0');
              setHh(s);
              commit(s, mm);
            }}
            onSubmitEditing={() => mmRef.current?.focus()}
          />
          <TouchableOpacity onPress={() => nudge('h', -1)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
            <Text style={tpStyles.arrow}>expand_more</Text>
          </TouchableOpacity>
        </View>

        <Text style={tpStyles.colon}>:</Text>

        {/* Minutes */}
        <View style={tpStyles.unit}>
          <TouchableOpacity onPress={() => nudge('m', 5)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
            <Text style={tpStyles.arrow}>expand_less</Text>
          </TouchableOpacity>
          <TextInput
            ref={mmRef}
            style={tpStyles.input}
            value={mm}
            keyboardType="number-pad"
            maxLength={2}
            selectTextOnFocus
            onChangeText={(t) => setMm(t.replace(/\D/g, '').slice(0, 2))}
            onBlur={() => {
              const s = String(Math.min(59, parseInt(mm, 10) || 0)).padStart(2, '0');
              setMm(s);
              commit(hh, s);
            }}
          />
          <TouchableOpacity onPress={() => nudge('m', -5)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
            <Text style={tpStyles.arrow}>expand_more</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const tpStyles = StyleSheet.create({
  wrap: { flex: 1 },
  label: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: C.onSurfaceVariant,
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  picker: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 4,
  },
  unit: { alignItems: 'center', gap: 2 },
  arrow: {
    fontFamily: 'MaterialSymbols',
    fontSize: 18,
    color: C.primary,
    lineHeight: 20,
  },
  input: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22,
    color: C.onSurface,
    textAlign: 'center',
    width: 38,
    paddingVertical: 2,
  },
  colon: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22,
    color: C.onSurface,
    marginHorizontal: 2,
    lineHeight: 30,
  },
});

// ────────────────────────────────────────────────────────────────────────────

export default function NotificationPreferencesScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();

  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await notificationService.getPrefs();
      setPrefs((prev) => ({ ...prev, ...res.data }));
    } catch {
      Alert.alert('Error', 'Could not load notification preferences.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggle(field: keyof Prefs, value: boolean) {
    const updated = { ...prefs, [field]: value };
    setPrefs(updated);
    setSaving(true);
    try {
      await notificationService.updatePrefs({ [field]: value });
    } catch {
      setPrefs(prefs);
      Alert.alert('Error', 'Could not save preference. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  async function saveTime(field: 'quiet_start' | 'quiet_end', value: string) {
    setPrefs((p) => ({ ...p, [field]: value }));
    setSaving(true);
    try {
      await notificationService.updatePrefs({ [field]: value });
    } catch {
      Alert.alert('Error', 'Could not save time. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  const boolFields = Object.keys(PREF_LABELS) as (keyof typeof PREF_LABELS)[];

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* Top bar */}
      <View style={styles.topBar}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          style={styles.backBtn}
        >
          <Text style={styles.msIcon}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={styles.topBarTitle}>Notification Preferences</Text>
        {saving ? (
          <ActivityIndicator size="small" color={C.primary} style={{ marginRight: 4 }} />
        ) : (
          <View style={{ width: 28 }} />
        )}
      </View>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator color={C.primary} size="large" />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 40 }]}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.sectionLabel}>ALERTS</Text>
          <View style={styles.card}>
            {boolFields.map((field, idx) => {
              const { label, icon } = PREF_LABELS[field];
              const isLast = idx === boolFields.length - 1;
              return (
                <View key={field}>
                  <View style={styles.row}>
                    <View style={styles.rowLeft}>
                      <View style={styles.iconWrap}>
                        <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>{icon}</Text>
                      </View>
                      <Text style={styles.rowLabel}>{label}</Text>
                    </View>
                    <Switch
                      value={Boolean(prefs[field])}
                      onValueChange={(val) => toggle(field, val)}
                      trackColor={{ false: C.surfaceContainerHigh, true: C.primaryContainer }}
                      thumbColor={prefs[field] ? C.primary : C.stone400}
                    />
                  </View>
                  {!isLast && <View style={styles.divider} />}
                </View>
              );
            })}
          </View>

          {prefs.quiet_hours_enabled && (
            <>
              <Text style={[styles.sectionLabel, { marginTop: 24 }]}>QUIET HOURS WINDOW</Text>
              <View style={[styles.card, { paddingVertical: 16 }]}>
                <Text style={styles.quietHint}>
                  Notifications will be suppressed between these times each day.
                </Text>
                <View style={styles.quietRow}>
                  <TimeInput
                    label="Start"
                    value={prefs.quiet_start}
                    onChange={(v) => saveTime('quiet_start', v)}
                  />
                  <View style={styles.quietArrow}>
                    <Text style={[styles.quietArrowIcon, { color: C.onSurfaceVariant }]}>arrow_forward</Text>
                  </View>
                  <TimeInput
                    label="End"
                    value={prefs.quiet_end}
                    onChange={(v) => saveTime('quiet_end', v)}
                  />
                </View>
              </View>
            </>
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  topBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    gap: 12,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  topBarTitle: {
    flex: 1,
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 18,
    color: C.onSurface,
    letterSpacing: -0.3,
  },
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
    color: C.onSurfaceVariant,
  },
  scroll: {
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  sectionLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 11,
    letterSpacing: 1.2,
    color: C.stone500,
    marginBottom: 8,
    marginLeft: 4,
  },
  card: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16,
    paddingHorizontal: 16,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
  },
  rowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: C.surfaceContainerLow,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 15,
    color: C.onSurface,
    flex: 1,
  },
  rowValue: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 14,
    color: C.stone500,
  },
  divider: {
    height: 1,
    backgroundColor: C.surfaceContainerLow,
    marginLeft: 48,
  },
  hintText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.stone500,
    paddingVertical: 12,
    lineHeight: 18,
  },
  quietHint: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.onSurfaceVariant,
    marginBottom: 16,
    lineHeight: 18,
  },
  quietRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
  },
  quietArrow: {
    paddingBottom: 14,
  },
  quietArrowIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
  },
});
