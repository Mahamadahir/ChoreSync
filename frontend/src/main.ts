import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import App from './App.vue';
import HomeView from './views/HomeView.vue';
import SignupView from './views/SignupView.vue';
import LoginView from './views/LoginView.vue';
import CheckEmailView from './views/CheckEmailView.vue';
import VerifyEmailView from './views/VerifyEmailView.vue';
import UpdateProfileView from './views/UpdateProfileView.vue';
import ForgotPasswordView from './views/ForgotPasswordView.vue';
import ResetPasswordView from './views/ResetPasswordView.vue';
import { useAuthStore } from './stores/auth';
import { authService } from './services/authService';
import GoogleLoginView from './views/GoogleLoginView.vue';
import MicrosoftLoginView from './views/MicrosoftLoginView.vue';
import CalendarView from './views/CalendarView.vue';
import GoogleCalendarSelectView from './views/GoogleCalendarSelectView.vue';
import { Quasar } from 'quasar';
import '@quasar/extras/material-icons/material-icons.css';
import 'quasar/src/css/index.sass';

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: HomeView, meta: { requiresAuth: true } },
  { path: '/signup', name: 'signup', component: SignupView, meta: { requiresGuest: true } },
  { path: '/login', name: 'login', component: LoginView, meta: { requiresGuest: true } },
  { path: '/check-email', name: 'check-email', component: CheckEmailView, meta: { requiresGuest: true } },
  { path: '/verify-email', name: 'verify-email', component: VerifyEmailView, meta: { requiresGuest: true } },
  { path: '/profile', name: 'profile', component: UpdateProfileView, meta: { requiresAuth: true } },
  { path: '/calendar', name: 'calendar', component: CalendarView, meta: { requiresAuth: true } },
  { path: '/calendar/google/select', name: 'google-calendar-select', component: GoogleCalendarSelectView, meta: { requiresAuth: true } },
  { path: '/forgot-password', name: 'forgot-password', component: ForgotPasswordView, meta: { requiresGuest: true } },
  { path: '/reset-password', name: 'reset-password', component: ResetPasswordView, meta: { requiresGuest: true } },
  { path: '/login/google', name: 'login-google', component: GoogleLoginView, meta: { requiresGuest: true } },
  { path: '/login/microsoft', name: 'login-microsoft', component: MicrosoftLoginView, meta: { requiresGuest: true } },
  // add more routes here
];

const pinia = createPinia();
const router = createRouter({
  history: createWebHistory(),
  routes,
});

let bootstrapPromise: Promise<void> | null = null;

const ensureAuthBootstrap = () => {
  const authStore = useAuthStore(pinia);
  if (authStore.hasBootstrapped) {
    return Promise.resolve();
  }
  if (!bootstrapPromise) {
    bootstrapPromise = authService
      .getProfile()
      .then(() => authStore.setAuthenticated(true))
      .catch(() => authStore.clear())
      .finally(() => {
        authStore.markBootstrapped();
      });
  }
  return bootstrapPromise;
};

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia);
  await ensureAuthBootstrap();
  const isAuthed = authStore.isAuthenticated;
  if (to.meta.requiresAuth && !isAuthed) {
    return { name: 'login' };
  }
  if (to.meta.requiresGuest && isAuthed) {
    return { name: 'home' };
  }
  return true;
});

createApp(App)
  .use(Quasar, { plugins: {} })
  .use(pinia)
  .use(router)
  .mount('#app');
