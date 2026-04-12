import { api } from './api';
import type { LoginPayload, SignupPayload } from '../types/auth';

export const authService = {
  login: (payload: LoginPayload) =>
    api.post('/api/auth/token/', payload),

  signup: (payload: SignupPayload) =>
    api.post('/api/auth/signup/', payload),

  refreshToken: (refresh: string) =>
    api.post('/api/auth/token/refresh/', { refresh }),

  getProfile: () =>
    api.get('/api/profile/'),

  updateProfile: (payload: { username?: string; first_name?: string; last_name?: string; timezone?: string }) =>
    api.post('/api/profile/', payload),

  changePassword: (payload: { current_password: string; new_password: string; confirm_password: string }) =>
    api.post('/api/auth/change-password/', payload),

  forgotPassword: (email: string) =>
    api.post('/api/auth/forgot-password/', { email }),

  resetPassword: (token: string, new_password: string, confirm_password: string) =>
    api.post('/api/auth/reset-password/', { token, new_password, confirm_password }),

  resendVerification: (email: string) =>
    api.post('/api/auth/resend-verification/', { email }),

  verifyEmail: (token: string) =>
    api.post('/api/auth/verify-email/', { token }),

  loginWithGoogle: (id_token: string) =>
    api.post('/api/auth/google/mobile/', { id_token }),

  loginWithMicrosoft: (id_token: string) =>
    api.post('/api/auth/microsoft/mobile/', { id_token }),
};
