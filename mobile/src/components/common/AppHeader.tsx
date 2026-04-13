import React, { useEffect } from 'react';
import { Image, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';
import { notificationService } from '../../services/notificationService';
import { tokenStorage } from '../../services/tokenStorage';
import type { Notification } from '../../types/notification';
import { Palette as C } from '../../theme';

interface Props {
  /** Optional extra element placed between the title and the right icons (e.g. a "Clear" button). */
  centerExtra?: React.ReactNode;
}

/**
 * Shared top app bar used by every root tab screen.
 *
 * Left:   ChoreSync wordmark
 * Right:  notification bell (with unread dot) → NotificationPreferences modal
 *         avatar circle (photo or initials)   → Profile modal
 */
export default function AppHeader({ centerExtra }: Props) {
  const navigation = useNavigation<any>();
  const user = useAuthStore((s) => s.user);
  const { setNotifications, notifications } = useNotificationStore();
  const unread = notifications.filter((n) => !n.read && !n.dismissed).length;

  // Bootstrap notification badge on initial mount so the count is never stale
  // at app launch. The useAppForegroundRefresh hook on HomeScreen handles
  // subsequent foreground transitions.
  useEffect(() => {
    notificationService
      .list()
      .then((res) => {
        const data: Notification[] = Array.isArray(res.data)
          ? res.data
          : (res.data?.results ?? []);
        setNotifications(data);
        if (data.length > 0) {
          const maxId = String(Math.max(...data.map((n) => Number(n.id))));
          tokenStorage.saveLastNotifId(maxId);
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initial = (user?.first_name?.[0] ?? user?.username?.[0] ?? 'U').toUpperCase();

  return (
    <View style={styles.bar}>
      {/* Left: logo */}
      <Text style={styles.title}>ChoreSync</Text>

      {/* Centre slot: optional */}
      {centerExtra ?? <View style={styles.flex} />}

      {/* Right: bell + avatar */}
      <View style={styles.right}>
        {/* Notification bell */}
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.btn}
          onPress={() => navigation.navigate('Notifications')}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={[styles.icon, { color: C.stone500 }]}>notifications</Text>
          {unread > 0 && <View style={styles.dot} />}
        </TouchableOpacity>

        {/* Avatar → Profile */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => navigation.navigate('Profile')}
          style={styles.avatar}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          {user?.avatar_url ? (
            <Image source={{ uri: user.avatar_url }} style={styles.avatarImg} resizeMode="cover" />
          ) : (
            <Text style={styles.avatarText}>{initial}</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    backgroundColor: C.bg,
    gap: 8,
  },
  title: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22,
    color: C.primary,
    letterSpacing: -0.5,
  },
  flex: { flex: 1 },
  right: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  btn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
  },
  dot: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.error,
    borderWidth: 1.5,
    borderColor: C.bg,
  },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: C.surfaceContainerHighest,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: C.surfaceContainerHigh,
    overflow: 'hidden',
  },
  avatarImg: {
    width: 38,
    height: 38,
    borderRadius: 19,
  },
  avatarText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 15,
    color: C.onSurfaceVariant,
  },
});
