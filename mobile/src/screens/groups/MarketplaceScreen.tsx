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
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { groupService } from '../../services/groupService';
import { useAuthStore } from '../../stores/authStore';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { Palette as C } from '../../theme';

// ── Design tokens ─────────────────────────────────────────────

// ── Types ─────────────────────────────────────────────────────
interface MarketplaceListing {
  id: number;
  task_occurrence_id: number;
  task_name: string;
  category: string;
  group_id: string;
  group_name: string;
  listed_by_id: string;
  listed_by_username: string;
  bonus_points: number;
  deadline: string;
  expires_at: string;
  created_at: string;
  claimed?: boolean; // optimistic local state
}

// ── Category config ───────────────────────────────────────────
type CategoryId = 'all' | 'cleaning' | 'cooking' | 'laundry' | 'maintenance' | 'other';

const CATEGORIES: { id: CategoryId; label: string }[] = [
  { id: 'all',         label: 'All'         },
  { id: 'cleaning',    label: 'Cleaning'    },
  { id: 'cooking',     label: 'Cooking'     },
  { id: 'laundry',     label: 'Laundry'     },
  { id: 'maintenance', label: 'Maintenance' },
  { id: 'other',       label: 'Other'       },
];

// Category → badge colours
const CAT_BADGE: Record<string, { bg: string; fg: string }> = {
  cleaning:    { bg: C.secondaryContainer,     fg: C.onSecondaryContainer   },
  cooking:     { bg: C.tertiaryFixed,          fg: C.onTertiaryFixedVariant },
  laundry:     { bg: C.primaryFixed,           fg: '#792f27'                },
  maintenance: { bg: C.surfaceContainerHighest,fg: C.onSurfaceVariant       },
  other:       { bg: C.surfaceContainerHigh,   fg: C.onSurfaceVariant       },
};

