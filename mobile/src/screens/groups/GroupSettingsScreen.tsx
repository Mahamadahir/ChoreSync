import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
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
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import { groupService } from '../../services/groupService';
import { useAuthStore } from '../../stores/authStore';
import type { Group } from '../../types/group';
import type { GroupSettingsScreenProps } from '../../navigation/types';
import { Palette as C } from '../../theme';

// ── Section header ─────────────────────────────────────────────
function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <View style={styles.sectionHeaderWrap}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionSub}>{subtitle}</Text>
    </View>
  );
}

// ── Toggle row ─────────────────────────────────────────────────
function ToggleRow({
  label,
  sub,
  value,
  onToggle,
}: {
  label: string;
  sub: string;
  value: boolean;
  onToggle: (v: boolean) => void;
}) {
  return (
    <View style={styles.toggleRow}>
      <View style={styles.toggleText}>
        <Text style={styles.toggleLabel}>{label}</Text>
        <Text style={styles.toggleSub}>{sub}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ false: C.surfaceContainerHighest, true: C.secondary }}
        thumbColor={C.white}
        ios_backgroundColor={C.surfaceContainerHighest}
      />
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────
export default function GroupSettingsScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const route = useRoute<GroupSettingsScreenProps['route']>();
  const { groupId } = route.params;
  const user = useAuthStore((s) => s.user);

  const [group, setGroup] = useState<Group | null>(null);
  const [groupName, setGroupName] = useState('');
  const [photoProof, setPhotoProof] = useState(false);
  const [taskVoting, setTaskVoting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await groupService.get(groupId);
      const g: Group = res.data;
      setGroup(g);
      setGroupName(g.name);
      setPhotoProof(g.photo_proof_required ?? false);
      setTaskVoting((g as any).task_proposal_voting_required ?? false);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not load group settings.');
    }
  }, [groupId]);

  useEffect(() => { load(); }, [load]);

  async function handleSave() {
    const trimmed = groupName.trim();
    if (!trimmed) {
      Alert.alert('Validation', 'Group name cannot be empty.');
      return;
    }
    setSaving(true);
    try {
      await groupService.settings(groupId, {
        name: trimmed,
        photo_proof_required: photoProof,
        task_proposal_voting_required: taskVoting,
      });
      Alert.alert('Saved', 'Group settings updated.');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not save settings.');
    } finally {
      setSaving(false);
    }
  }

  function handleLeaveGroup() {
    Alert.alert(
      'Leave Group',
      `Leave "${group?.name ?? 'this group'}"? You will lose access to all tasks and history in this group.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Leave',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            try {
              await groupService.leave(groupId);
              navigation.popToTop();
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not leave group.');
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  }

  return (
    <KeyboardAvoidingView
      style={[styles.root, { paddingTop: insets.top }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <StatusBar barStyle="dark-content" backgroundColor={C.bg} />

      {/* ── Top App Bar ─────────────────────────── */}
      <View style={styles.topBar}>
        <View style={styles.topBarLeft}>
          <TouchableOpacity activeOpacity={0.7} onPress={() => navigation.goBack()} style={styles.topBarBtn}>
            <Text style={[styles.msIcon, { color: C.stone500 }]}>arrow_back</Text>
          </TouchableOpacity>
          <Text style={styles.topBarTitle}>Group Settings</Text>
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

        {/* ── GROUP IDENTITY ──────────────────────── */}
        <View style={styles.section}>
          <SectionHeader
            title="Group Identity"
            subtitle="Define how your homestead appears to others."
          />
          <View style={styles.card}>
            <Text style={styles.inputLabel}>GROUP NAME</Text>
            <TextInput
              style={styles.textInput}
              value={groupName}
              onChangeText={setGroupName}
              placeholder="Enter group name"
              placeholderTextColor={C.stone500}
              returnKeyType="done"
            />
            <TouchableOpacity
              activeOpacity={saving ? 1 : 0.85}
              onPress={handleSave}
              disabled={saving}
              style={{ borderRadius: 12, overflow: 'hidden', marginTop: 8 }}
            >
              <LinearGradient
                colors={saving ? [C.surfaceContainerHigh, C.surfaceContainerHigh] : [C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={styles.saveBtn}
              >
                <Text style={[styles.saveBtnText, saving && { color: C.onSurfaceVariant }]}>
                  {saving ? 'Saving…' : 'Save Changes'}
                </Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>

        {/* ── TASK RULES ──────────────────────────── */}
        <View style={styles.section}>
          <SectionHeader
            title="Task Rules"
            subtitle="Automate accountability within your group."
          />
          <View style={styles.togglesCard}>
            <ToggleRow
              label="Require Photo Proof"
              sub="Members must upload a photo to complete tasks"
              value={photoProof}
              onToggle={setPhotoProof}
            />
            <View style={styles.toggleDivider} />
            <ToggleRow
              label="Moderator Approval Required"
              sub="Members can only suggest tasks — moderators approve before they go live"
              value={taskVoting}
              onToggle={setTaskVoting}
            />
          </View>
        </View>

        {/* ── DANGER ZONE ─────────────────────────── */}
        <View style={[styles.section, { marginBottom: 0 }]}>
          <View style={styles.dangerHeader}>
            <Text style={[styles.msIcon, { color: C.error, fontSize: 22 }]}>warning</Text>
            <Text style={styles.dangerTitle}>Danger Zone</Text>
          </View>
          <View style={styles.dangerCard}>
            <Text style={styles.dangerItemTitle}>Leave Group</Text>
            <Text style={styles.dangerItemSub}>
              You will lose access to all tasks and history in this group. A moderator can re-invite you later.
            </Text>
            <TouchableOpacity
              activeOpacity={deleting ? 1 : 0.85}
              onPress={handleLeaveGroup}
              disabled={deleting}
              style={styles.deleteBtn}
            >
              <Text style={[styles.msIcon, { color: C.error, fontSize: 18 }]}>logout</Text>
              <Text style={styles.deleteBtnText}>{deleting ? 'Leaving…' : 'Leave Group'}</Text>
            </TouchableOpacity>
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
  topBarLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
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

  // Section wrapper
  section: { marginBottom: 36 },
  sectionHeaderWrap: { marginBottom: 16, gap: 3 },
  sectionTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.onSurface, letterSpacing: -0.3,
  },
  sectionSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13, color: C.onSurfaceVariant,
  },

  // Identity card
  card: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 20, padding: 24, gap: 14,
  },
  inputLabel: {
    fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 10,
    color: C.onSurfaceVariant, letterSpacing: 2, textTransform: 'uppercase',
    marginBottom: -4,
  },
  textInput: {
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 14, paddingHorizontal: 18, paddingVertical: 16,
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 15, color: C.onSurface,
  },
  saveBtn: {
    paddingVertical: 18, borderRadius: 12, alignItems: 'center', justifyContent: 'center',
  },
  saveBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.white,
  },

  // Toggles
  togglesCard: {
    backgroundColor: C.surfaceContainerLow,
    borderRadius: 20, overflow: 'hidden',
  },
  toggleRow: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 22, paddingVertical: 20, gap: 16,
  },
  toggleText: { flex: 1, gap: 3 },
  toggleLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold', fontSize: 14, color: C.onSurface,
  },
  toggleSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 12, color: C.onSurfaceVariant,
  },
  toggleDivider: {
    height: StyleSheet.hairlineWidth, backgroundColor: C.outlineVariant,
    marginHorizontal: 22,
  },

  // Danger zone
  dangerHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16,
  },
  dangerTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 20, color: C.error,
  },
  dangerCard: {
    backgroundColor: `${C.errorContainer}4d`,
    borderWidth: StyleSheet.hairlineWidth, borderColor: `${C.error}1a`,
    borderRadius: 20, padding: 24, gap: 14,
  },
  dangerItemTitle: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.onSurface,
  },
  dangerItemSub: {
    fontFamily: 'PlusJakartaSans-Regular', fontSize: 13,
    color: C.onSurfaceVariant, lineHeight: 20,
  },
  deleteBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 18, borderRadius: 14,
    borderWidth: 2, borderColor: C.error,
    marginTop: 4,
  },
  deleteBtnText: {
    fontFamily: 'PlusJakartaSans-Bold', fontSize: 15, color: C.error,
  },

  // Shared
  msIcon: { fontFamily: 'MaterialSymbols', fontSize: 24, color: C.onSurface },
});
