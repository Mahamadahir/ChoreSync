export type NotificationType =
  | 'task_assigned'
  | 'task_swap'
  | 'emergency_reassignment'
  | 'deadline_reminder'
  | 'badge_earned'
  | 'marketplace_claim'
  | 'suggestion_pattern'
  | 'suggestion_availability'
  | 'suggestion_preference'
  | 'suggestion_streak'
  | 'calendar_sync_complete'
  | 'group_invite'
  | 'task_proposal'
  | 'message'
  // Legacy — declared in early schema but no longer emitted by the backend
  | 'task_suggestion';

export interface Notification {
  id: string | number;
  type: NotificationType;
  title: string;
  content: string;
  read: boolean;
  dismissed: boolean;
  action_url: string | null;
  task_occurrence_id: number | null;
  task_swap_id: number | null;
  task_proposal_id: number | null;
  message_id: number | null;
  group_id: string | null;
  created_at: string;
}
