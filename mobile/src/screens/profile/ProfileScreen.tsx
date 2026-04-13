import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Constants from 'expo-constants';
import { useAuthStore } from '../../stores/authStore';
import { api } from '../../services/api';
import { authService } from '../../services/authService';
import type { RootStackParamList } from '../../navigation/types';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Profile'>;


// ── Bento card ────────────────────────────────────────────────
function BentoCard({
  icon,
  sectionLabel,
  valueText,
  onPress,
  style,
}: {
  icon: string;
  sectionLabel: string;
  valueText: string;
  onPress: () => void;
  style?: object;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={[styles.bentoCard, style]}
    >
      <View style={styles.bentoCardTop}>
        <Text style={[styles.msIcon, { color: C.primary, fontSize: 24 }]}>{icon}</Text>
        <Text style={[styles.msIcon, { color: C.outline, fontSize: 18 }]}>chevron_right</Text>
      </View>
      <Text style={styles.bentoCardLabel}>{sectionLabel}</Text>
      <Text style={styles.bentoCardValue}>{valueText}</Text>
    </TouchableOpacity>
  );
}

// ── Calendar row ──────────────────────────────────────────────
function CalendarRow({
  icon,
  iconBg,
  iconColor,
  label,
  subtitle,
  connected,
  onToggle,
  last = false,
}: {
  icon: string;
  iconBg: string;
  iconColor: string;
  label: string;
  subtitle: string;
  connected: boolean;
  onToggle: (v: boolean) => void;
  last?: boolean;
}) {
  return (
    <View style={[styles.calRow, last && { opacity: connected ? 1 : 0.8 }]}>
      <View style={styles.calLeft}>
        <View style={[styles.calIconWrap, { backgroundColor: iconBg }]}>
          <Text style={[styles.msIcon, { color: iconColor, fontSize: 22 }]}>{icon}</Text>
        </View>
        <View>
          <Text style={styles.calLabel}>{label}</Text>
          <Text style={styles.calSub}>{subtitle}</Text>
        </View>
      </View>
      {/* Custom pill toggle matching the HTML */}
      <Switch
        value={connected}
        onValueChange={onToggle}
        trackColor={{ false: C.surfaceContainerHighest, true: C.secondary }}
        thumbColor={C.white}
        ios_backgroundColor={C.surfaceContainerHighest}
      />
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────
export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<Nav>();
  const { user, logout } = useAuthStore();

  const [stats, setStats] = useState<{ current_streak_days: number; total_points: number } | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState(false);
  const [statsRetry, setStatsRetry] = useState(0);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [outlookConnected, setOutlookConnected] = useState(false);

  // Badges
  const [badges, setBadges] = useState<any[]>([]);
  const [loadingBadges, setLoadingBadges] = useState(true);
  const [badgesError, setBadgesError] = useState(false);
  const [badgesRetry, setBadgesRetry] = useState(0);
  const [selectedBadge, setSelectedBadge] = useState<any>(null);
  const [badgeModalOpen, setBadgeModalOpen] = useState(false);

  // Avatar upload
  const [avatarUrl, setAvatarUrl] = useState<string | null>(user?.avatar_url ?? null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  // Email change modal
  const [emailModal, setEmailModal] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailSaving, setEmailSaving] = useState(false);

  // Password change modal
  const [pwModal, setPwModal] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  // Edit profile modal (name / username / timezone)
  const [editProfileModal, setEditProfileModal] = useState(false);
  const [editFirstName, setEditFirstName] = useState('');
  const [editLastName, setEditLastName] = useState('');
  const [editUsername, setEditUsername] = useState('');
  const [editTimezone, setEditTimezone] = useState('');
  const [editProfileSaving, setEditProfileSaving] = useState(false);

  const displayName = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username
    : 'You';

  const initials = String(displayName)
    .split(' ')
    .slice(0, 2)
    .map((w: string) => w[0]?.toUpperCase() ?? '')
    .join('');

  useEffect(() => {
    setLoadingStats(true);
    setStatsError(false);
    async function loadStats() {
      try {
        const res = await api.get('/api/users/me/stats/');
        const raw = res.data;
        if (Array.isArray(raw) && raw.length > 0) {
          setStats({
            current_streak_days: Math.max(...raw.map((s: any) => s.current_streak_days || 0)),
            total_points: raw.reduce((acc: number, s: any) => acc + (s.total_points || 0), 0),
          });
        } else if (raw && !Array.isArray(raw)) {
          setStats(raw);
        }
      } catch {
        setStatsError(true);
      } finally {
        setLoadingStats(false);
      }
    }
    loadStats();
  }, [statsRetry]);

  useEffect(() => {
    setLoadingBadges(true);
    setBadgesError(false);
    async function loadBadges() {
      try {
        const res = await api.get('/api/users/me/badges/');
        setBadges(Array.isArray(res.data) ? res.data : []);
      } catch {
        setBadgesError(true);
      } finally {
        setLoadingBadges(false);
      }
    }
    loadBadges();
  }, [badgesRetry]);

  async function pickAvatar() {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission required', 'Please allow photo library access to upload a profile picture.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.85,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    setUploadingAvatar(true);
    try {
      const formData = new FormData();
      formData.append('avatar', {
        uri: asset.uri,
        name: asset.fileName ?? 'avatar.jpg',
        type: asset.mimeType ?? 'image/jpeg',
      } as any);
      const res = await api.post('/api/users/me/avatar/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setAvatarUrl(res.data.avatar_url);
    } catch {
      Alert.alert('Upload failed', 'Could not upload photo. Please try again.');
    } finally {
      setUploadingAvatar(false);
    }
  }

  function handleLogout() {
    Alert.alert('Log Out', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log Out', style: 'destructive', onPress: () => logout() },
    ]);
  }

  function openEditProfile() {
    setEditFirstName(user?.first_name ?? '');
    setEditLastName(user?.last_name ?? '');
    setEditUsername(user?.username ?? '');
    setEditTimezone(user?.timezone ?? '');
    setEditProfileModal(true);
  }

  async function submitEditProfile() {
    const username = editUsername.trim();
    if (!username) {
      Alert.alert('Validation', 'Username cannot be empty.');
      return;
    }
    setEditProfileSaving(true);
    try {
      const res = await authService.updateProfile({
        first_name: editFirstName.trim(),
        last_name: editLastName.trim(),
        username,
        timezone: editTimezone.trim() || undefined,
      });
      // Refresh user in auth store so header/display name updates
      const { setUser } = useAuthStore.getState();
      setUser(res.data);
      setEditProfileModal(false);
      Alert.alert('Done', 'Profile updated.');
    } catch (e: any) {
      const msg = e?.response?.data?.username?.[0]
        ?? e?.response?.data?.detail
        ?? 'Could not update profile. Please try again.';
      Alert.alert('Error', msg);
    } finally {
      setEditProfileSaving(false);
    }
  }

  function handleGoogleToggle(val: boolean) {
    if (val) {
      // Navigate to the Calendar screen where the user can connect Google Calendar
      (navigation as any).navigate('CalendarTab', { screen: 'CalendarMain' });
    } else {
      setGoogleConnected(false);
    }
  }

  function handleOutlookToggle(val: boolean) {
    if (val) {
      // Navigate to the Calendar screen where the user can connect Outlook Calendar
      (navigation as any).navigate('CalendarTab', { screen: 'CalendarMain' });
    } else {
      setOutlookConnected(false);
    }
  }

  async function submitEmailChange() {
    const trimmed = newEmail.trim();
    if (!trimmed) return;
    setEmailSaving(true);
    try {
      await api.post('/api/profile/', { email: trimmed });
      setEmailModal(false);
      setNewEmail('');
      Alert.alert('Done', 'Email updated. Check your inbox to verify the new address.');
    } catch {
      Alert.alert('Error', 'Could not update email. Please try again.');
    } finally {
      setEmailSaving(false);
    }
  }

  async function submitPasswordChange() {
    if (!currentPw || !newPw || !confirmPw) {
      Alert.alert('Missing fields', 'Please fill in all fields.');
      return;
    }
    if (newPw !== confirmPw) {
      Alert.alert('Mismatch', 'New passwords do not match.');
      return;
    }
    setPwSaving(true);
    try {
      await api.post('/api/auth/change-password/', {
        current_password: currentPw,
        new_password: newPw,
        confirm_password: confirmPw,
      });
      setPwModal(false);
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
      Alert.alert('Done', 'Password changed successfully.');
    } catch {
      Alert.alert('Error', 'Could not change password. Check your current password and try again.');
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <Text style={styles.topBarTitle}>ChoreSync</Text>
        </View>
        <TouchableOpacity
          onPress={() => navigation.navigate('NotificationPreferences')}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Text style={[styles.msIcon, styles.topBarNotif]}>notifications</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 100 },
        ]}
      >

        {/* ── Hero Profile ────────────────────────── */}
        <View style={styles.heroSection}>
          {/* Avatar */}
          <View style={styles.avatarWrap}>
            <View style={styles.avatarRing}>
              <View style={styles.avatarCircle}>
                {avatarUrl ? (
                  <Image
                    source={{ uri: avatarUrl }}
                    style={styles.avatarImage}
                    resizeMode="cover"
                  />
                ) : (
                  <Text style={styles.avatarInitials}>{initials}</Text>
                )}
              </View>
            </View>
            {/* Edit button */}
            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.editBtn}
              onPress={pickAvatar}
              disabled={uploadingAvatar}
            >
              <View style={[styles.editBtnInner, { backgroundColor: C.primary }]}>
                {uploadingAvatar ? (
                  <ActivityIndicator color={C.white} size="small" />
                ) : (
                  <Text style={[styles.msIcon, styles.editBtnIcon]}>edit</Text>
                )}
              </View>
            </TouchableOpacity>
          </View>

          {/* Name */}
          <Text style={styles.heroName}>{displayName}</Text>

          {/* Streak + Points pills */}
          <View style={styles.pillsRow}>
            {loadingStats ? (
              <ActivityIndicator color={C.primary} size="small" />
            ) : statsError ? (
              <TouchableOpacity onPress={() => setStatsRetry((n) => n + 1)}>
                <Text style={[styles.bentoCardValue, { color: C.outline }]}>Failed to load stats — tap to retry</Text>
              </TouchableOpacity>
            ) : (
              <>
                {/* Streak — secondary-container */}
                <View style={[styles.pill, { backgroundColor: C.secondaryContainer }]}>
                  <Text style={[styles.msIcon, styles.pillIcon, { color: C.onSecondaryContainer }]}>
                    local_fire_department
                  </Text>
                  <Text style={[styles.pillText, { color: C.onSecondaryContainer }]}>
                    {stats?.current_streak_days ?? 0} DAY STREAK
                  </Text>
                </View>
                {/* Points — tertiary-fixed */}
                <View style={[styles.pill, { backgroundColor: C.tertiaryFixed }]}>
                  <Text style={[styles.msIcon, styles.pillIcon, { color: C.onTertiaryFixed }]}>
                    stars
                  </Text>
                  <Text style={[styles.pillText, { color: C.onTertiaryFixed }]}>
                    {(stats?.total_points ?? 0).toLocaleString()} PTS
                  </Text>
                </View>
              </>
            )}
          </View>
        </View>

        {/* ── Account Settings Bento Grid ────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>ACCOUNT SETTINGS</Text>
          {/* Row 1: Edit Profile full-width */}
          <TouchableOpacity
            onPress={openEditProfile}
            activeOpacity={0.75}
            style={[styles.notifCard, { marginBottom: 10 }]}
          >
            <View style={styles.notifCardLeft}>
              <View style={styles.notifIconWrap}>
                <Text style={[styles.msIcon, { color: C.primary, fontSize: 22 }]}>manage_accounts</Text>
              </View>
              <View>
                <Text style={styles.bentoCardLabel}>EDIT PROFILE</Text>
                <Text style={styles.bentoCardValue}>
                  {[user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Tap to edit'}
                </Text>
              </View>
            </View>
            <Text style={[styles.msIcon, { color: C.outline, fontSize: 18 }]}>chevron_right</Text>
          </TouchableOpacity>
          {/* Row 2: Email + Password side by side */}
          <View style={styles.bentoRow}>
            <BentoCard
              icon="mail"
              sectionLabel="EMAIL ADDRESS"
              valueText={user?.email ?? 'tap to update'}
              onPress={() => { setNewEmail(user?.email ?? ''); setEmailModal(true); }}
              style={{ flex: 1, marginRight: 6 }}
            />
            <BentoCard
              icon="lock"
              sectionLabel="PASSWORD"
              valueText="••••••••••••"
              onPress={() => setPwModal(true)}
              style={{ flex: 1, marginLeft: 6 }}
            />
          </View>
          {/* Row 2: Notifications full-width */}
          <TouchableOpacity
            onPress={() => navigation.navigate('NotificationPreferences')}
            activeOpacity={0.75}
            style={styles.notifCard}
          >
            <View style={styles.notifCardLeft}>
              <View style={styles.notifIconWrap}>
                <Text style={[styles.msIcon, { color: C.primary, fontSize: 22 }]}>
                  notifications_active
                </Text>
              </View>
              <View>
                <Text style={styles.bentoCardLabel}>NOTIFICATIONS</Text>
                <Text style={styles.bentoCardValue}>All alerts enabled</Text>
              </View>
            </View>
            <Text style={[styles.msIcon, { color: C.outline, fontSize: 18 }]}>chevron_right</Text>
          </TouchableOpacity>
        </View>

        {/* ── Connected Calendars ──────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>CONNECTED CALENDARS</Text>
          <View style={styles.calCard}>
            <CalendarRow
              icon="calendar_today"
              iconBg="#EFF6FF"
              iconColor="#2563EB"
              label="Google Calendar"
              subtitle={googleConnected ? 'Connected' : 'Not connected'}
              connected={googleConnected}
              onToggle={handleGoogleToggle}
            />
            <View style={styles.calDivider} />
            <CalendarRow
              icon="event"
              iconBg={C.surfaceContainerHighest}
              iconColor={C.stone500}
              label="Outlook Calendar"
              subtitle={outlookConnected ? 'Connected' : 'Not connected'}
              connected={outlookConnected}
              onToggle={handleOutlookToggle}
              last
            />
          </View>
        </View>

        {/* ── Achievements / Badges ───────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>ACHIEVEMENTS</Text>
          {loadingBadges ? (
            <ActivityIndicator color={C.primary} size="small" style={{ alignSelf: 'flex-start' }} />
          ) : badgesError ? (
            <TouchableOpacity onPress={() => setBadgesRetry((n) => n + 1)}>
              <Text style={[styles.badgeEmptyText, { color: C.outline }]}>Failed to load — tap to retry</Text>
            </TouchableOpacity>
          ) : badges.length === 0 ? (
            <View style={styles.badgeEmpty}>
              <Text style={[styles.msIcon, { color: C.outline, fontSize: 28 }]}>emoji_events</Text>
              <Text style={styles.badgeEmptyText}>No badges earned yet.</Text>
            </View>
          ) : (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
              {badges.map((b) => (
                <TouchableOpacity
                  key={b.badge_id}
                  activeOpacity={0.75}
                  style={styles.badgeChip}
                  onPress={() => { setSelectedBadge(b); setBadgeModalOpen(true); }}
                >
                  {b.emoji ? (
                    <Text style={styles.badgeChipEmoji}>{b.emoji}</Text>
                  ) : (
                    <Text style={[styles.msIcon, { color: C.secondary, fontSize: 14 }]}>emoji_events</Text>
                  )}
                  <Text style={styles.badgeChipLabel}>{b.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}
        </View>

        {/* ── Logout ───────────────────────────────── */}
        <View style={styles.footerSection}>
          <TouchableOpacity
            onPress={handleLogout}
            activeOpacity={0.8}
            style={styles.logoutBtn}
          >
            <Text style={styles.logoutBtnText}>Log Out</Text>
          </TouchableOpacity>
          <Text style={styles.versionText}>
            CHORESYNC VERSION {Constants.expoConfig?.version ?? '1.0.0'}
          </Text>
        </View>

      </ScrollView>

      {/* ── Change Email Modal ──────────────────── */}
      <Modal visible={emailModal} transparent animationType="slide" onRequestClose={() => setEmailModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Change Email</Text>
            <Text style={styles.modalLabel}>New email address</Text>
            <TextInput
              style={styles.modalInput}
              value={newEmail}
              onChangeText={setNewEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              autoCorrect={false}
              placeholder="you@example.com"
              placeholderTextColor={C.outline}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnGhost]}
                onPress={() => setEmailModal(false)}
              >
                <Text style={[styles.modalBtnText, { color: C.onSurfaceVariant }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, { backgroundColor: C.primary }]}
                onPress={submitEmailChange}
                disabled={emailSaving}
              >
                {emailSaving
                  ? <ActivityIndicator color={C.white} size="small" />
                  : <Text style={[styles.modalBtnText, { color: C.white }]}>Save</Text>
                }
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Change Password Modal ────────────────── */}
      <Modal visible={pwModal} transparent animationType="slide" onRequestClose={() => setPwModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Change Password</Text>
            <Text style={styles.modalLabel}>Current password</Text>
            <TextInput
              style={styles.modalInput}
              value={currentPw}
              onChangeText={setCurrentPw}
              secureTextEntry
              placeholder="Enter current password"
              placeholderTextColor={C.outline}
            />
            <Text style={[styles.modalLabel, { marginTop: 12 }]}>New password</Text>
            <TextInput
              style={styles.modalInput}
              value={newPw}
              onChangeText={setNewPw}
              secureTextEntry
              placeholder="Enter new password"
              placeholderTextColor={C.outline}
            />
            <Text style={[styles.modalLabel, { marginTop: 12 }]}>Confirm new password</Text>
            <TextInput
              style={styles.modalInput}
              value={confirmPw}
              onChangeText={setConfirmPw}
              secureTextEntry
              placeholder="Confirm new password"
              placeholderTextColor={C.outline}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnGhost]}
                onPress={() => { setPwModal(false); setCurrentPw(''); setNewPw(''); setConfirmPw(''); }}
              >
                <Text style={[styles.modalBtnText, { color: C.onSurfaceVariant }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, { backgroundColor: C.primary }]}
                onPress={submitPasswordChange}
                disabled={pwSaving}
              >
                {pwSaving
                  ? <ActivityIndicator color={C.white} size="small" />
                  : <Text style={[styles.modalBtnText, { color: C.white }]}>Save</Text>
                }
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Edit Profile Modal ──────────────────── */}
      <Modal visible={editProfileModal} transparent animationType="slide" onRequestClose={() => setEditProfileModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Edit Profile</Text>
            <Text style={styles.modalLabel}>First Name</Text>
            <TextInput
              style={styles.modalInput}
              value={editFirstName}
              onChangeText={setEditFirstName}
              placeholder="First name"
              placeholderTextColor={C.outline}
            />
            <Text style={[styles.modalLabel, { marginTop: 12 }]}>Last Name</Text>
            <TextInput
              style={styles.modalInput}
              value={editLastName}
              onChangeText={setEditLastName}
              placeholder="Last name"
              placeholderTextColor={C.outline}
            />
            <Text style={[styles.modalLabel, { marginTop: 12 }]}>Username</Text>
            <TextInput
              style={styles.modalInput}
              value={editUsername}
              onChangeText={setEditUsername}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="username"
              placeholderTextColor={C.outline}
            />
            <Text style={[styles.modalLabel, { marginTop: 12 }]}>Timezone</Text>
            <TextInput
              style={styles.modalInput}
              value={editTimezone}
              onChangeText={setEditTimezone}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="e.g. Europe/London"
              placeholderTextColor={C.outline}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnGhost]}
                onPress={() => setEditProfileModal(false)}
              >
                <Text style={[styles.modalBtnText, { color: C.onSurfaceVariant }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, { backgroundColor: C.primary }]}
                onPress={submitEditProfile}
                disabled={editProfileSaving}
              >
                {editProfileSaving
                  ? <ActivityIndicator color={C.white} size="small" />
                  : <Text style={[styles.modalBtnText, { color: C.white }]}>Save</Text>
                }
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Badge Detail Modal ──────────────────── */}
      <Modal
        visible={badgeModalOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setBadgeModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { alignItems: 'center' }]}>
            {/* Emoji or icon */}
            {selectedBadge?.emoji ? (
              <Text style={styles.badgeModalEmoji}>{selectedBadge.emoji}</Text>
            ) : (
              <Text style={[styles.msIcon, { fontSize: 52, color: C.secondary, marginBottom: 12 }]}>emoji_events</Text>
            )}

            {/* Name */}
            <Text style={styles.badgeModalName}>{selectedBadge?.name}</Text>

            {/* Points pill */}
            <View style={styles.badgeModalPointsPill}>
              <Text style={styles.badgeModalPointsText}>+{selectedBadge?.points_value} pts</Text>
            </View>

            {/* Description */}
            <Text style={styles.badgeModalDesc}>{selectedBadge?.description}</Text>

            {/* Date & time earned */}
            {selectedBadge?.awarded_at && (
              <Text style={styles.badgeModalDate}>
                Earned {new Date(selectedBadge.awarded_at).toLocaleString(undefined, {
                  month: 'short', day: 'numeric', year: 'numeric',
                  hour: '2-digit', minute: '2-digit',
                })}
                {selectedBadge.household_name ? `\nin ${selectedBadge.household_name}` : ''}
              </Text>
            )}

            {/* Close */}
            <TouchableOpacity
              style={[styles.modalBtn, styles.modalBtnGhost, { marginTop: 24, width: '100%' }]}
              onPress={() => setBadgeModalOpen(false)}
            >
              <Text style={[styles.modalBtnText, { color: C.onSurfaceVariant }]}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
  },

  // Top bar
  topBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    backgroundColor: C.bg,
  },
  topBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  topBarMenu: {
    fontSize: 24,
    color: C.stone500,
  },
  topBarTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22,
    color: C.primary,
    letterSpacing: -0.5,
  },
  topBarNotif: {
    fontSize: 24,
    color: C.stone500,
  },

  // Scroll
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 8,
  },

  // Hero
  heroSection: {
    alignItems: 'center',
    marginBottom: 36,
    paddingTop: 8,
  },
  avatarWrap: {
    position: 'relative',
    marginBottom: 20,
  },
  avatarRing: {
    borderRadius: 999,
    padding: 4,
    borderWidth: 3,
    borderColor: C.surfaceContainerHigh,
  },
  avatarCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: C.surfaceContainerHigh,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  avatarImage: {
    width: 120,
    height: 120,
    borderRadius: 60,
  },
  avatarInitials: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 40,
    color: C.primary,
    letterSpacing: 1,
  },
  editBtn: {
    position: 'absolute',
    bottom: 0,
    right: 4,
  },
  editBtnInner: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
    elevation: 3,
  },
  editBtnIcon: {
    fontSize: 16,
    color: C.white,
  },
  heroName: {
    fontFamily: 'PlusJakartaSans-ExtraBold',
    fontSize: 28,
    color: C.onSurface,
    letterSpacing: -0.5,
    marginBottom: 12,
    textAlign: 'center',
  },
  pillsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 999,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07,
    shadowRadius: 3,
    elevation: 1,
  },
  pillIcon: {
    fontSize: 16,
  },
  pillText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 11,
    letterSpacing: 0.6,
  },

  // Section
  section: {
    marginBottom: 28,
  },
  sectionLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 11,
    color: C.onSurfaceVariant,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 14,
    paddingHorizontal: 2,
  },

  // Bento cards
  bentoRow: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  bentoCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 16,
    padding: 20,
  },
  bentoCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 14,
  },
  bentoCardLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    color: C.onSurfaceVariant,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  bentoCardValue: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 13,
    color: C.onSurface,
  },

  // Notification full-width card
  notifCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  notifCardLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    flex: 1,
  },
  notifIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Calendar cards
  calCard: {
    backgroundColor: C.surfaceContainerLowest,
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.outlineVariant,
  },
  calRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 18,
  },
  calDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: C.outlineVariant,
    marginHorizontal: 20,
  },
  calLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    flex: 1,
  },
  calIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  calLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 14,
    color: C.onSurface,
    marginBottom: 2,
  },
  calSub: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.onSurfaceVariant,
  },

  // Footer / logout
  footerSection: {
    marginTop: 4,
    marginBottom: 12,
    alignItems: 'center',
  },
  logoutBtn: {
    width: '100%',
    paddingVertical: 18,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: C.primaryContainer,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  logoutBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 16,
    color: C.primary,
  },
  versionText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    color: '#A8A29E',
    letterSpacing: 2,
    textTransform: 'uppercase',
  },

  // Shared
  msIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
    color: C.onSurface,
  },

  // Badges
  badgeEmpty: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
  },
  badgeEmptyText: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 13,
    color: C.outline,
  },
  badgeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#e8f5e2',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  badgeChipEmoji: {
    fontSize: 14,
  },
  badgeChipLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: C.secondary,
  },

  // Badge detail modal
  badgeModalEmoji: {
    fontSize: 52,
    marginBottom: 12,
  },
  badgeModalName: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 20,
    color: C.onSurface,
    textAlign: 'center',
    marginBottom: 10,
  },
  badgeModalPointsPill: {
    backgroundColor: '#e8f5e2',
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 4,
    marginBottom: 16,
  },
  badgeModalPointsText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 13,
    color: C.secondary,
  },
  badgeModalDesc: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 14,
    color: C.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 21,
    marginBottom: 16,
  },
  badgeModalDate: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 12,
    color: C.outline,
    textAlign: 'center',
    lineHeight: 18,
  },

  // Modals
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: C.bg,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 28,
    paddingBottom: 40,
  },
  modalTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 18,
    color: C.onSurface,
    marginBottom: 20,
  },
  modalLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: C.onSurfaceVariant,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  modalInput: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 15,
    color: C.onSurface,
    borderWidth: 1,
    borderColor: C.outlineVariant,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 24,
  },
  modalBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBtnGhost: {
    backgroundColor: C.surfaceContainerLow,
    borderWidth: 1,
    borderColor: C.outlineVariant,
  },
  modalBtnText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15,
  },
});
