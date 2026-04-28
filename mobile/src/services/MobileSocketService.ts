/**
 * Global singleton WebSocket service for the mobile app.
 *
 * Mirrors the web's NotificationSocketService. Connects once when the user
 * logs in (wired in AppNavigator) and stays alive across all screens.
 *
 * Auth: passes ?token=<jwt_access_token> so JWTAuthMiddleware can identify
 * the user without a session cookie.
 *
 * Replay: passes ?since=<lastNotifId> on (re)connect so the server replays
 * any notifications missed during a gap.
 *
 * Reconnect: exponential back-off capped at 30 s.
 */

import Constants from 'expo-constants';
import { tokenStorage } from './tokenStorage';

const WS_BASE = (
  (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ?? 'http://localhost:8000'
).replace(/^http/, 'ws');

// ── Payload types ────────────────────────────────────────────────────────────

export type NotificationPayload = {
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

export type TaskUpdatePayload = {
  type: 'task_update';
  subtype: string;
  group_id: string | null;
  occurrence_id?: number | null;
  proposal_id?: number | null;
  listing_id?: number | null;
};

export type ChatPayload = {
  id: number;
  group_id: string;
  sender_id: string;
  username: string;
  body: string;
  sent_at: string;
};

export type ReceiptsPayload = {
  message_ids: number[];
  user_id: string;
  username: string;
  seen_at: string;
};

type Handler<T> = (payload: T) => void;
type Unsubscribe = () => void;

// ── Service ──────────────────────────────────────────────────────────────────

class MobileSocketService {
  private socket: WebSocket | null = null;
  private shouldConnect = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;

  private notifHandlers: Handler<NotificationPayload>[] = [];
  private taskUpdateHandlers: Handler<TaskUpdatePayload>[] = [];
  private chatHandlers: Handler<ChatPayload>[] = [];
  private receiptsHandlers: Handler<ReceiptsPayload>[] = [];

  // ── Lifecycle ──────────────────────────────────────────────────

  connect(): void {
    this.shouldConnect = true;
    this._open();
  }

  disconnect(): void {
    this.shouldConnect = false;
    this._clearTimer();
    this.socket?.close();
    this.socket = null;
    this.reconnectDelay = 1000;
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  // ── Subscriptions (return an unsubscribe fn) ───────────────────

  onNotification(cb: Handler<NotificationPayload>): Unsubscribe {
    this.notifHandlers.push(cb);
    return () => { this.notifHandlers = this.notifHandlers.filter((h) => h !== cb); };
  }

  onTaskUpdate(cb: Handler<TaskUpdatePayload>): Unsubscribe {
    this.taskUpdateHandlers.push(cb);
    return () => { this.taskUpdateHandlers = this.taskUpdateHandlers.filter((h) => h !== cb); };
  }

  onChat(cb: Handler<ChatPayload>): Unsubscribe {
    this.chatHandlers.push(cb);
    return () => { this.chatHandlers = this.chatHandlers.filter((h) => h !== cb); };
  }

  onReceiptsUpdate(cb: Handler<ReceiptsPayload>): Unsubscribe {
    this.receiptsHandlers.push(cb);
    return () => { this.receiptsHandlers = this.receiptsHandlers.filter((h) => h !== cb); };
  }

  // ── Send helpers ───────────────────────────────────────────────

  sendChatMessage(groupId: string, body: string): void {
    this._send({ type: 'chat_message', group_id: groupId, body });
  }

  sendMarkRead(groupId: string, messageIds: number[]): void {
    this._send({ type: 'mark_read', group_id: groupId, message_ids: messageIds });
  }

  // ── Private ────────────────────────────────────────────────────

  private async _open(): Promise<void> {
    if (!this.shouldConnect) return;
    if (this.socket?.readyState === WebSocket.CONNECTING) return;

    const token = await tokenStorage.getAccess();
    if (!token || !this.shouldConnect) return;

    const lastId = await tokenStorage.getLastNotifId();
    let url = `${WS_BASE}/ws/chores/?token=${encodeURIComponent(token)}`;
    if (lastId) url += `&since=${encodeURIComponent(lastId)}`;

    const ws = new WebSocket(url);
    this.socket = ws;

    ws.onopen = () => {
      this.reconnectDelay = 1000;
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string);
        switch (data.type) {
          case 'notification': {
            const n: NotificationPayload = data.notification;
            tokenStorage.saveLastNotifId(String(n.id));
            this.notifHandlers.forEach((h) => h(n));
            break;
          }
          case 'task_update':
            this.taskUpdateHandlers.forEach((h) => h(data as TaskUpdatePayload));
            break;
          case 'chat_message':
            this.chatHandlers.forEach((h) => h(data as ChatPayload));
            break;
          case 'receipts_update':
            this.receiptsHandlers.forEach((h) => h(data as ReceiptsPayload));
            break;
        }
      } catch { /* ignore malformed frames */ }
    };

    ws.onerror = () => ws.close();

    ws.onclose = () => {
      if (!this.shouldConnect) return;
      this._clearTimer();
      this.reconnectTimer = setTimeout(() => {
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30_000);
        this._open();
      }, this.reconnectDelay);
    };
  }

  private _send(payload: object): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private _clearTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

export const socketService = new MobileSocketService();
