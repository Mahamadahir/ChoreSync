<template>
  <Teleport to="body">
    <Transition name="popup">
      <div v-if="visible && current" class="sp-backdrop" @click.self="dismiss">
        <div class="sp-sheet" role="dialog" aria-modal="true">

          <!-- Streak icon -->
          <div class="sp-icon-wrap">
            <span class="material-symbols-outlined sp-icon">autorenew</span>
          </div>

          <!-- Text -->
          <div class="sp-title">Your usual task is ready</div>
          <div class="sp-task-name">{{ current.taskName }}</div>
          <div class="sp-body">
            You've done this <strong>{{ current.streakLength }} times in a row</strong>.
            Want it assigned to you again?
          </div>

          <!-- Deadline + window -->
          <div class="sp-meta">
            <span class="sp-meta-item">
              <span class="material-symbols-outlined" style="font-size:14px">event</span>
              Due {{ formatDate(current.deadline) }}
            </span>
            <span class="sp-meta-sep">·</span>
            <span class="sp-meta-item">
              <span class="material-symbols-outlined" style="font-size:14px">timer</span>
              {{ windowLabel }} to respond
            </span>
          </div>

          <!-- Actions -->
          <div class="sp-actions">
            <button class="sp-btn sp-btn--decline" :disabled="acting" @click="decline">
              No thanks
            </button>
            <button class="sp-btn sp-btn--accept" :disabled="acting" @click="accept">
              <span v-if="acting" class="sp-spinner" />
              <template v-else>
                <span class="material-symbols-outlined" style="font-size:16px;font-variation-settings:'FILL' 1">check_circle</span>
                Yes, assign me
              </template>
            </button>
          </div>

          <!-- Queue indicator -->
          <div v-if="queue.length > 1" class="sp-queue-hint">
            +{{ queue.length - 1 }} more suggestion{{ queue.length > 2 ? 's' : '' }}
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { taskApi } from '../services/api';

interface StreakSuggestion {
  occurrenceId: number;
  taskName: string;
  deadline: string;       // ISO
  streakLength: number;
  windowMinutes: number;  // from notification content or default
}

// ── Queue: multiple streak suggestions can arrive in quick succession ──
const queue = ref<StreakSuggestion[]>([]);
const acting = ref(false);

const visible = computed(() => queue.value.length > 0);
const current = computed(() => queue.value[0] ?? null);

const windowLabel = computed(() => {
  if (!current.value) return '';
  const h = current.value.windowMinutes / 60;
  if (h < 1) return `${current.value.windowMinutes}m`;
  const rounded = Math.round(h * 10) / 10;
  return `${rounded}h`;
});

// ── Public API — called from App.vue when a suggestion_streak notification arrives ──
function push(suggestion: StreakSuggestion) {
  // Don't duplicate
  if (queue.value.some(s => s.occurrenceId === suggestion.occurrenceId)) return;
  queue.value.push(suggestion);
}

function dismiss() {
  queue.value.shift();
}

async function accept() {
  if (!current.value || acting.value) return;
  acting.value = true;
  try {
    await taskApi.acceptSuggestion(current.value.occurrenceId);
    queue.value.shift();
  } catch {
    // If already resolved (auto-assigned), just dismiss
    queue.value.shift();
  } finally {
    acting.value = false;
  }
}

