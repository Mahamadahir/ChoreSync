import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import { api } from '../../services/api';
import { Palette as C } from '../../theme';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { GroupsStackParamList } from '../../navigation/types';

// ── Types ─────────────────────────────────────────────────────────────

interface Invitation {
  id: number;
  group_id: string;
  group_name: string;
  invited_by: string | null;
  role: string;
  created_at: string;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Screen ────────────────────────────────────────────────────────────

export default function InvitationScreen() {
  const insets     = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<GroupsStackParamList>>();
  const route      = useRoute<any>();
  const invitationId: number = route.params?.invitationId;

  const [loading,    setLoading]    = useState(true);
  const [acting,     setActing]     = useState(false);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [notFound,   setNotFound]   = useState(false);

  useEffect(() => {
    api.get('/api/invitations/')
      .then(res => {
        const match = (res.data as Invitation[]).find(inv => inv.id === invitationId);
        if (match) setInvitation(match);
        else       setNotFound(true);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [invitationId]);

  const respond = useCallback(async (action: 'accept' | 'decline') => {
    setActing(true);
    try {
      const res = await api.post(`/api/invitations/${invitationId}/${action}/`);
      const detail: string = res.data?.detail ?? (action === 'accept' ? 'Joined!' : 'Invitation declined.');
      const groupId: string | undefined = res.data?.group_id;

      Alert.alert(
        action === 'accept' ? 'Joined!' : 'Declined',
        detail,
        [{
          text: 'OK',
          onPress: () => {
            if (action === 'accept' && groupId) {
              navigation.replace('GroupDetail', { groupId });
            } else {
              navigation.goBack();
            }
          },
        }],
      );
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Something went wrong. Please try again.');
    } finally {
      setActing(false);
    }
  }, [invitationId, navigation]);

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.msIcon}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Group Invitation</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.body}>
        {loading ? (
          <ActivityIndicator size="large" color={C.brandPrimary} style={{ marginTop: 64 }} />
        ) : notFound || !invitation ? (
          <View style={styles.centerBox}>
            <Text style={[styles.msIcon, styles.bigIcon]}>error_outline</Text>
            <Text style={styles.centerTitle}>Invitation not found</Text>
            <Text style={styles.centerSub}>This invitation has already been resolved or doesn't exist.</Text>
            <TouchableOpacity style={styles.backLink} onPress={() => navigation.goBack()}>
              <Text style={styles.backLinkText}>Go back</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Avatar */}
            <View style={styles.avatarWrap}>
              <View style={styles.avatar}>
                <Text style={[styles.msIcon, styles.avatarIcon]}>group_add</Text>
              </View>
              <Text style={styles.headline}>You've been invited!</Text>
              {invitation.invited_by && (
                <Text style={styles.subline}>
                  <Text style={{ fontFamily: 'PlusJakartaSans-Bold' }}>{invitation.invited_by}</Text>
                  {' '}invited you to join
                </Text>
              )}
            </View>

            {/* Group card */}
            <View style={styles.groupCard}>
              <Text style={styles.groupName}>{invitation.group_name}</Text>
              <View style={styles.metaRow}>
                <View style={styles.roleBadge}>
                  <Text style={styles.roleBadgeText}>{invitation.role.toUpperCase()}</Text>
                </View>
                <Text style={styles.timeAgo}>{timeAgo(invitation.created_at)}</Text>
              </View>
            </View>

            {/* Actions */}
            <View style={styles.actions}>
              <TouchableOpacity
                style={[styles.actionBtn, styles.declineBtn]}
                disabled={acting}
                onPress={() => respond('decline')}
              >
                <Text style={[styles.msIcon, { color: C.error, fontSize: 20 }]}>close</Text>
                <Text style={[styles.actionBtnText, { color: C.error }]}>Decline</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.actionBtn, { flex: 1 }]}
                disabled={acting}
                onPress={() => respond('accept')}
              >
                <LinearGradient
                  colors={[C.terracotta, C.brandPrimary]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.acceptGradient}
                >
                  {acting
                    ? <ActivityIndicator size="small" color="#fff" />
                    : <Text style={[styles.msIcon, { color: '#fff', fontSize: 20 }]}>check</Text>
                  }
                  <Text style={[styles.actionBtnText, { color: '#fff' }]}>Accept</Text>
                </LinearGradient>
              </TouchableOpacity>
            </View>
          </>
        )}
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.warmCream },

  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.charcoal },
  bigIcon: { fontSize: 56, color: C.stone300, marginBottom: 16 },

  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(168,162,158,0.3)',
  },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 17, color: C.charcoal },

  body: { flex: 1, paddingHorizontal: 24, paddingTop: 32 },

  centerBox: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingBottom: 80 },
  centerTitle: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.charcoal, marginBottom: 8 },
  centerSub: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 14, color: C.stone500, textAlign: 'center', lineHeight: 20 },
  backLink: { marginTop: 20 },
  backLinkText: { fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.brandPrimary },

  avatarWrap: { alignItems: 'center', marginBottom: 28 },
  avatar: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: C.primaryFixed ?? C.lightClay,
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  avatarIcon: { fontSize: 40, color: C.brandPrimary },
  headline: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 24, color: C.charcoal, marginBottom: 6 },
  subline: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 14, color: C.stone500 },

  groupCard: {
    backgroundColor: C.white, borderRadius: 20, padding: 20, marginBottom: 32,
    borderWidth: 1, borderColor: 'rgba(168,162,158,0.2)',
  },
  groupName: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 22, color: C.charcoal, marginBottom: 12 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  roleBadge: {
    backgroundColor: C.primaryFixed ?? C.lightClay, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  roleBadgeText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 10, letterSpacing: 1.2,
    color: C.brandPrimary,
  },
  timeAgo: { fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.stone400 },

  actions: { flexDirection: 'row', gap: 12 },
  actionBtn: { borderRadius: 16, overflow: 'hidden' },
  declineBtn: {
    backgroundColor: C.white, borderWidth: 1, borderColor: C.error,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingHorizontal: 20, paddingVertical: 16,
  },
  acceptGradient: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingHorizontal: 24, paddingVertical: 16,
  },
  actionBtnText: { fontFamily: 'PlusJakartaSans-Bold', fontSize: 15 },
});
