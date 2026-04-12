import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import Constants from 'expo-constants';
import { tokenStorage } from './tokenStorage';

const BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// ── Attach Bearer token to every request ────────────────────────────
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await tokenStorage.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auto-refresh on 401 ──────────────────────────────────────────────
let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve) => {
          refreshQueue.push((newToken) => {
            original.headers.Authorization = `Bearer ${newToken}`;
            resolve(api(original));
          });
        });
      }

      original._retry = true;
      isRefreshing = true;

      try {
        const refresh = await tokenStorage.getRefresh();
        if (!refresh) throw new Error('No refresh token');

        const { data } = await axios.post(`${BASE_URL}/api/auth/token/refresh/`, { refresh });
        await tokenStorage.save(data.access, data.refresh ?? refresh);

        refreshQueue.forEach((cb) => cb(data.access));
        refreshQueue = [];

        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        refreshQueue = [];
        await tokenStorage.clear();
        // Signal to AuthStore that session has expired
        authExpiredCallback?.();
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  },
);

// Callback registered by the auth store to handle expiry (navigate to login)
let authExpiredCallback: (() => void) | null = null;
export function registerAuthExpiredCallback(cb: () => void) {
  authExpiredCallback = cb;
}
