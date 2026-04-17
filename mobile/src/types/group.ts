export type GroupRole = 'moderator' | 'member';

export interface Group {
  id: string;
  name: string;
  member_count: number;
  open_task_count: number;
  my_role: GroupRole;
  reassignment_rule: string;
  group_type: 'flatshare' | 'family' | 'work_team' | 'custom';
}

export interface GroupMember {
  user_id: string;
  username: string;
  first_name: string;
  last_name: string;
  role: GroupRole;
  email: string;
}

export interface LeaderboardEntry {
  user_id: string;
  username: string;
  first_name: string;
  last_name: string;
  total_tasks_completed: number;
  total_points: number;
  streak: number;
  badges: Badge[];
}

export interface Badge {
  id: number;
  name: string;
  icon: string;
  description: string;
  earned_at: string;
}

export interface Message {
  id: number;
  sender_id: string;
  sender_name: string;
  content: string;
  created_at: string;
}

export interface Proposal {
  id: number;
  task_template_id: number;
  task_template_name: string;
  reason: string;
  status: 'open' | 'approved' | 'rejected';
  created_at: string;
}
