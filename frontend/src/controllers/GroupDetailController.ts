import { ref, readonly } from 'vue';
import { groupApi, taskApi } from '../services/api';

export type GroupDetail = {
  id: string;
  name: string;
  group_code: string;
  role: string;
  fairness_algorithm: string;
  reassignment_rule: string;
  photo_proof_required: boolean;
  task_proposal_voting_required: boolean;
};

export type GroupMember = {
  user_id: string;
  username: string;
  email: string;
  role: string;
  joined_at: string;
  stats: {
    total_tasks_completed: number;
    total_points: number;
    tasks_completed_this_week: number;
    on_time_completion_rate: number;
    current_streak_days: number;
  } | null;
};

export type TaskOccurrence = {
  id: number;
  template_name: string;
  status: string;
  deadline: string;
  assigned_to_id: string;
  points_earned: number;
  snooze_count: number;
};

/** Class alias for test imports. Prefer `useGroupDetailController` in components. */
export class GroupDetailController {
  constructor(public groupId: string) {}
}

export function useGroupDetailController(groupId: string) {
  const group = ref<GroupDetail | null>(null);
  const members = ref<GroupMember[]>([]);
  const tasks = ref<TaskOccurrence[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      const [groupRes, membersRes, tasksRes] = await Promise.all([
        groupApi.get(groupId),
        groupApi.members(groupId),
        taskApi.groupTasks(groupId),
      ]);
      group.value = groupRes.data;
      members.value = membersRes.data;
      tasks.value = tasksRes.data;
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to load group.';
    } finally {
      loading.value = false;
    }
  }

  async function refreshTasks() {
    try {
      const res = await taskApi.groupTasks(groupId);
      tasks.value = res.data;
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to refresh tasks.';
    }
  }

  return {
    group: readonly(group),
    members: readonly(members),
    tasks: readonly(tasks),
    loading: readonly(loading),
    error: readonly(error),
    load,
    refreshTasks,
  };
}
