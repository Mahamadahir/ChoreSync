import { api } from './api';

type SignupPayload = {
  username: string;
  email: string;
  password: string;
};

type LoginPayload = {
  identifier: string;
  password: string;
};

export const authService = {
  signup(payload: SignupPayload) {
    return api.post('/api/auth/signup/', payload);
  },
  login(payload: LoginPayload) {
    return api.post('/api/auth/login/', payload);
  },
  resendVerification(email: string) {
    return api.post('/api/auth/resend-verification/', { email });
  },
  verifyEmail(token: string) {
    return api.post('/api/auth/verify-email/', { token });
  },
  updateEmail(token: string, email: string) {
    return api.post('/api/auth/update-email/', { token, email });
  },
  getProfile() {
    return api.get('/api/profile/');
  },
  updateProfile(payload: { username?: string; email?: string; timezone?: string }) {
    return api.post('/api/profile/', payload);
  },
  changePassword(payload: { current_password: string; new_password: string; confirm_password: string }) {
    return api.post('/api/auth/change-password/', payload);
  },
  logout() {
    return api.post('/api/auth/logout/');
  },
  forgotPassword(email: string) {
    return api.post('/api/auth/forgot-password/', { email });
  },
  resetPassword(token: string, new_password: string, confirm_password: string) {
    return api.post('/api/auth/reset-password/', { token, new_password, confirm_password });
  },
};
