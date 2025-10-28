/** Service placeholder for notification socket management. */
export function connectNotificationSocket(
  userId: number,
  onMessage: (payload: unknown) => void,
): void {
  /** TODO: Open a WebSocket and bind notification message handlers. */
  throw new Error('TODO: implement connectNotificationSocket');
}

export function disconnectNotificationSocket(): void {
  /** TODO: Close the notification WebSocket and release resources. */
  throw new Error('TODO: implement disconnectNotificationSocket');
}
