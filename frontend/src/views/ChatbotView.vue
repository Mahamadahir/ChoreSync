<template>
  <div class="chatbot-layout">

    <!-- Sessions sidebar -->
    <div :class="['chatbot-sidebar', { 'chatbot-sidebar--open': sidebarOpen }]">
      <div class="chatbot-sidebar-header">
        <span style="font-weight:700;font-size:14px">Chats</span>
        <button class="cs-btn-ghost icon-btn" title="Close" @click="sidebarOpen = false">
          <span class="material-symbols-outlined" style="font-size:18px">close</span>
        </button>
      </div>

      <button class="chatbot-new-btn" @click="startNewChat">
        <span class="material-symbols-outlined" style="font-size:16px">add</span>
        New chat
      </button>

      <div class="chatbot-session-list">
        <div v-if="sessions.length === 0" class="chatbot-session-empty">No previous chats</div>
        <button
          v-for="s in sessions"
          :key="s.id"
          :class="['chatbot-session-item', { 'chatbot-session-item--active': s.id === sessionId }]"
          @click="loadSession(s.id)"
        >
          <div class="chatbot-session-preview">{{ s.preview || 'Empty chat' }}</div>
          <div class="chatbot-session-meta">{{ formatDate(s.last_active) }} · {{ s.message_count }} msgs</div>
        </button>
      </div>
    </div>

    <!-- Main chat area -->
    <div class="chatbot-main">

      <!-- Header -->
      <div class="chatbot-header">
        <div style="display:flex;align-items:center;gap:10px">
          <button class="cs-btn-ghost icon-btn" title="Chat history" @click="sidebarOpen = !sidebarOpen">
            <span class="material-symbols-outlined" style="font-size:20px">history</span>
          </button>
          <div>
            <div class="cs-page-title" style="margin-bottom:2px">AI Assistant</div>
            <div style="font-size:13px;color:var(--cs-muted)">Ask me to create tasks, check stats, swap tasks, and more</div>
          </div>
        </div>
        <button
          class="cs-btn-outline"
          style="font-size:12px;padding:6px 14px;display:flex;align-items:center;gap:6px"
          @click="startNewChat"
          title="New chat"
        >
          <span class="material-symbols-outlined" style="font-size:16px">add</span>
          New chat
        </button>
      </div>

      <!-- Message list -->
      <div class="chatbot-messages" ref="scrollEl">
        <!-- Empty state -->
        <div v-if="messages.length === 0" class="chatbot-empty">
          <span class="material-symbols-outlined chatbot-empty-icon">smart_toy</span>
          <div class="chatbot-empty-title">What can I help with?</div>
          <div class="chatbot-empty-sub">Try one of these:</div>
          <div class="chatbot-suggestions">
            <button
              v-for="s in examplePrompts"
              :key="s"
              class="chatbot-suggestion-chip"
              @click="sendMessage(s)"
            >{{ s }}</button>
          </div>
        </div>

        <!-- Messages -->
        <template v-else>
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['chatbot-msg', msg.role === 'user' ? 'chatbot-msg--user' : 'chatbot-msg--bot']"
          >
            <div v-if="msg.role === 'bot'" class="chatbot-avatar">
              <span class="material-symbols-outlined" style="font-size:18px;font-variation-settings:'FILL' 1">smart_toy</span>
            </div>
            <div class="chatbot-msg-body">
              <div class="chatbot-bubble" v-html="renderMarkdown(msg.content)" />
              <div v-if="msg.chips && msg.chips.length" class="chatbot-chips">
                <button
                  v-for="chip in msg.chips"
                  :key="chip"
                  :class="['chatbot-chip', chip === 'None' && 'chatbot-chip--none']"
                  :disabled="loading"
                  @click="sendMessage(chip)"
                >
                  <span class="material-symbols-outlined chatbot-chip-icon">
                    {{ chip === 'None' ? 'cancel' : 'apartment' }}
                  </span>
                  {{ chip }}
                </button>
              </div>
            </div>
            <div v-if="msg.role === 'user'" class="chatbot-avatar chatbot-avatar--user">
              {{ userInitials }}
            </div>
          </div>

          <!-- Typing indicator -->
          <div v-if="loading" class="chatbot-msg chatbot-msg--bot">
            <div class="chatbot-avatar">
              <span class="material-symbols-outlined" style="font-size:18px;font-variation-settings:'FILL' 1">smart_toy</span>
            </div>
            <div class="chatbot-bubble chatbot-bubble--typing">
              <span class="dot" /><span class="dot" /><span class="dot" />
            </div>
          </div>
        </template>
      </div>

      <!-- Pending action banner -->
      <div v-if="pendingAction" class="chatbot-pending-banner">
        <span class="material-symbols-outlined" style="font-size:16px;color:var(--cs-tertiary)">pending_actions</span>
        <span style="font-size:13px;color:var(--cs-on-surface-variant)">Waiting for your choice — type your response below</span>
      </div>

      <!-- Input bar -->
      <div class="chatbot-input-bar">
        <div class="chatbot-input-wrap">
          <textarea
            ref="inputEl"
            v-model="draft"
            class="chatbot-textarea"
            placeholder="Type a message…"
            rows="1"
            @keydown.enter.exact.prevent="submitDraft"
            @input="autoResize"
          />
          <button
            class="chatbot-send-btn"
            :disabled="!draft.trim() || loading"
            @click="submitDraft"
            title="Send (Enter)"
          >
            <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1">send</span>
          </button>
        </div>
        <div style="font-size:11px;color:var(--cs-muted);text-align:center;margin-top:6px">
          Powered by Gemini · Shift+Enter for newline
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, onMounted } from 'vue';
import { chatbotApi } from '../services/api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();

