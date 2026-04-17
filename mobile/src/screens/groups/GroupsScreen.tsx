import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Dimensions,
  KeyboardAvoidingView,
  Modal,
  Platform,
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
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { groupService } from '../../services/groupService';
import type { Group } from '../../types/group';
import type { GroupsStackParamList } from '../../navigation/types';
import { Palette as C } from '../../theme';
import { useNotificationStore } from '../../stores/notificationStore';
import AppHeader from '../../components/common/AppHeader';

type Nav = NativeStackNavigationProp<GroupsStackParamList, 'Groups'>;

const { width: SCREEN_W } = Dimensions.get('window');
const CARD_GAP = 12;
const H_PAD = 24;
const HALF_W = (SCREEN_W - H_PAD * 2 - CARD_GAP) / 2;


// Cycle through housing icons for each group card
const GROUP_ICONS = ['home', 'apartment', 'cottage', 'cabin', 'house', 'domain', 'villa', 'holiday_village'];
const ICON_PALETTES = [
  { bg: C.secondaryContainer, fg: C.onSecondaryContainer },
  { bg: C.tertiaryFixed,      fg: C.onTertiaryFixed       },
  { bg: C.primaryFixed,       fg: C.primary               },
  { bg: C.surfaceContainerHighest, fg: C.onSurfaceVariant },
];

function getGroupIcon(idx: number) { return GROUP_ICONS[idx % GROUP_ICONS.length]; }
function getIconPalette(idx: number) { return ICON_PALETTES[idx % ICON_PALETTES.length]; }

// Initials from group name
function initials(name: string) {
  return name.split(' ').slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
}

