import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { View, ActivityIndicator } from 'react-native';
import { useAuthStore } from '../stores/authStore';
import { useNotificationStore } from '../stores/notificationStore';
import { socketService } from '../services/MobileSocketService';
import { Colors } from '../theme';
import AuthNavigator from './AuthNavigator';
import MainTabNavigator from './MainTabNavigator';

export default function AppNavigator() {
  const { isAuthenticated, isBootstrapping, bootstrap } = useAuthStore();
  const { prependNotification } = useNotificationStore();

  useEffect(() => {
    bootstrap();
  }, []);

  // Connect / disconnect the global socket when auth state changes.
  useEffect(() => {
    if (isAuthenticated) {
      socketService.connect();
      const unsub = socketService.onNotification((n) => {
        prependNotification({
          id: n.id,
          type: n.type as any,
          title: n.title,
          content: n.content,
          read: n.read,
          dismissed: n.dismissed,
          created_at: n.created_at,
          group_id: n.group_id,
          task_occurrence_id: n.task_occurrence_id,
          task_swap_id: n.task_swap_id,
          task_proposal_id: n.task_proposal_id,
          message_id: n.message_id,
          action_url: n.action_url,
        });
      });
      return () => {
        unsub();
        socketService.disconnect();
      };
    }
  }, [isAuthenticated]);

  if (isBootstrapping) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.warmCream }}>
        <ActivityIndicator size="large" color={Colors.brandPrimary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <MainTabNavigator /> : <AuthNavigator />}
    </NavigationContainer>
  );
}