const userInitials = computed(() => {
  const name = authStore.displayName || authStore.username || 'U';
  return name.slice(0, 2).toUpperCase();
});

interface ChatMessage { role: 'user' | 'bot'; content: string; chips?: string[] }
interface SessionSummary { id: number; preview: string; message_count: number; last_active: string }

const messages = ref<ChatMessage[]>([]);
const sessions = ref<SessionSummary[]>([]);
const draft = ref('');
const loading = ref(false);
const sessionId = ref<number | null>(null);
const pendingAction = ref(false);
const sidebarOpen = ref(false);
const scrollEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);

const examplePrompts = [
  'Add a weekly task to take out the bins on Monday',
  'What are my pending tasks?',
  'Show me the group leaderboard',
  "I can't do tonight's cooking — put it on the marketplace",
  'Set my preference for cleaning to "avoid"',
  'What are my stats?',
];

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86400000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diff < 604800000) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

function autoResize() {
  const el = inputEl.value;
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

async function scrollToBottom() {
  await nextTick();
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight;
}

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>(\n|$))+/g, '<ul>$&</ul>')
    .replace(/\n/g, '<br/>');
}

async function loadSessions() {
  try {
    const res = await chatbotApi.listSessions();
    sessions.value = res.data;
  } catch {}
}

async function loadSession(id: number) {
  try {
    const res = await chatbotApi.loadSession(id);
    sessionId.value = res.data.session_id;
    messages.value = res.data.messages;
    pendingAction.value = false;
    sidebarOpen.value = false;
    await scrollToBottom();
    inputEl.value?.focus();
  } catch {}
}

async function sendMessage(text: string) {
  const trimmed = text.trim();
  if (!trimmed || loading.value) return;

  messages.value.push({ role: 'user', content: trimmed });
  draft.value = '';
  loading.value = true;
  await scrollToBottom();

  if (inputEl.value) inputEl.value.style.height = 'auto';

  try {
    const res = await chatbotApi.send(trimmed, sessionId.value);
    const { reply, session_id, pending_action, options } = res.data;

    sessionId.value = session_id;
    pendingAction.value = !!pending_action;
    messages.value.push({
      role: 'bot',
      content: reply,
      chips: Array.isArray(options) && options.length > 0 ? options : undefined,
    });
    // Refresh sidebar list after each message
    await loadSessions();
  } catch (err: any) {
    const detail = err?.response?.data?.error || err?.response?.data?.detail || 'Something went wrong. Please try again.';
    messages.value.push({ role: 'bot', content: detail });
  } finally {
    loading.value = false;
    await scrollToBottom();
    inputEl.value?.focus();
  }
}

