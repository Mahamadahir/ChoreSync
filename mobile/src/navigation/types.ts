import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';

// ── Auth stack ───────────────────────────────────────────────────────
export type AuthStackParamList = {
  Login: undefined;
  SignUp: undefined;
  VerifyEmail: { email: string };
  ForgotPassword: undefined;
  ResetPassword: { token: string };
};

// ── Home tab stack ───────────────────────────────────────────────────
export type HomeStackParamList = {
  Home: undefined;
};

// ── Tasks tab stack ──────────────────────────────────────────────────
export type TasksStackParamList = {
  Tasks: undefined;
  TaskDetail: { taskId: number };
};

// ── Groups tab stack ─────────────────────────────────────────────────
export type GroupsStackParamList = {
  Groups: undefined;
  GroupDetail: { groupId: string; initialTab?: string };
  GroupSettings: { groupId: string };
  TaskTemplateDetail: { templateId: number; groupId: string };
  TaskAuthor: { groupId: string; templateId?: number };
  InviteMember: { groupId: string; groupType?: string };
  Marketplace: { groupId: string };
  Proposals: { groupId: string; myRole?: string };
  Invitation: { invitationId: number };
  AssignmentHistory: { groupId: string; groupName?: string };
};

// ── Assistant tab stack ──────────────────────────────────────────────
export type AssistantStackParamList = {
  Assistant: undefined;
};

// ── Profile stack (modal, not a tab) ────────────────────────────────
export type ProfileStackParamList = {
  Profile: undefined;
  NotificationPreferences: undefined;
};

// ── Calendar tab stack ───────────────────────────────────────────────
export type CalendarStackParamList = {
  CalendarMain: undefined;
};

// ── Root stack (tabs + modal overlays) ──────────────────────────────
export type RootStackParamList = {
  Tabs: undefined;
  Profile: undefined;
  Notifications: undefined;
  NotificationPreferences: undefined;
};

// ── Bottom tab bar ───────────────────────────────────────────────────
export type TabParamList = {
  HomeTab: undefined;
  TasksTab: undefined;
  GroupsTab: undefined;
  AssistantTab: undefined;
  CalendarTab: undefined;
};

// Screen prop helpers
export type LoginScreenProps = NativeStackScreenProps<AuthStackParamList, 'Login'>;
export type SignUpScreenProps = NativeStackScreenProps<AuthStackParamList, 'SignUp'>;
export type VerifyEmailScreenProps = NativeStackScreenProps<AuthStackParamList, 'VerifyEmail'>;
export type ForgotPasswordScreenProps = NativeStackScreenProps<AuthStackParamList, 'ForgotPassword'>;
export type ResetPasswordScreenProps = NativeStackScreenProps<AuthStackParamList, 'ResetPassword'>;

export type HomeScreenProps = NativeStackScreenProps<HomeStackParamList, 'Home'>;
export type TasksScreenProps = NativeStackScreenProps<TasksStackParamList, 'Tasks'>;
export type TaskDetailScreenProps = NativeStackScreenProps<TasksStackParamList, 'TaskDetail'>;
export type GroupsScreenProps = NativeStackScreenProps<GroupsStackParamList, 'Groups'>;
export type GroupDetailScreenProps = NativeStackScreenProps<GroupsStackParamList, 'GroupDetail'>;
export type GroupSettingsScreenProps = NativeStackScreenProps<GroupsStackParamList, 'GroupSettings'>;
export type TaskTemplateDetailScreenProps = NativeStackScreenProps<GroupsStackParamList, 'TaskTemplateDetail'>;
export type TaskAuthorScreenProps = NativeStackScreenProps<GroupsStackParamList, 'TaskAuthor'>;
export type InviteMemberScreenProps = NativeStackScreenProps<GroupsStackParamList, 'InviteMember'>;
export type MarketplaceScreenProps = NativeStackScreenProps<GroupsStackParamList, 'Marketplace'>;
export type ProposalsScreenProps = NativeStackScreenProps<GroupsStackParamList, 'Proposals'>;
export type AssistantScreenProps = NativeStackScreenProps<AssistantStackParamList, 'Assistant'>;
export type ProfileScreenProps = NativeStackScreenProps<ProfileStackParamList, 'Profile'>;
export type CalendarScreenProps = NativeStackScreenProps<CalendarStackParamList, 'CalendarMain'>;