// ── Small group card (half-width) ─────────────────────────────
function GroupCard({
  group,
  idx,
  onPress,
  notifBadge = 0,
}: {
  group: Group;
  idx: number;
  onPress: () => void;
  notifBadge?: number;
}) {
  const icon = getGroupIcon(idx);
  const palette = getIconPalette(idx);
  const isEven = idx % 2 === 0;

  return (
    <TouchableOpacity
      activeOpacity={0.88}
      onPress={onPress}
      style={[styles.card, isEven ? styles.cardTinted : styles.cardElevated]}
    >
      {/* Decorative circle for even cards */}
      {isEven && <View style={styles.cardDecor} />}

      <View style={styles.cardInner}>
        {/* Icon + badge row */}
        <View style={styles.cardTop}>
          <View style={[styles.iconCircle, { backgroundColor: palette.bg }]}>
            <Text style={[styles.msIcon, { color: palette.fg, fontSize: 28 }]}>{icon}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <View style={styles.activeBadge}>
              <Text style={styles.activeBadgeText}>ACTIVE</Text>
            </View>
            {notifBadge > 0 && (
              <View style={styles.notifBadge}>
                <Text style={styles.notifBadgeText}>{notifBadge}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Name */}
        <Text style={styles.cardName} numberOfLines={2}>{group.name}</Text>

        {/* Stats row */}
        <View style={styles.cardStats}>
          <View style={styles.statCol}>
            <Text style={styles.statLabel}>MEMBERS</Text>
            <View style={styles.memberRow}>
              {/* Member count circle(s) */}
              {Array.from({ length: Math.min(group.member_count, 3) }).map((_, i) => (
                <View
                  key={i}
                  style={[
                    styles.memberCircle,
                    { marginLeft: i === 0 ? 0 : -8, backgroundColor: palette.bg, borderColor: isEven ? C.surfaceContainerLow : C.surfaceContainerLowest },
                  ]}
                >
                  <Text style={[styles.memberInitial, { color: palette.fg }]}>
                    {String.fromCharCode(65 + (idx + i) % 26)}
                  </Text>
                </View>
              ))}
              {group.member_count > 3 && (
                <View style={[styles.memberCircle, styles.memberOverflow, { marginLeft: -8, borderColor: isEven ? C.surfaceContainerLow : C.surfaceContainerLowest }]}>
                  <Text style={styles.memberOverflowText}>+{group.member_count - 3}</Text>
                </View>
              )}
            </View>
          </View>

          <View style={styles.statDivider} />

          <View style={styles.statCol}>
            <Text style={styles.statLabel}>OPEN TASKS</Text>
            <Text style={[styles.statCount, { color: isEven ? C.secondary : C.primary }]}>
              {group.open_task_count}
            </Text>
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── Wide group card (full-width) ──────────────────────────────
function GroupCardWide({
  group,
  idx,
  onPress,
  notifBadge = 0,
}: {
  group: Group;
  idx: number;
  onPress: () => void;
  notifBadge?: number;
}) {
  const icon = getGroupIcon(idx);
  const palette = getIconPalette(idx);

  return (
    <TouchableOpacity activeOpacity={0.88} onPress={onPress} style={styles.cardWide}>
      <View style={styles.cardWideLeft}>
        <View style={[styles.iconCircle, { backgroundColor: palette.bg, marginBottom: 16 }]}>
          <Text style={[styles.msIcon, { color: palette.fg, fontSize: 28 }]}>{icon}</Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <Text style={[styles.cardWideName, { marginBottom: 0 }]} numberOfLines={1}>{group.name}</Text>
          {notifBadge > 0 && (
            <View style={styles.notifBadge}>
              <Text style={styles.notifBadgeText}>{notifBadge}</Text>
            </View>
          )}
        </View>
        <Text style={styles.cardWideRole} numberOfLines={1}>
          {group.my_role === 'moderator' ? 'You are the moderator' : 'You are a member'}
        </Text>
      </View>

      <View style={styles.cardWideStats}>
        <View style={styles.wideStatItem}>
          <Text style={[styles.wideStatNum, { color: C.primary }]}>{group.member_count}</Text>
          <Text style={styles.wideStatLabel}>MEMBERS</Text>
        </View>
        <View style={styles.wideStatDivider} />
        <View style={styles.wideStatItem}>
          <Text style={[styles.wideStatNum, { color: C.tertiary }]}>{group.open_task_count}</Text>
          <Text style={styles.wideStatLabel}>OPEN TASKS</Text>
        </View>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={onPress}
          style={styles.wideArrowBtn}
        >
          <Text style={[styles.msIcon, { color: C.white, fontSize: 22 }]}>arrow_forward</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

// ── Group presets ──────────────────────────────────────────────
type PresetId = 'flat_share' | 'family' | 'work_team';

const PRESETS: {
  id: PresetId; label: string; icon: string; description: string;
  reassignment_rule: string;
  group_type: string;
}[] = [
  {
    id: 'flat_share', label: 'Flat Share', icon: 'apartment',
    description: 'Equal rotation — everyone has full access.',
    reassignment_rule: 'on_create',
    group_type: 'flatshare',
  },
  {
    id: 'family', label: 'Family', icon: 'family_restroom',
    description: 'Adults are moderators who manage tasks. Children are members.',
    reassignment_rule: 'on_create',
    group_type: 'family',
  },
  {
    id: 'work_team', label: 'Work Team', icon: 'corporate_fare',
    description: 'Equal rotation. Team Leads manage tasks; Members complete them.',
    reassignment_rule: 'on_create',
    group_type: 'work_team',
  },
];

// ── Create Group Modal ─────────────────────────────────────────
function CreateGroupModal({
  visible,
  onClose,
  onCreate,
}: {
  visible: boolean;
  onClose: () => void;
  onCreate: (payload: {
    name: string;
    reassignment_rule: string;
    group_type: string;
  }) => Promise<void>;
}) {
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState('');
  const [preset, setPreset] = useState<PresetId>('flat_share');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    if (visible) {
      setStep(1);
      setName('');
      setPreset('flat_share');
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [visible]);

  function handleNext() {
    if (!name.trim()) return;
    setStep(2);
  }

  async function handleCreate() {
    const chosen = PRESETS.find((p) => p.id === preset)!;
    setLoading(true);
    try {
      await onCreate({
        name: name.trim(),
        reassignment_rule: chosen.reassignment_rule,
        group_type: chosen.group_type,
      });
      onClose();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not create group.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={styles.modalBackdrop} activeOpacity={1} onPress={onClose} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.modalWrapper}
      >
        <View style={[styles.modalSheet, { paddingBottom: insets.bottom + 16 }]}>
          <View style={styles.modalHandle} />

          {step === 1 ? (
            <>
              <Text style={styles.modalTitle}>New Group</Text>
              <Text style={styles.modalSub}>Give your household a name.</Text>

              <TextInput
                ref={inputRef}
                style={styles.modalInput}
                value={name}
                onChangeText={setName}
                placeholder="e.g. The Studio Apt."
                placeholderTextColor={`${C.onSurfaceVariant}80`}
                returnKeyType="next"
                onSubmitEditing={handleNext}
                autoCapitalize="words"
              />

              <TouchableOpacity
                activeOpacity={0.85}
                onPress={handleNext}
                disabled={!name.trim()}
                style={[styles.modalBtn, !name.trim() && { opacity: 0.45 }]}
              >
                <LinearGradient
                  colors={[C.primary, C.primaryContainer]}
                  start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                  style={styles.modalBtnGradient}
                >
                  <Text style={styles.modalBtnText}>Next</Text>
                </LinearGradient>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.modalTitle}>Choose a preset</Text>
              <Text style={styles.modalSub}>You can adjust these in group settings later.</Text>

              <View style={{ gap: 10, marginBottom: 16 }}>
                {PRESETS.map((p) => (
                  <TouchableOpacity
                    key={p.id}
                    activeOpacity={0.8}
                    onPress={() => setPreset(p.id)}
                    style={[
                      styles.presetCard,
                      preset === p.id && styles.presetCardSelected,
                    ]}
                  >
                    <Text style={[
                      styles.msIcon,
                      { fontSize: 22, color: preset === p.id ? C.primary : C.onSurfaceVariant },
                    ]}>{p.icon}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[
                        styles.presetLabel,
                        preset === p.id && { color: C.primary },
                      ]}>{p.label}</Text>
                      <Text style={styles.presetDesc}>{p.description}</Text>
                    </View>
                    {preset === p.id && (
                      <Text style={[styles.msIcon, { fontSize: 18, color: C.primary }]}>check_circle</Text>
                    )}
                  </TouchableOpacity>
                ))}
              </View>

              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TouchableOpacity
                  activeOpacity={0.7}
                  onPress={() => setStep(1)}
                  style={{ flex: 0.4, borderRadius: 999, overflow: 'hidden', backgroundColor: C.surfaceContainerHigh, paddingVertical: 16, alignItems: 'center', justifyContent: 'center' }}
                >
                  <Text style={[styles.modalBtnText, { color: C.onSurfaceVariant }]}>Back</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  activeOpacity={0.85}
                  onPress={handleCreate}
                  disabled={loading}
                  style={[styles.modalBtn, { flex: 1 }, loading && { opacity: 0.6 }]}
                >
                  <LinearGradient
                    colors={[C.primary, C.primaryContainer]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                    style={styles.modalBtnGradient}
                  >
                    {loading
                      ? <ActivityIndicator color={C.white} size="small" />
                      : <Text style={styles.modalBtnText}>Create Group</Text>
                    }
                  </LinearGradient>
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ── Join Group Modal ───────────────────────────────────────────
function JoinGroupModal({
  visible,
  onClose,
  onJoin,
}: {
  visible: boolean;
  onClose: () => void;
  onJoin: (code: string) => Promise<void>;
}) {
  const insets = useSafeAreaInsets();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    if (visible) {
      setCode('');
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [visible]);

  async function handleJoin() {
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    try {
      await onJoin(trimmed);
      onClose();
    } catch (e: any) {
      Alert.alert('Invalid Code', e?.response?.data?.detail ?? 'Could not find a group with that code.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <TouchableOpacity
        style={styles.modalBackdrop}
        activeOpacity={1}
        onPress={onClose}
      />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.modalWrapper}
      >
        <View style={[styles.modalSheet, { paddingBottom: insets.bottom + 16 }]}>
          <View style={styles.modalHandle} />

          {/* Icon */}
          <View style={styles.joinIconWrap}>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 32 }]}>vpn_key</Text>
          </View>

          <Text style={styles.modalTitle}>Join a Group</Text>
          <Text style={styles.modalSub}>Enter the invite code shared by your housemate.</Text>

          <TextInput
            ref={inputRef}
            style={[styles.modalInput, styles.joinCodeInput]}
            value={code}
            onChangeText={(t) => setCode(t.toUpperCase())}
            placeholder="e.g. AB12CD"
            placeholderTextColor={`${C.onSurfaceVariant}60`}
            returnKeyType="done"
            onSubmitEditing={handleJoin}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={12}
          />

          <TouchableOpacity
            activeOpacity={0.85}
            onPress={handleJoin}
            disabled={loading || !code.trim()}
            style={[styles.modalBtn, (!code.trim() || loading) && { opacity: 0.45 }]}
          >
            <LinearGradient
              colors={[C.secondary, C.onSecondaryContainer]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.modalBtnGradient}
            >
              {loading ? (
                <ActivityIndicator color={C.white} size="small" />
              ) : (
                <Text style={styles.modalBtnText}>Join Group</Text>
              )}
            </LinearGradient>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ── FAB action menu ────────────────────────────────────────────
function FabMenu({
  visible,
  onClose,
  onCreate,
  onJoin,
  bottom,
}: {
  visible: boolean;
  onClose: () => void;
  onCreate: () => void;
  onJoin: () => void;
  bottom: number;
}) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(anim, {
      toValue: visible ? 1 : 0,
      useNativeDriver: true,
      tension: 120,
      friction: 10,
    }).start();
  }, [visible]);

  if (!visible) return null;

  return (
    <>
      <TouchableOpacity style={StyleSheet.absoluteFillObject} activeOpacity={1} onPress={onClose} />
      <Animated.View
        style={[
          styles.fabMenu,
          { bottom: bottom + 64, opacity: anim, transform: [{ scale: anim }] },
        ]}
        pointerEvents="box-none"
      >
        {/* Join option */}
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.fabMenuItem}
          onPress={() => { onClose(); onJoin(); }}
        >
          <View style={[styles.fabMenuIcon, { backgroundColor: C.secondaryContainer }]}>
            <Text style={[styles.msIcon, { color: C.secondary, fontSize: 20 }]}>vpn_key</Text>
          </View>
          <Text style={styles.fabMenuLabel}>Join with Code</Text>
        </TouchableOpacity>

        {/* Create option */}
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.fabMenuItem}
          onPress={() => { onClose(); onCreate(); }}
        >
          <View style={[styles.fabMenuIcon, { backgroundColor: C.primaryFixed }]}>
            <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>add_home</Text>
          </View>
          <Text style={styles.fabMenuLabel}>Create Group</Text>
        </TouchableOpacity>
      </Animated.View>
    </>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function GroupsScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<Nav>();
  const groupBadge = useNotificationStore((s) => s.groupBadge);

  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [fabMenuOpen, setFabMenuOpen] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await groupService.list();
      setGroups(res.data.results ?? res.data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return groups;
    return groups.filter((g) =>
      g.name.toLowerCase().includes(search.toLowerCase()),
    );
  }, [groups, search]);

  async function handleCreate(payload: {
    name: string;
    reassignment_rule: string;
    group_type: string;
  }) {
    const res = await groupService.create(payload);
    const newGroup: Group = res.data;
    setGroups((prev) => [newGroup, ...prev]);
    navigation.navigate('GroupDetail', { groupId: String(newGroup.id) });
  }

  async function handleJoin(code: string) {
    const res = await groupService.joinByCode(code);
    const joined: Group = res.data;
    setGroups((prev) => {
      if (prev.some((g) => g.id === joined.id)) return prev;
      return [joined, ...prev];
    });
    navigation.navigate('GroupDetail', { groupId: String(joined.id) });
  }

  // Split into rows of 2; last item gets full-width if odd count
  const rows: Array<{ type: 'pair'; items: [Group, Group | null]; startIdx: number } | { type: 'wide'; item: Group; idx: number }> = [];
  let i = 0;
  while (i < filtered.length) {
    if (i === filtered.length - 1 && filtered.length % 2 !== 0) {
      rows.push({ type: 'wide', item: filtered[i], idx: i });
      i++;
    } else {
      rows.push({
        type: 'pair',
        items: [filtered[i], filtered[i + 1] ?? null],
        startIdx: i,
      });
      i += 2;
    }
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
        {/* ── Header + Search ──────────────────── */}
        <Text style={styles.pageTitle}>Your Groups</Text>

        <View style={styles.searchWrap}>
          <Text style={[styles.msIcon, styles.searchIcon]}>search</Text>
          <TextInput
            style={styles.searchInput}
            value={search}
            onChangeText={setSearch}
            placeholder="Find a home or apartment..."
            placeholderTextColor={`${C.onSurfaceVariant}80`}
            clearButtonMode="while-editing"
          />
        </View>

        {/* ── Content ──────────────────────────── */}
        {loading ? (
          <View style={styles.centered}>
            <ActivityIndicator color={C.primary} size="large" />
          </View>
        ) : filtered.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={[styles.msIcon, styles.emptyIcon]}>group_add</Text>
            <Text style={styles.emptyTitle}>
              {search ? 'No groups match your search.' : 'No groups yet.'}
            </Text>
            {!search && (
              <Text style={styles.emptySub}>
                Tap the + button to create your first household.
              </Text>
            )}
          </View>
        ) : (
          <View style={styles.grid}>
            {rows.map((row, rowIdx) => {
              if (row.type === 'wide') {
                return (
                  <GroupCardWide
                    key={row.item.id}
                    group={row.item}
                    idx={row.idx}
                    notifBadge={groupBadge(String(row.item.id))}
                    onPress={() => navigation.navigate('GroupDetail', { groupId: String(row.item.id) })}
                  />
                );
              }
              const [a, b] = row.items;
              return (
                <View key={rowIdx} style={styles.gridRow}>
                  <GroupCard
                    group={a}
                    idx={row.startIdx}
                    notifBadge={groupBadge(String(a.id))}
                    onPress={() => navigation.navigate('GroupDetail', { groupId: String(a.id) })}
                  />
                  {b ? (
                    <GroupCard
                      group={b}
                      idx={row.startIdx + 1}
                      notifBadge={groupBadge(String(b.id))}
                      onPress={() => navigation.navigate('GroupDetail', { groupId: String(b.id) })}
                    />
                  ) : (
                    <View style={{ width: HALF_W }} />
                  )}
                </View>
              );
            })}
          </View>
        )}

        <View style={{ height: 120 }} />
      </ScrollView>

      {/* ── FAB menu ──────────────────────────── */}
      <FabMenu
        visible={fabMenuOpen}
        onClose={() => setFabMenuOpen(false)}
        onCreate={() => setShowCreate(true)}
        onJoin={() => setShowJoin(true)}
        bottom={insets.bottom + 88}
      />

      {/* ── FAB ───────────────────────────────── */}
      <LinearGradient
        colors={fabMenuOpen ? [C.onSurfaceVariant, C.stone500] : [C.primary, C.primaryContainer]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.fab, { bottom: insets.bottom + 88 }]}
      >
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.fabInner}
          onPress={() => setFabMenuOpen((o) => !o)}
        >
          <Text style={[styles.msIcon, { color: C.white, fontSize: 30 }]}>
            {fabMenuOpen ? 'close' : 'add'}
          </Text>
        </TouchableOpacity>
      </LinearGradient>

      {/* ── Create Group Modal ─────────────────── */}
      <CreateGroupModal
        visible={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={handleCreate}
      />

      {/* ── Join Group Modal ───────────────────── */}
      <JoinGroupModal
        visible={showJoin}
        onClose={() => setShowJoin(false)}
        onJoin={handleJoin}
      />
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },

  
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: H_PAD, paddingTop: 8 },

  pageTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 36, color: C.onSurface, letterSpacing: -1,
    marginBottom: 20,
  },

  // Search
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 4,
    marginBottom: 28,
    gap: 8,
  },
  searchIcon: { fontSize: 22, color: C.onSurfaceVariant, opacity: 0.7 },
  searchInput: {
    flex: 1,
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 15,
    color: C.onSurface,
    paddingVertical: 12,
  },

  // Grid
  grid: { gap: CARD_GAP },
  gridRow: { flexDirection: 'row', gap: CARD_GAP },

  // Half-width card
  card: {
    width: HALF_W,
    borderRadius: 20,
    padding: 20,
    overflow: 'hidden',
    position: 'relative',
    minHeight: 220,
  },
  cardTinted: { backgroundColor: C.surfaceContainerLow },
  cardElevated: {
    backgroundColor: C.surfaceContainerLowest,
    borderWidth: 1,
    borderColor: `${C.outlineVariant}20`,
    shadowColor: '#1b1c1a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  cardDecor: {
    position: 'absolute',
    top: -40,
    right: -40,
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: `${C.primary}0d`,
  },
  cardInner: { flex: 1, justifyContent: 'space-between' },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  iconCircle: {
    width: 52, height: 52, borderRadius: 26,
    alignItems: 'center', justifyContent: 'center',
  },
  activeBadge: {
    backgroundColor: C.surfaceContainerLowest,
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 999,
  },
  activeBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 1.2,
  },
  notifBadge: {
    minWidth: 18, height: 18, paddingHorizontal: 5,
    borderRadius: 9, backgroundColor: C.error,
    alignItems: 'center', justifyContent: 'center',
  },
  notifBadgeText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10, color: C.white, lineHeight: 16,
  },
  cardName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 17, color: C.onSurface, lineHeight: 23,
    marginBottom: 16,
  },
  cardStats: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  statCol: { flex: 1 },
  statLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 1,
    marginBottom: 6,
  },
  memberRow: { flexDirection: 'row', alignItems: 'center' },
  memberCircle: {
    width: 28, height: 28, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2,
  },
  memberInitial: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11,
  },
  memberOverflow: { backgroundColor: C.surfaceContainerHighest },
  memberOverflowText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 9, color: C.onSurfaceVariant,
  },
  statDivider: {
    width: 1, height: 36,
    backgroundColor: `${C.outlineVariant}40`,
    marginHorizontal: 4,
  },
  statCount: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 18,
  },

  // Wide card
  cardWide: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 20,
    padding: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
  },
  cardWideLeft: { flex: 1 },
  cardWideName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 20, color: C.onSurface, marginBottom: 4,
  },
  cardWideRole: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13, color: C.onSurfaceVariant,
  },
  cardWideStats: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: `${C.surfaceContainerLowest}b3`,
    padding: 16,
    borderRadius: 16,
    gap: 16,
    borderWidth: 1,
    borderColor: `${C.white}66`,
  },
  wideStatItem: { alignItems: 'center', minWidth: 36 },
  wideStatNum: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 26, letterSpacing: -0.5, marginBottom: 2,
  },
  wideStatLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 9, color: C.onSurfaceVariant, letterSpacing: 1,
  },
  wideStatDivider: {
    width: 1, height: 40,
    backgroundColor: `${C.outlineVariant}40`,
  },
  wideArrowBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },

  // Empty / loading
  centered: { paddingVertical: 80, alignItems: 'center' },
  emptyState: { paddingVertical: 80, alignItems: 'center', gap: 10 },
  emptyIcon: { fontSize: 52, color: C.outlineVariant },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16, color: C.onSurfaceVariant, textAlign: 'center',
  },
  emptySub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13, color: C.onSurfaceVariant, opacity: 0.6, textAlign: 'center',
  },

  // FAB
  fab: {
    position: 'absolute',
    right: 24,
    width: 60, height: 60,
    borderRadius: 18,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
    overflow: 'hidden',
  },
  fabInner: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  // Modal
  modalBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  modalWrapper: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  modalSheet: {
    backgroundColor: C.surfaceContainerLowest,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingTop: 12,
    paddingHorizontal: 24,
  },
  modalHandle: {
    width: 40, height: 4,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 24, color: C.onSurface, letterSpacing: -0.5, marginBottom: 6,
  },
  modalSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 14, color: C.onSurfaceVariant, marginBottom: 24,
  },
  modalInput: {
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 16,
    color: C.onSurface,
    marginBottom: 20,
  },
  modalBtn: { borderRadius: 999, overflow: 'hidden' },
  modalBtnGradient: {
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 999,
  },
  modalBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15, color: C.white,
  },

  // Preset cards
  presetCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 14, padding: 14,
    borderWidth: 2, borderColor: C.surfaceContainerHigh,
  },
  presetCardSelected: {
    borderColor: C.primary,
    backgroundColor: C.primaryFixed,
  },
  presetLabel: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface,
  },
  presetDesc: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12,
    color: C.onSurfaceVariant, marginTop: 2,
  },

  // Join modal extras
  joinIconWrap: {
    width: 64, height: 64, borderRadius: 20,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    alignSelf: 'center', marginBottom: 12,
  },
  joinCodeInput: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 24,
    letterSpacing: 8,
    textAlign: 'center',
    color: C.primary,
  },

  // FAB menu
  fabMenu: {
    position: 'absolute',
    right: 24,
    alignItems: 'flex-end',
    gap: 12,
    zIndex: 99,
  },
  fabMenuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10,
    shadowRadius: 12,
    elevation: 6,
  },
  fabMenuIcon: {
    width: 40, height: 40, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
  },
  fabMenuLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 14, color: C.onSurface,
  },

  // Shared
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
    color: C.onSurface,
  },
});