function submitDraft() {
  sendMessage(draft.value);
}

async function startNewChat() {
  messages.value = [];
  sessionId.value = null;
  pendingAction.value = false;
  draft.value = '';
  sidebarOpen.value = false;
  await nextTick();
  inputEl.value?.focus();
}

onMounted(async () => {
  await loadSessions();
  // Auto-load the most recent session if one exists
  if (sessions.value.length > 0) {
    await loadSession(sessions.value[0].id);
  }
});
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────── */
.chatbot-layout {
  display: flex;
  height: calc(100vh - var(--cs-topbar-h, 64px));
  overflow: hidden;
  position: relative;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
.chatbot-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--cs-surface-container);
  border-right: 1px solid var(--cs-outline-variant);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, opacity 0.2s ease;
}

@media (max-width: 700px) {
  .chatbot-sidebar {
    position: absolute;
    top: 0; left: 0; bottom: 0;
    z-index: 10;
    width: 260px;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
    box-shadow: 2px 0 12px rgba(0,0,0,0.12);
  }
  .chatbot-sidebar--open {
    transform: translateX(0);
  }
}

@media (min-width: 701px) {
  .chatbot-sidebar {
    width: 0;
    opacity: 0;
    pointer-events: none;
  }
  .chatbot-sidebar--open {
    width: 260px;
    opacity: 1;
    pointer-events: auto;
  }
}

.chatbot-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px 10px;
  border-bottom: 1px solid var(--cs-outline-variant);
  flex-shrink: 0;
}

.chatbot-new-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 10px 10px 6px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px dashed var(--cs-outline-variant);
  background: transparent;
  color: var(--cs-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}
.chatbot-new-btn:hover {
  background: var(--cs-surface-container-high, #eae8e4);
}

.chatbot-session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 6px 10px;
}

.chatbot-session-empty {
  font-size: 12px;
  color: var(--cs-muted);
  text-align: center;
  padding: 20px 10px;
}