// ── Helpers ───────────────────────────────────────────────────
function formatDeadline(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = d.getTime() - now.getTime();
  const days = Math.floor(diff / 86400000);
  if (days < 0)  return 'Overdue';
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  if (days < 7)  return d.toLocaleDateString('en-US', { weekday: 'long' });
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function initials(username: string): string {
  return username.slice(0, 2).toUpperCase();
}

// ── Listing card ──────────────────────────────────────────────
function ListingCard({
  listing,
  isOwn,
  onClaim,
  claiming,
  onCancel,
  cancelling,
}: {
  listing: MarketplaceListing;
  isOwn: boolean;
  onClaim: () => void;
  claiming: boolean;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const catBadge = CAT_BADGE[listing.category] ?? CAT_BADGE.other;
  const deadlineStr = formatDeadline(listing.deadline);
  const isOverdue = deadlineStr === 'Overdue';
  const isClaimed = listing.claimed;

  if (isClaimed) {
    return (
      <View style={[styles.card, styles.cardClaimed]}>
        {/* Claimed banner */}
        <View style={styles.claimedBanner}>
          <Text style={styles.claimedBannerText}>Claimed</Text>
          <Text style={[styles.msIcon, { color: C.white, fontSize: 16 }]}>check_circle</Text>
        </View>

        {/* Category + title */}
        <View style={styles.cardHeader}>
          <View style={[styles.catBadge, { backgroundColor: C.surfaceContainerHighest }]}>
            <Text style={[styles.catBadgeText, { color: C.onSurfaceVariant }]}>
              {listing.category.toUpperCase()}
            </Text>
          </View>
          <Text style={[styles.cardTitle, { color: C.onSurfaceVariant }]}>{listing.task_name}</Text>
          <View style={styles.cardGroupRow}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>home_work</Text>
            <Text style={styles.cardGroupName}>{listing.group_name}</Text>
          </View>
        </View>

        {/* Meta row */}
        <View style={styles.cardMeta}>
          <View style={styles.cardMetaLeft}>
            <View style={[styles.avatarCircle, { opacity: 0.6 }]}>
              <Text style={styles.avatarInitials}>{initials(listing.listed_by_username)}</Text>
            </View>
            <View>
              <Text style={styles.metaLabel}>LISTED BY</Text>
              <Text style={styles.metaValue}>{listing.listed_by_username}</Text>
            </View>
          </View>
          <View style={styles.cardMetaRight}>
            <Text style={styles.metaLabel}>STATUS</Text>
            <Text style={[styles.metaValue, { color: C.secondary }]}>In Progress</Text>
          </View>
        </View>

        {/* Progress bar */}
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '100%' }]} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      {/* Top row: category badge + XP pill */}
      <View style={styles.cardTopRow}>
        <View>
          <View style={[styles.catBadge, { backgroundColor: catBadge.bg }]}>
            <Text style={[styles.catBadgeText, { color: catBadge.fg }]}>
              {listing.category.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.cardTitle}>{listing.task_name}</Text>
          <View style={styles.cardGroupRow}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant, fontSize: 14 }]}>home_work</Text>
            <Text style={styles.cardGroupName}>{listing.group_name}</Text>
          </View>
        </View>
        {listing.bonus_points > 0 && (
          <View style={styles.xpPill}>
            <Text style={styles.xpPillText}>+{listing.bonus_points} XP</Text>
          </View>
        )}
      </View>

      {/* Divider row: lister + deadline */}
      <View style={styles.cardMeta}>
        <View style={styles.cardMetaLeft}>
          <View style={styles.avatarCircle}>
            <Text style={styles.avatarInitials}>{initials(listing.listed_by_username)}</Text>
          </View>
          <View>
            <Text style={styles.metaLabel}>LISTED BY</Text>
            <Text style={styles.metaValue}>{listing.listed_by_username}</Text>
          </View>
        </View>
        <View style={styles.cardMetaRight}>
          <Text style={styles.metaLabel}>DEADLINE</Text>
          <Text style={[styles.metaValue, { color: isOverdue ? C.error : C.primary }]}>
            {deadlineStr}
          </Text>
        </View>
      </View>

      {/* Claim or Cancel button */}
      {isOwn ? (
        <TouchableOpacity
          activeOpacity={cancelling ? 1 : 0.88}
          onPress={onCancel}
          disabled={cancelling}
          style={[styles.claimBtnWrap, { backgroundColor: C.errorContainer, borderRadius: 14 }]}
        >
          <View style={[styles.claimBtn, { backgroundColor: 'transparent' }]}>
            {cancelling
              ? <ActivityIndicator color={C.error} size="small" />
              : <Text style={[styles.claimBtnText, { color: C.error }]}>Remove Listing</Text>
            }
          </View>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          activeOpacity={claiming ? 1 : 0.88}
          onPress={onClaim}
          disabled={claiming}
          style={styles.claimBtnWrap}
        >
          <LinearGradient
            colors={[C.primary, C.primaryContainer]}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={styles.claimBtn}
          >
            {claiming
              ? <ActivityIndicator color={C.white} size="small" />
              : <Text style={styles.claimBtnText}>Claim Task</Text>
            }
          </LinearGradient>
        </TouchableOpacity>
      )}
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────
export default function MarketplaceScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<MarketplaceScreenProps['route']>();
  const { groupId } = route.params;
  const currentUser = useAuthStore((s) => s.user);

  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [claiming, setClaiming] = useState<Record<number, boolean>>({});
  const [cancelling, setCancelling] = useState<Record<number, boolean>>({});
  const [activeCategory, setActiveCategory] = useState<CategoryId>('all');

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await groupService.marketplace(groupId);
      const data: MarketplaceListing[] = Array.isArray(res.data)
        ? res.data
        : (res.data?.results ?? []);
      setListings(data);
    } catch (e: any) {
      console.error('MarketplaceScreen: load failed', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [groupId]);

  useEffect(() => { load(); }, [load]);
  // Refresh when navigating back to this screen so stale listings disappear
  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function handleClaim(listing: MarketplaceListing) {
    Alert.alert(
      'Claim Task',
      `Take on "${listing.task_name}"${listing.bonus_points > 0 ? ` for +${listing.bonus_points} bonus XP` : ''}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Claim',
          onPress: async () => {
            setClaiming((p) => ({ ...p, [listing.id]: true }));
            try {
              await groupService.claimListing(listing.id);
              await load();
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not claim this task.');
            } finally {
              setClaiming((p) => ({ ...p, [listing.id]: false }));
            }
          },
        },
      ],
    );
  }

  async function handleCancel(listing: MarketplaceListing) {
    Alert.alert(
      'Remove Listing',
      `Remove "${listing.task_name}" from the marketplace?`,
      [
        { text: 'Keep Listed', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setCancelling((p) => ({ ...p, [listing.id]: true }));
            try {
              await groupService.cancelListing(listing.id);
              setListings((prev) => prev.filter((l) => l.id !== listing.id));
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not remove listing.');
            } finally {
              setCancelling((p) => ({ ...p, [listing.id]: false }));
            }
          },
        },
      ],
    );
  }

  const filtered = activeCategory === 'all'
    ? listings
    : listings.filter((l) => l.category === activeCategory);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.onSurfaceVariant }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>Marketplace</Text>
        </View>
        <TouchableOpacity style={styles.topBarFilterBtn} activeOpacity={0.75}>
          <Text style={[styles.msIcon, { color: C.onSurface, fontSize: 22 }]}>tune</Text>
        </TouchableOpacity>
      </View>

      {/* ── Subtitle ────────────────────────────── */}
      <View style={styles.subtitleRow}>
        <Text style={styles.subtitle}>Claim tasks from your group members</Text>
      </View>

      {/* ── Category filter chips ────────────────── */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipsContent}
        style={styles.chipsScroll}
      >
        {CATEGORIES.map((cat) => {
          const active = activeCategory === cat.id;
          return active ? (
            <TouchableOpacity
              key={cat.id}
              activeOpacity={0.9}
              onPress={() => setActiveCategory(cat.id)}
              style={styles.chipWrap}
            >
              <LinearGradient
                colors={[C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={styles.chipActive}
              >
                <Text style={styles.chipActiveText}>{cat.label}</Text>
              </LinearGradient>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              key={cat.id}
              activeOpacity={0.8}
              onPress={() => setActiveCategory(cat.id)}
              style={[styles.chipWrap, styles.chipInactive]}
            >
              <Text style={styles.chipInactiveText}>{cat.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* ── Listings ─────────────────────────────── */}
      {loading ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={C.primary} size="large" />
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={C.primary} />
          }
          contentContainerStyle={[
            styles.listContent,
            { paddingBottom: insets.bottom + 32 },
          ]}
        >
          {filtered.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={[styles.msIcon, { fontSize: 52, color: C.outlineVariant }]}>storefront</Text>
              <Text style={styles.emptyTitle}>Nothing listed yet</Text>
              <Text style={styles.emptySub}>
                {activeCategory === 'all'
                  ? 'Group members can list tasks here for others to claim.'
                  : `No ${activeCategory} tasks listed right now.`}
              </Text>
            </View>
          ) : (
            filtered.map((listing) => (
              <ListingCard
                key={listing.id}
                listing={listing}
                isOwn={listing.listed_by_id === currentUser?.id}
                onClaim={() => handleClaim(listing)}
                claiming={!!claiming[listing.id]}
                onCancel={() => handleCancel(listing)}
                cancelling={!!cancelling[listing.id]}
              />
            ))
          )}
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
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  topBarBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.primary, letterSpacing: -0.4,
  },
  topBarFilterBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.surfaceContainer,
    alignItems: 'center', justifyContent: 'center',
  },

  // Subtitle
  subtitleRow: { paddingHorizontal: 24, paddingBottom: 12 },
  subtitle: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 16, color: C.onSurfaceVariant,
  },

  // Category chips
  chipsScroll: { maxHeight: 52, marginBottom: 8 },
  chipsContent: { paddingHorizontal: 24, gap: 10, alignItems: 'center' },
  chipWrap: { borderRadius: 999, overflow: 'hidden' },
  chipActive: { paddingHorizontal: 22, paddingVertical: 10 },
  chipActiveText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13, color: C.white,
  },
  chipInactive: {
    backgroundColor: C.surfaceContainer,
    paddingHorizontal: 22, paddingVertical: 10,
  },
  chipInactiveText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 13, color: C.onSurfaceVariant,
  },

  // Listings
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  listContent: { paddingHorizontal: 24, paddingTop: 8, gap: 20 },

  // Card
  card: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 20, padding: 22, gap: 16,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04, shadowRadius: 16, elevation: 2,
    borderWidth: StyleSheet.hairlineWidth, borderColor: `${C.outlineVariant}1a`,
  },
  cardClaimed: {
    backgroundColor: C.surfaceContainer, opacity: 0.85,
  },

  // Claimed banner (top-right absolute)
  claimedBanner: {
    position: 'absolute', top: 0, right: 0,
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.secondary,
    paddingHorizontal: 14, paddingVertical: 6,
    borderTopRightRadius: 20, borderBottomLeftRadius: 14,
  },
  claimedBannerText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11, color: C.white,
  },

  // Card sections
  cardTopRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  cardHeader: { gap: 4 },

  catBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, marginBottom: 6,
  },
  catBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 10, letterSpacing: 1,
  },
  cardTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 22,
    color: C.onSurface, letterSpacing: -0.4, lineHeight: 28,
  },
  cardGroupRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  cardGroupName: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.onSurfaceVariant,
  },

  xpPill: {
    backgroundColor: C.tertiaryFixed,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 12,
  },
  xpPillText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 13, color: C.onTertiaryFixed,
  },

  // Meta row
  cardMeta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: 14,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: `${C.surfaceContainerLow}80`,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: `${C.surfaceContainerLow}80`,
  },
  cardMetaLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  cardMetaRight: { alignItems: 'flex-end' },
  avatarCircle: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.secondaryContainer,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: C.bg,
  },
  avatarInitials: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 13, color: C.onSecondaryContainer,
  },
  metaLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 10,
    color: C.stone500, letterSpacing: 1.2, textTransform: 'uppercase',
    marginBottom: 1,
  },
  metaValue: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurface,
  },

  // Claim button
  claimBtnWrap: { borderRadius: 14, overflow: 'hidden' },
  claimBtn: {
    paddingVertical: 18, alignItems: 'center', justifyContent: 'center',
    borderRadius: 14,
  },
  claimBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 16, color: C.white,
  },

  // Progress bar (claimed state)
  progressTrack: {
    height: 10, backgroundColor: C.surfaceContainerHighest,
    borderRadius: 5, overflow: 'hidden',
  },
  progressFill: {
    height: '100%', backgroundColor: C.secondary, borderRadius: 5,
  },

  // Empty state
  emptyState: {
    paddingVertical: 80, alignItems: 'center', gap: 12,
  },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 18, color: C.onSurfaceVariant,
  },
  emptySub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.onSurfaceVariant,
    textAlign: 'center', maxWidth: 260, lineHeight: 20,
  },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
