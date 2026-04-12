export type TaskStatus = 'suggested' | 'pending' | 'in_progress' | 'snoozed' | 'completed' | 'overdue' | 'reassigned';

export type RecurringChoice = 'none' | 'weekly' | 'monthly' | 'every_n_days' | 'custom';

export type TaskPreference = 'prefer' | 'neutral' | 'avoid';

export interface TaskOccurrence {
  id: number;
  template_id: number;
  template_name: string;
  group_id: string;
  group_name: string;
  assigned_to_id: string | null;
  assigned_to_username: string | null;
  deadline: string;
  status: TaskStatus;
  completed_at: string | null;
  points_earned: number | null;
  snooze_count: number;
  photo_proof_required: boolean;
  photo_proof: string | null;
  on_marketplace: boolean;
  marketplace_listing_id?: number | null;
  suggestion_expires_at?: string | null;
  reassignment_reason?: string | null;
  original_assignee_id?: string | null;
  // Template detail fields (from task detail endpoint)
  template_details?: string | null;
  estimated_mins?: number | null;
  difficulty?: number | null;
  assignee_first_name?: string | null;
  assignee_last_name?: string | null;
}

export interface TaskTemplate {
  id: number;
  name: string;
  details: string;
  group_id: string;
  recurring_choice: RecurringChoice;
  days_of_week: string[];
  recur_value: number | null;
  next_due: string;
  estimated_mins: number | null;
  difficulty: number;
  active: boolean;
  photo_proof_required: boolean;
  my_preference?: TaskPreference;
}

export interface TaskSwap {
  id: number;
  task_id: number;
  task_name: string;
  from_user_id: string;
  from_user_name: string;
  to_user_id: string | null;
  swap_type: 'direct_swap' | 'open_request';
  status: 'pending' | 'accepted' | 'rejected' | 'expired';
  reason: string;
  expires_at: string;
}
