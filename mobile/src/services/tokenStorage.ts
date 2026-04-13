import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'choresync_access';
const REFRESH_KEY = 'choresync_refresh';
const LAST_NOTIF_KEY = 'last_notif_id';

export const tokenStorage = {
  async getAccess(): Promise<string | null> {
    return SecureStore.getItemAsync(ACCESS_KEY);
  },
  async getRefresh(): Promise<string | null> {
    return SecureStore.getItemAsync(REFRESH_KEY);
  },
  async save(access: string, refresh: string): Promise<void> {
    await Promise.all([
      SecureStore.setItemAsync(ACCESS_KEY, access),
      SecureStore.setItemAsync(REFRESH_KEY, refresh),
    ]);
  },
  async clear(): Promise<void> {
    await Promise.all([
      SecureStore.deleteItemAsync(ACCESS_KEY),
      SecureStore.deleteItemAsync(REFRESH_KEY),
    ]);
  },
  async saveLastNotifId(id: string): Promise<void> {
    await SecureStore.setItemAsync(LAST_NOTIF_KEY, id);
  },
  async getLastNotifId(): Promise<string | null> {
    return SecureStore.getItemAsync(LAST_NOTIF_KEY);
  },
};
