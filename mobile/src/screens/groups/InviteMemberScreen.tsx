import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Share,
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
import { groupService } from '../../services/groupService';
import { useAuthStore } from '../../stores/authStore';
import type { InviteMemberScreenProps } from '../../navigation/types';
import { Palette as C } from '../../theme';

// ── Design tokens ─────────────────────────────────────────────

// ── Pending invite type (local state only — no backend list endpoint) ──
interface PendingInvite {
  id: string;
  email: string;
  sentAt: Date;
}

// ── Pending invite row ────────────────────────────────────────
function PendingRow({
  invite,
  onRevoke,
}: {
  invite: PendingInvite;
  onRevoke: () => void;
}) {
  function timeAgo(d: Date): string {
    const mins = Math.floor((Date.now() - d.getTime()) / 60000);
    if (mins < 1)  return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)  return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <View style={styles.pendingRow}>
      <View style={styles.pendingLeft}>
        <View style={styles.pendingIconWrap}>
          <Text style={[styles.msIcon, { color: C.secondary, fontSize: 22 }]}>alternate_email</Text>
        </View>
        <View>
          <Text style={styles.pendingEmail} numberOfLines={1}>{invite.email}</Text>
          <Text style={styles.pendingSent}>Sent {timeAgo(invite.sentAt)}</Text>
        </View>
      </View>
      <View style={styles.pendingRight}>
        <View style={styles.pendingBadge}>
          <Text style={styles.pendingBadgeText}>PENDING</Text>
        </View>
        <TouchableOpacity activeOpacity={0.7} onPress={onRevoke} style={styles.revokeBtn}>
          <Text style={[styles.msIcon, { color: C.stone400, fontSize: 20 }]}>close</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────
// ── Role options per group type ────────────────────────────────
type RoleOption = { label: string; value: 'member' | 'moderator' };

function getRoleOptions(groupType?: string): RoleOption[] | null {
  if (groupType === 'flatshare') return null; // no picker — always moderator
  if (groupType === 'family') return [
    { label: 'Child', value: 'member' },
    { label: 'Adult', value: 'moderator' },
  ];
  if (groupType === 'work_team') return [
    { label: 'Member', value: 'member' },
    { label: 'Team Lead', value: 'moderator' },
  ];
  return [
    { label: 'Member', value: 'member' },
    { label: 'Moderator', value: 'moderator' },
  ];
}

export default function InviteMemberScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<InviteMemberScreenProps['route']>();
  const { groupId, groupType } = route.params;
  const user = useAuthStore((s) => s.user);

  const [groupCode, setGroupCode] = useState<string | null>(null);
  const [groupName, setGroupName] = useState<string>('');
  const [email, setEmail] = useState('');
  const [selectedRole, setSelectedRole] = useState<'member' | 'moderator'>(
    groupType === 'flatshare' ? 'moderator' : 'member',
  );
  const [sending, setSending] = useState(false);
  const [pendingInvites, setPendingInvites] = useState<PendingInvite[]>([]);
  const [copied, setCopied] = useState(false);
  const inputRef = useRef<TextInput>(null);

  const roleOptions = getRoleOptions(groupType);

  // Load group code
  useEffect(() => {
    groupService.get(groupId).then((res) => {
      setGroupCode(res.data.group_code ?? null);
      setGroupName(res.data.name ?? '');
    }).catch(() => {});
  }, [groupId]);

  const inviteLink = groupCode
    ? `choresync.com/join/${groupCode.toLowerCase()}`
    : 'loading…';

  // ── Send invite ───────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      Alert.alert('Invalid email', 'Please enter a valid email address.');
      return;
    }
    if (pendingInvites.find((p) => p.email === trimmed)) {
      Alert.alert('Already invited', `${trimmed} has already been invited.`);
      return;
    }

    setSending(true);
    try {
      await groupService.invite(groupId, trimmed, selectedRole);
      setPendingInvites((prev) => [
        { id: Date.now().toString(), email: trimmed, sentAt: new Date() },
        ...prev,
      ]);
      setEmail('');
      inputRef.current?.blur();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not send invite. Please try again.');
    } finally {
      setSending(false);
    }
  }, [email, groupId, pendingInvites, selectedRole]);

  // ── Copy link ─────────────────────────────────────────────────
  const handleCopy = useCallback(async () => {
    if (!groupCode) return;
    try {
      await Share.share({
        message: `Join "${groupName}" on ChoreSync: https://${inviteLink}`,
        url: `https://${inviteLink}`,
      });
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // user dismissed share sheet — not an error
    }
  }, [groupCode, groupName, inviteLink]);

  // ── Revoke local invite ───────────────────────────────────────
  const handleRevoke = useCallback((id: string) => {
    Alert.alert('Revoke Invite', 'Remove this pending invite?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Revoke',
        style: 'destructive',
        onPress: () => setPendingInvites((p) => p.filter((i) => i.id !== id)),
      },
    ]);
  }, []);

  return (
    <KeyboardAvoidingView
      style={[styles.root, { paddingTop: insets.top }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={0}
    >
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.stone500 }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>Invite Member</Text>
        </View>
        <View style={styles.topBarAvatar}>
          <Text style={styles.topBarAvatarText}>
            {(user?.first_name?.[0] ?? user?.username?.[0] ?? 'U').toUpperCase()}
          </Text>
        </View>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 40 }]}
      >

        {/* ── Hero ──────────────────────────────────── */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>
            Grow your {'\n'}
            <Text style={styles.heroTitleAccent}>homestead team.</Text>
          </Text>
          <Text style={styles.heroSub}>
            Managing chores is better together. Invite family members or roommates to sync schedules and share responsibilities.
          </Text>
        </View>

        {/* ── Email invite ──────────────────────────── */}
        <View style={styles.emailSection}>
          <View style={styles.emailRow}>
            <TextInput
              ref={inputRef}
              style={styles.emailInput}
              value={email}
              onChangeText={setEmail}
              placeholder="Enter family email address"
              placeholderTextColor={C.stone400}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="send"
              onSubmitEditing={handleSend}
              editable={!sending}
            />
            <TouchableOpacity
              activeOpacity={sending ? 1 : 0.88}
              onPress={handleSend}
              disabled={sending || !email.trim()}
              style={styles.sendBtnWrap}
            >
              <LinearGradient
                colors={sending || !email.trim()
                  ? [C.surfaceContainerHigh, C.surfaceContainerHigh]
                  : [C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={styles.sendBtn}
              >
                <Text style={[
                  styles.msIcon,
                  { fontSize: 20, color: sending || !email.trim() ? C.onSurfaceVariant : C.white },
                ]}>
                  {sending ? 'hourglass_top' : 'send'}
                </Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>

        {/* ── Role picker (not shown for flatshare) ── */}
        {roleOptions && (
          <View style={styles.roleSection}>
            <Text style={styles.roleLabel}>JOINING AS</Text>
            <View style={styles.roleRow}>
              {roleOptions.map((opt) => (
                <TouchableOpacity
                  key={opt.value}
                  activeOpacity={0.8}
                  onPress={() => setSelectedRole(opt.value)}
                  style={[
                    styles.roleChip,
                    selectedRole === opt.value && styles.roleChipActive,
                  ]}
                >
                  <Text style={[
                    styles.roleChipText,
                    selectedRole === opt.value && styles.roleChipTextActive,
                  ]}>
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}
        {groupType === 'flatshare' && (
          <View style={styles.roleSection}>
            <Text style={styles.flatshareNote}>
              All housemates join with full access — no role needed.
            </Text>
          </View>
        )}

        {/* ── Share link ────────────────────────────── */}
        <View style={styles.shareLinkSection}>
          <Text style={styles.shareLinkLabel}>OR SHARE INVITE LINK</Text>
          <View style={styles.shareLinkRow}>
            <Text style={styles.shareLinkText} numberOfLines={1}>{inviteLink}</Text>
            <TouchableOpacity
              activeOpacity={0.8}
              onPress={handleCopy}
              style={styles.copyBtn}
            >
              <Text style={[styles.msIcon, { color: C.primary, fontSize: 20 }]}>
                {copied ? 'check' : 'content_copy'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* ── Pending invites ───────────────────────── */}
        <View style={styles.pendingSection}>
          <View style={styles.pendingHeader}>
            <Text style={styles.pendingSectionTitle}>Pending Invites</Text>
            <View style={styles.pendingCountBadge}>
              <Text style={styles.pendingCountText}>{pendingInvites.length} Total</Text>
            </View>
          </View>

          <View style={styles.pendingList}>
            {pendingInvites.map((invite) => (
              <PendingRow
                key={invite.id}
                invite={invite}
                onRevoke={() => handleRevoke(invite.id)}
              />
            ))}

            {/* Empty state — always shown so the section never looks blank */}
            <View style={styles.emptyState}>
              <View style={styles.emptyIconWrap}>
                <Text style={[styles.msIcon, { color: C.stone400, fontSize: 28 }]}>mail</Text>
              </View>
              <Text style={styles.emptyTitle}>
                {pendingInvites.length === 0 ? 'No pending invites' : 'More invites on the way'}
              </Text>
              <Text style={styles.emptySub}>
                When you invite more people, they will appear here until they join.
              </Text>
            </View>
          </View>
        </View>

      </ScrollView>
    </KeyboardAvoidingView>
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
  topBarAvatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center',
  },
  topBarAvatarText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurfaceVariant,
  },

  // Scroll
  scrollContent: { paddingHorizontal: 24, paddingTop: 8 },

  // Hero
  heroSection: { marginBottom: 36, gap: 12 },
  heroTitle: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 34,
    color: C.onSurface, letterSpacing: -0.8, lineHeight: 40,
  },
  heroTitleAccent: {
    color: C.primary, fontStyle: 'italic',
  },
  heroSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 15,
    color: C.onSurfaceVariant, lineHeight: 23, maxWidth: 320,
  },

  // Email input row
  emailSection: { marginBottom: 24 },
  emailRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 16, padding: 6, gap: 8,
  },
  emailInput: {
    flex: 1, paddingHorizontal: 16, paddingVertical: 14,
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 15, color: C.onSurface,
  },
  sendBtnWrap: { borderRadius: 12, overflow: 'hidden' },
  sendBtn: {
    width: 48, height: 48, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
  },

  // Role picker
  roleSection: { marginBottom: 24, gap: 8 },
  roleLabel: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10,
    color: C.stone500, letterSpacing: 2, textTransform: 'uppercase',
  },
  roleRow: { flexDirection: 'row', gap: 10 },
  roleChip: {
    paddingHorizontal: 20, paddingVertical: 10, borderRadius: 999,
    backgroundColor: C.surfaceContainerHighest,
    borderWidth: 1.5, borderColor: 'transparent',
  },
  roleChipActive: {
    backgroundColor: C.primaryContainer,
    borderColor: C.primary,
  },
  roleChipText: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurfaceVariant,
  },
  roleChipTextActive: { color: C.primary },
  flatshareNote: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13,
    color: C.onSurfaceVariant, fontStyle: 'italic',
  },

  // Share link
  shareLinkSection: { marginBottom: 36, gap: 10 },
  shareLinkLabel: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10,
    color: C.stone500, letterSpacing: 2, textTransform: 'uppercase',
  },
  shareLinkRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: `${C.surfaceContainerLow}cc`,
    borderRadius: 999, paddingVertical: 10, paddingLeft: 22, paddingRight: 6,
    borderWidth: StyleSheet.hairlineWidth, borderColor: `${C.outlineVariant}26`,
  },
  shareLinkText: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 13, color: C.onSurfaceVariant, flex: 1,
  },
  copyBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center', justifyContent: 'center',
  },

  // Pending section
  pendingSection: { gap: 18 },
  pendingHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  pendingSectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.onSurface, letterSpacing: -0.3,
  },
  pendingCountBadge: {
    backgroundColor: C.surfaceContainerHigh,
    paddingHorizontal: 12, paddingVertical: 4, borderRadius: 999,
  },
  pendingCountText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 11, color: C.stone500,
  },
  pendingList: { gap: 12 },

  // Pending row
  pendingRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 18, padding: 18,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.02, shadowRadius: 16, elevation: 1,
    borderWidth: StyleSheet.hairlineWidth, borderColor: `${C.outlineVariant}1a`,
  },
  pendingLeft: { flexDirection: 'row', alignItems: 'center', gap: 14, flex: 1 },
  pendingIconWrap: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: `${C.secondaryContainer}4d`,
    alignItems: 'center', justifyContent: 'center',
  },
  pendingEmail: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 14, color: C.onSurface,
  },
  pendingSent: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant, marginTop: 2,
  },
  pendingRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  pendingBadge: {
    backgroundColor: `${C.tertiaryFixed}33`,
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999,
  },
  pendingBadgeText: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 9,
    color: C.onTertiaryFixedVariant, letterSpacing: 0.8,
  },
  revokeBtn: {
    width: 32, height: 32, alignItems: 'center', justifyContent: 'center',
  },

  // Empty state
  emptyState: {
    backgroundColor: `${C.surfaceContainerLow}80`,
    borderRadius: 18, padding: 48,
    alignItems: 'center', gap: 10,
    borderWidth: 2, borderStyle: 'dashed', borderColor: `${C.outlineVariant}33`,
  },
  emptyIconWrap: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center', justifyContent: 'center', marginBottom: 4,
  },
  emptyTitle: {
    fontFamily: 'PlusJakartaSans-Medium', fontSize: 14, color: C.stone400,
  },
  emptySub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12,
    color: `${C.stone400}99`, textAlign: 'center', maxWidth: 200, lineHeight: 18,
  },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