.chatbot-session-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s;
  margin-bottom: 2px;
}
.chatbot-session-item:hover {
  background: var(--cs-surface-container-high, #eae8e4);
}
.chatbot-session-item--active {
  background: var(--cs-primary-fixed, #ffdad5);
}
.chatbot-session-preview {
  font-size: 13px;
  color: var(--cs-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.chatbot-session-meta {
  font-size: 11px;
  color: var(--cs-muted);
  margin-top: 2px;
}

/* ── Main ────────────────────────────────────────────────────── */
.chatbot-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-width: 860px;
  padding: 0 24px;
}

.chatbot-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid var(--cs-outline-variant);
  flex-shrink: 0;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--cs-on-surface-variant);
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
}
.icon-btn:hover { background: var(--cs-surface-container-high, #eae8e4); }

/* ── Messages ─────────────────────────────────────────────────── */
.chatbot-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-behavior: smooth;
}

/* ── Empty state ─────────────────────────────────────────── */
.chatbot-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
}
.chatbot-empty-icon {
  font-size: 56px;
  color: var(--cs-primary);
  opacity: 0.25;
  margin-bottom: 16px;
  font-variation-settings: 'FILL' 1;
}
.chatbot-empty-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--cs-on-surface);
  margin-bottom: 8px;
}
.chatbot-empty-sub {
  font-size: 13px;
  color: var(--cs-muted);
  margin-bottom: 16px;
}
.chatbot-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 600px;
}
.chatbot-suggestion-chip {
  background: var(--cs-surface-container);
  border: 1px solid var(--cs-outline-variant);
  border-radius: 20px;
  padding: 7px 14px;
  font-size: 13px;
  font-family: inherit;
  color: var(--cs-on-surface);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  text-align: left;
}
.chatbot-suggestion-chip:hover {
  background: var(--cs-surface-container-high, #eae8e4);
  border-color: var(--cs-primary);
  color: var(--cs-primary);
}

/* ── Message rows ────────────────────────────────────────── */
.chatbot-msg {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.chatbot-msg--user { flex-direction: row-reverse; }

.chatbot-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--cs-primary-fixed, #ffdad5);
  color: var(--cs-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
}
.chatbot-avatar--user {
  background: var(--cs-primary);
  color: #fff;
}

.chatbot-bubble {
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--cs-on-surface);
  background: var(--cs-surface-container);
  word-break: break-word;
}
.chatbot-msg-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 70%;
}
.chatbot-msg--user .chatbot-msg-body { align-items: flex-end; }
.chatbot-msg--user .chatbot-bubble {
  background: var(--cs-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
  max-width: 100%;
}
.chatbot-msg--bot .chatbot-bubble { border-bottom-left-radius: 4px; max-width: 100%; }

/* ── Option chips ─────────────────────────────────────────── */
.chatbot-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chatbot-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid var(--cs-outline-variant);
  background: var(--cs-surface-container);
  color: var(--cs-on-surface);
  font-size: 13px;
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.chatbot-chip:hover:not(:disabled) {
  background: var(--cs-primary-fixed, #ffdad5);
  border-color: var(--cs-primary);
  color: var(--cs-primary);
}
.chatbot-chip:disabled { opacity: 0.5; cursor: not-allowed; }
.chatbot-chip--none {
  border-color: var(--cs-error, #ba1a1a);
  color: var(--cs-error, #ba1a1a);
}
.chatbot-chip--none:hover:not(:disabled) {
  background: color-mix(in srgb, var(--cs-error, #ba1a1a) 10%, transparent);
}
.chatbot-chip-icon {
  font-size: 14px;
}

.chatbot-bubble :deep(code) {
  background: rgba(0,0,0,0.08);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}
.chatbot-msg--user .chatbot-bubble :deep(code) { background: rgba(255,255,255,0.2); }
.chatbot-bubble :deep(ul) { margin: 6px 0 0 0; padding-left: 18px; list-style: disc; }
.chatbot-bubble :deep(li) { margin-bottom: 2px; }

/* Typing dots */
.chatbot-bubble--typing {
  display: flex; align-items: center; gap: 5px; padding: 14px 18px;
}
.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--cs-on-surface-variant);
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
  40%            { transform: scale(1);   opacity: 1; }
}

/* ── Pending action banner ────────────────────────────────── */
.chatbot-pending-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--cs-tertiary-container, #ffdcbd);
  padding: 8px 14px;
  border-radius: 10px;
  margin: 0 0 8px;
  flex-shrink: 0;
}

/* ── Input bar ───────────────────────────────────────────── */
.chatbot-input-bar {
  flex-shrink: 0;
  padding: 12px 0 16px;
  border-top: 1px solid var(--cs-outline-variant);
}
.chatbot-input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--cs-surface-container);
  border-radius: 16px;
  padding: 10px 10px 10px 16px;
  border: 1px solid var(--cs-outline-variant);
  transition: border-color 0.15s;
}
.chatbot-input-wrap:focus-within { border-color: var(--cs-primary); }
.chatbot-textarea {
  flex: 1;
  border: none; outline: none;
  background: transparent;
  resize: none;
  font-family: inherit;
  font-size: 14px;
  color: var(--cs-on-surface);
  line-height: 1.5;
  max-height: 140px;
  overflow-y: auto;
}
.chatbot-textarea::placeholder { color: var(--cs-muted); }
.chatbot-send-btn {
  width: 38px; height: 38px;
  border-radius: 10px;
  background: var(--cs-primary);
  color: #fff; border: none;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.15s, background 0.15s;
}
.chatbot-send-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.chatbot-send-btn:not(:disabled):hover { background: var(--cs-primary-container, #b35b50); }
</style>
