/**
 * Connects to the Django Channels WebSocket endpoint and dispatches
 * incoming messages to registered handlers.
 *
 * Usage:
 *   const svc = new NotificationSocketService();
 *   svc.onNotification((n) => console.log(n));
 *   svc.connect();
 *   // later:
 *   svc.disconnect();
 */

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
};

type ChatPayload = {
  group_id: string;
  sender_id: string;
  username: string;
  body: string;
  sent_at: string;
};

type NotificationHandler = (payload: NotificationPayload) => void;
type ChatHandler = (payload: ChatPayload) => void;

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
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  connect() {
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

  sendPing() {
    this._send({ type: 'ping' });
  }

  sendChatMessage(groupId: string, body: string) {
    this._send({ type: 'chat_message', group_id: groupId, body });
  }

  // ---------------------------------------------------------------- //
  //  Private
  // ---------------------------------------------------------------- //

  private _open() {
    this.socket = new WebSocket(`${WS_BASE}/ws/chores/`);

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'notification') {
          this.notificationHandlers.forEach((h) => h(data.notification));
        } else if (data.type === 'chat_message') {
          this.chatHandlers.forEach((h) => h(data));
        }
      } catch {
        // ignore malformed frames
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
