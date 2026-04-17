import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text, View } from 'react-native';
import { Colors } from '../theme';
import { useNotificationStore } from '../stores/notificationStore';
import { usePushNotifications } from '../hooks/usePushNotifications';
import type {
  TabParamList,
  HomeStackParamList,
  TasksStackParamList,
  GroupsStackParamList,
  AssistantStackParamList,
  CalendarStackParamList,
  RootStackParamList,
} from './types';

// Screens
import HomeScreen from '../screens/home/HomeScreen';
import TasksScreen from '../screens/tasks/TasksScreen';
import TaskDetailScreen from '../screens/tasks/TaskDetailScreen';
import GroupsScreen from '../screens/groups/GroupsScreen';
import GroupDetailScreen from '../screens/groups/GroupDetailScreen';
import GroupSettingsScreen from '../screens/groups/GroupSettingsScreen';
import TaskTemplateDetailScreen from '../screens/groups/TaskTemplateDetailScreen';
import TaskAuthorScreen from '../screens/groups/TaskAuthorScreen';
import InviteMemberScreen from '../screens/groups/InviteMemberScreen';
import MarketplaceScreen from '../screens/groups/MarketplaceScreen';
import ProposalsScreen from '../screens/groups/ProposalsScreen';
import AssistantScreen from '../screens/assistant/AssistantScreen';
import CalendarScreen from '../screens/calendar/CalendarScreen';
import ProfileScreen from '../screens/profile/ProfileScreen';
import NotificationsScreen from '../screens/notifications/NotificationsScreen';
import NotificationPreferencesScreen from '../screens/notifications/NotificationPreferencesScreen';

// ── Per-tab stacks ───────────────────────────────────────────────────

const HomeStack = createNativeStackNavigator<HomeStackParamList>();
function HomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={{ headerShown: false }}>
      <HomeStack.Screen name="Home" component={HomeScreen} />
    </HomeStack.Navigator>
  );
}

const TasksStack = createNativeStackNavigator<TasksStackParamList>();
function TasksStackNavigator() {
  return (
    <TasksStack.Navigator screenOptions={{ headerShown: false }}>
      <TasksStack.Screen name="Tasks" component={TasksScreen} />
      <TasksStack.Screen name="TaskDetail" component={TaskDetailScreen} />
    </TasksStack.Navigator>
  );
}

const GroupsStack = createNativeStackNavigator<GroupsStackParamList>();
function GroupsStackNavigator() {
  return (
    <GroupsStack.Navigator screenOptions={{ headerShown: false }}>
      <GroupsStack.Screen name="Groups" component={GroupsScreen} />
      <GroupsStack.Screen name="GroupDetail" component={GroupDetailScreen} />
      <GroupsStack.Screen name="GroupSettings" component={GroupSettingsScreen} />
      <GroupsStack.Screen name="TaskTemplateDetail" component={TaskTemplateDetailScreen} />
      <GroupsStack.Screen name="TaskAuthor" component={TaskAuthorScreen} />
      <GroupsStack.Screen name="InviteMember" component={InviteMemberScreen} />
      <GroupsStack.Screen name="Marketplace" component={MarketplaceScreen} />
      <GroupsStack.Screen name="Proposals" component={ProposalsScreen} />
    </GroupsStack.Navigator>
  );
}

const AssistantStack = createNativeStackNavigator<AssistantStackParamList>();
function AssistantStackNavigator() {
  return (
    <AssistantStack.Navigator screenOptions={{ headerShown: false }}>
      <AssistantStack.Screen name="Assistant" component={AssistantScreen} />
    </AssistantStack.Navigator>
  );
}

const CalendarStack = createNativeStackNavigator<CalendarStackParamList>();
function CalendarStackNavigator() {
  return (
    <CalendarStack.Navigator screenOptions={{ headerShown: false }}>
      <CalendarStack.Screen name="CalendarMain" component={CalendarScreen} />
    </CalendarStack.Navigator>
  );
}

// ── Tab icon helper ──────────────────────────────────────────────────

