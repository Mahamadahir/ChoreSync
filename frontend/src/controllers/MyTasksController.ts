import { ref, readonly } from 'vue';
import { taskApi } from '../services/api';

export type MyTask = {
  id: number;
  template_name: string;
  group_id: string;
  group_name: string;
  status: string;
  deadline: string;
  points_earned: number;
  snooze_count: number;
  swap_id: number | null;
};

/** Class alias for test imports. Prefer `useMyTasksController` in components. */
export class MyTasksController {}

export function useMyTasksController() {
  const tasks = ref<MyTask[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load(params?: { status?: string; group_id?: string }) {
    loading.value = true;
    error.value = null;
    try {
      const res = await taskApi.myTasks(params);
      tasks.value = res.data;
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to load tasks.';
    } finally {
      loading.value = false;
    }
  }

  async function complete(taskId: number, photoProofUrl?: string) {
    try {
      await taskApi.complete(taskId, photoProofUrl ? { photo_proof_url: photoProofUrl } : {});
      await load();
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to complete task.';
      throw e;
    }
  }

  async function snooze(taskId: number, snoozeUntil: string) {
    try {
      await taskApi.snooze(taskId, { snooze_until: snoozeUntil });
      await load();
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to snooze task.';
      throw e;
    }
  }

  async function requestSwap(taskId: number, targetUserId: string, reason?: string) {
    try {
      await taskApi.createSwap(taskId, { to_user_id: targetUserId || undefined, reason });
      await load();
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to request swap.';
      throw e;
    }
  }

  async function respondSwap(swapId: number, action: 'accept' | 'reject') {
    try {
      await taskApi.respondSwap(swapId, action === 'accept');
      await load();
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Failed to respond to swap.';
      throw e;
    }
  }

  return {
    tasks: readonly(tasks),
    loading: readonly(loading),
    error: readonly(error),
    load,
    complete,
    snooze,
    requestSwap,
    respondSwap,
  };
}
