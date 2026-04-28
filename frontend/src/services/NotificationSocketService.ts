/**
 * Connects to the Django Channels WebSocket endpoint and dispatches
 * incoming messages to registered handlers.
 *
 * Replay-aware reconnection:
 *   - Tracks the ID of the last received notification in localStorage.
 *   - On every (re)connect, appends ?since={id} to the WS URL so the server
 *     replays any notifications the client missed during the gap.
 *
 * Usage:
 *   const svc = new NotificationSocketService();
 *   svc.onNotification((n) => console.log(n));
 *   svc.connect();
 *   // later:
 *   svc.disconnect();
 */

const LAST_NOTIF_KEY = 'cs_last_notification_id';

type NotificationPayload = {
  id: string;
  type: string;
  title: string;
  content: string;
  read: boolean;
  dismissed: boolean;
  created_at: string;
  group_id: string | null;
  task_occurrence_id: number | null;
  task_swap_id: number | null;
  task_proposal_id: number | null;
  message_id: number | null;
  action_url: string;
};

type ChatPayload = {
  id: number;
  group_id: string;
  sender_id: string;
  username: string;
  body: string;
  sent_at: string;
};

type ReceiptsPayload = {
  message_ids: number[];
  user_id: string;
  username: string;
  seen_at: string;
};

export type TaskUpdatePayload = {
  subtype: 'marketplace_claimed' | 'emergency_accepted';
  group_id: string | null;
  occurrence_id: number | null;
  listing_id: number | null;
};

type NotificationHandler = (payload: NotificationPayload) => void;
type ChatHandler = (payload: ChatPayload) => void;
type ReceiptsHandler = (payload: ReceiptsPayload) => void;
type TaskUpdateHandler = (payload: TaskUpdatePayload) => void;

/** Module-level singleton used by the function-style API below. */
let _singleton: NotificationSocketService | null = null;

/** Connect the module-level singleton (for test imports). */
export function connectNotificationSocket(): NotificationSocketService {
  if (!_singleton) _singleton = new NotificationSocketService();
  _singleton.connect();
  return _singleton;
}

/** Disconnect and destroy the module-level singleton. */
export function disconnectNotificationSocket(): void {
  _singleton?.disconnect();
  _singleton = null;
}

const WS_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws');

export class NotificationSocketService {
  private socket: WebSocket | null = null;
  private notificationHandlers: NotificationHandler[] = [];
  private chatHandlers: ChatHandler[] = [];
  private receiptsHandlers: ReceiptsHandler[] = [];
  private taskUpdateHandlers: TaskUpdateHandler[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  connect() {
    if (this.socket && this.socket.readyState === WebSocket.CONNECTING) return; // already opening
    this.shouldReconnect = true;
    this._open();
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  onNotification(handler: NotificationHandler) {
    this.notificationHandlers.push(handler);
  }

  onChat(handler: ChatHandler) {
    this.chatHandlers.push(handler);
  }

  onReceiptsUpdate(handler: ReceiptsHandler) {
    this.receiptsHandlers.push(handler);
  }

  onTaskUpdate(handler: TaskUpdateHandler) {
    this.taskUpdateHandlers.push(handler);
  }

  sendMarkRead(groupId: string, messageIds: number[]) {
    this._send({ type: 'mark_read', group_id: groupId, message_ids: messageIds });
  }

  sendPing() {
    this._send({ type: 'ping' });
  }

  sendChatMessage(groupId: string, body: string) {
    this._send({ type: 'chat_message', group_id: groupId, body });
  }

  // ---------------------------------------------------------------- //
  //  Private
  // ---------------------------------------------------------------- //

  private _buildUrl(): string {
    const lastId = localStorage.getItem(LAST_NOTIF_KEY);
    const base = `${WS_BASE}/ws/chores/`;
    return lastId ? `${base}?since=${lastId}` : base;
  }

  private _open() {
    this.socket = new WebSocket(this._buildUrl());

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'notification') {
          const n: NotificationPayload = data.notification;
          // Persist the highest seen notification ID for replay on next reconnect
          const stored = localStorage.getItem(LAST_NOTIF_KEY);
          if (!stored || parseInt(n.id, 10) > parseInt(stored, 10)) {
            localStorage.setItem(LAST_NOTIF_KEY, n.id);
          }
          this.notificationHandlers.forEach((h) => h(n));
        } else if (data.type === 'chat_message') {
          this.chatHandlers.forEach((h) => h(data));
        } else if (data.type === 'receipts_update') {
          this.receiptsHandlers.forEach((h) => h(data));
        } else if (data.type === 'task_update') {
          this.taskUpdateHandlers.forEach((h) => h(data as TaskUpdatePayload));
        }
      } catch (e) {
        console.error('NotificationSocketService: malformed WebSocket frame', event.data, e);
      }
    };

    this.socket.onclose = () => {
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this._open(), 3000);
      }
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  private _send(payload: object) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }
}