async function decline() {
  if (!current.value || acting.value) return;
  acting.value = true;
  try {
    await taskApi.declineSuggestion(current.value.occurrenceId);
  } catch {
    // Auto-assigned already — no action needed
  } finally {
    queue.value.shift();
    acting.value = false;
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}

// ── Parse a raw notification into a StreakSuggestion ──────────────────
function parseNotification(n: any): StreakSuggestion | null {
  if (n.type !== 'suggestion_streak') return null;
  const occurrenceId = n.task_occurrence_id ?? n.occurrence_id;
  if (!occurrenceId) return null;

  // Extract streak length from content e.g. "…the last 3 times…"
  const streakMatch = n.content?.match(/last (\d+) times/);
  const streakLength = streakMatch ? parseInt(streakMatch[1]) : 3;

  // Extract window from content e.g. "Respond within 16.0h…"
  const windowMatch = n.content?.match(/within ([\d.]+)h/);
  const windowMinutes = windowMatch ? Math.round(parseFloat(windowMatch[1]) * 60) : 480;

  return {
    occurrenceId,
    taskName: n.title?.replace("Your usual task is ready: ", "") ?? 'Task',
    deadline: n.deadline ?? new Date(Date.now() + 86400000 * 2).toISOString(),
    streakLength,
    windowMinutes,
  };
}

defineExpose({ push, parseNotification });
</script>

<style scoped>
/* ── Backdrop ───────────────────────────────────────────────── */
.sp-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(27, 28, 26, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0 0 env(safe-area-inset-bottom, 0);
}

/* ── Sheet ──────────────────────────────────────────────────── */
.sp-sheet {
  width: 100%;
  max-width: 480px;
  background: var(--cs-surface-container-lowest, #ffffff);
  border-radius: 28px 28px 0 0;
  padding: 28px 28px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;
  box-shadow: 0 -8px 40px rgba(27,28,26,0.12);
}

/* ── Icon ───────────────────────────────────────────────────── */
.sp-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: var(--cs-primary-fixed, #ffdad5);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}
.sp-icon {
  font-size: 28px;
  color: var(--cs-primary, #94433a);
  font-variation-settings: 'FILL' 1;
}

/* ── Text ───────────────────────────────────────────────────── */
.sp-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--cs-on-surface-variant, #554240);
  margin-bottom: -4px;
}
.sp-task-name {
  font-size: 22px;
  font-weight: 800;
  color: var(--cs-on-surface, #1b1c1a);
  letter-spacing: -0.3px;
  line-height: 1.2;
}
.sp-body {
  font-size: 14px;
  color: var(--cs-on-surface-variant, #554240);
  line-height: 1.5;
  max-width: 300px;
}

/* ── Meta row ───────────────────────────────────────────────── */
.sp-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--cs-on-surface-variant, #554240);
  background: var(--cs-surface-container, #efeeea);
  padding: 6px 14px;
  border-radius: 999px;
  margin: 2px 0 6px;
}
.sp-meta-item {
  display: flex;
  align-items: center;
  gap: 3px;
}
.sp-meta-sep { opacity: 0.4; }

/* ── Actions ────────────────────────────────────────────────── */
.sp-actions {
  display: flex;
  gap: 10px;
  width: 100%;
  margin-top: 4px;
}
.sp-btn {
  flex: 1;
  height: 48px;
  border-radius: 14px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: opacity 0.15s, transform 0.1s;
}
.sp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sp-btn:not(:disabled):active { transform: scale(0.97); }

.sp-btn--decline {
  background: var(--cs-surface-container, #efeeea);
  color: var(--cs-on-surface-variant, #554240);
}
.sp-btn--decline:not(:disabled):hover {
  background: var(--cs-surface-container-high, #eae8e4);
}
.sp-btn--accept {
  background: linear-gradient(135deg, #94433a, #b35b50);
  color: #fff;
  box-shadow: 0 4px 16px rgba(148, 67, 58, 0.28);
}
.sp-btn--accept:not(:disabled):hover { opacity: 0.9; }

.sp-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Queue hint ─────────────────────────────────────────────── */
.sp-queue-hint {
  font-size: 12px;
  color: var(--cs-on-surface-variant, #554240);
  opacity: 0.55;
  margin-top: -4px;
}

/* ── Transition ─────────────────────────────────────────────── */
.popup-enter-active { transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s; }
.popup-leave-active { transition: transform 0.2s ease-in, opacity 0.15s; }
.popup-enter-from  { transform: translateY(100%); opacity: 0; }
.popup-leave-to    { transform: translateY(100%); opacity: 0; }
</style>
