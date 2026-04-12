export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  email_verified: boolean;
  avatar_url?: string | null;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export interface SignupPayload {
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  password: string;
  timezone?: string;
}