function TabIcon({
  icon,
  label,
  focused,
  badge = 0,
}: {
  icon: string;
  label: string;
  focused: boolean;
  badge?: number;
}) {
  return (
    <View style={{ alignItems: 'center', paddingTop: 4 }}>
      <View>
        <Text
          style={{
            fontFamily: 'MaterialSymbols',
            fontSize: 24,
            color: focused ? Colors.brandPrimary : Colors.stone500,
          }}
        >
          {icon}
        </Text>
        {badge > 0 && (
          <View
            style={{
              position: 'absolute',
              top: -4,
              right: -9,
              backgroundColor: Colors.brandPrimary,
              borderRadius: 8,
              minWidth: 16,
              height: 16,
              paddingHorizontal: 3,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Text
              style={{
                color: '#ffffff',
                fontSize: 9,
                fontFamily: 'PlusJakartaSans-Bold',
                lineHeight: 14,
              }}
            >
              {badge > 99 ? '99+' : badge}
            </Text>
          </View>
        )}
      </View>
      <Text
        style={{
          fontFamily: 'PlusJakartaSans-SemiBold',
          fontSize: 9,
          letterSpacing: 0.8,
          textTransform: 'uppercase',
          color: focused ? Colors.brandPrimary : Colors.stone500,
          marginTop: 2,
        }}
      >
        {label}
      </Text>
    </View>
  );
}

// Notification types that belong on the Tasks tab badge
const TASK_NOTIF_TYPES = new Set([
  'task_assigned', 'deadline_reminder', 'emergency_reassignment',
  'marketplace_claim', 'suggestion_pattern', 'suggestion_availability',
  'suggestion_preference', 'suggestion_streak', 'badge_earned',
]);
// Notification types that belong on the Groups tab badge
const GROUP_NOTIF_TYPES = new Set([
  'message', 'group_invite', 'task_proposal', 'task_swap',
]);

// ── Root stack: tabs + modal screens (Profile / Notifications) ────────

const RootStack = createNativeStackNavigator<RootStackParamList>();

// ── Bottom tab navigator ─────────────────────────────────────────────

function TabNavigator() {
  usePushNotifications();
  const notifications = useNotificationStore((s) => s.notifications);

  const taskBadge = notifications.filter(
    (n) => !n.read && !n.dismissed && TASK_NOTIF_TYPES.has(n.type)
  ).length;

  const groupBadge = notifications.filter(
    (n) => !n.read && !n.dismissed && GROUP_NOTIF_TYPES.has(n.type)
  ).length;

  const Tab = createBottomTabNavigator<TabParamList>();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          backgroundColor: Colors.navBackground,
          borderTopColor: Colors.navBorder,
          borderTopWidth: 1,
          height: 80,
          paddingBottom: 16,
        },
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeStackNavigator}
        options={{ tabBarIcon: ({ focused }) => <TabIcon icon="home" label="Home" focused={focused} /> }}
      />
      <Tab.Screen
        name="TasksTab"
        component={TasksStackNavigator}
        options={{ tabBarIcon: ({ focused }) => <TabIcon icon="checklist" label="Tasks" focused={focused} badge={taskBadge} /> }}
      />
      <Tab.Screen
        name="GroupsTab"
        component={GroupsStackNavigator}
        options={{ tabBarIcon: ({ focused }) => <TabIcon icon="group" label="Groups" focused={focused} badge={groupBadge} /> }}
      />
      <Tab.Screen
        name="AssistantTab"
        component={AssistantStackNavigator}
        options={{ tabBarIcon: ({ focused }) => <TabIcon icon="smart_toy" label="Assistant" focused={focused} /> }}
      />
      <Tab.Screen
        name="CalendarTab"
        component={CalendarStackNavigator}
        options={{ tabBarIcon: ({ focused }) => <TabIcon icon="calendar_month" label="Calendar" focused={focused} /> }}
      />
    </Tab.Navigator>
  );
}

// ── Main export: root stack wrapping tabs + modal overlays ───────────

export default function MainTabNavigator() {
  return (
    <RootStack.Navigator screenOptions={{ headerShown: false }}>
      <RootStack.Screen name="Tabs" component={TabNavigator} />
      <RootStack.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ presentation: 'modal' }}
      />
      <RootStack.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{ presentation: 'modal' }}
      />
      <RootStack.Screen
        name="NotificationPreferences"
        component={NotificationPreferencesScreen}
        options={{ presentation: 'modal' }}
      />
    </RootStack.Navigator>
  );
}
