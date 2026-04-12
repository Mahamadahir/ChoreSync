import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { AuthStackParamList } from '../../navigation/types';
import { authService } from '../../services/authService';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<AuthStackParamList, 'VerifyEmail'>;
type Route = RouteProp<AuthStackParamList, 'VerifyEmail'>;

const RESEND_COOLDOWN = 45;

type Status = 'idle' | 'checking' | 'success' | 'error';

export default function VerifyEmailScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const email = route.params?.email ?? '';

  const [status, setStatus] = useState<Status>('idle');
  const [resendCountdown, setResendCountdown] = useState(0);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendError, setResendError] = useState('');

  // Progress bar animation (decorative — fills to ~40% while idle)
  const progressAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: 0.38,
      duration: 900,
      useNativeDriver: false,
    }).start();
  }, []);

  // Animate to full on success
  useEffect(() => {
    if (status === 'success') {
      Animated.timing(progressAnim, {
        toValue: 1,
        duration: 600,
        useNativeDriver: false,
      }).start();
    }
  }, [status]);

  // Resend countdown ticker
  useEffect(() => {
    if (resendCountdown <= 0) return;
    const id = setInterval(() => {
      setResendCountdown(c => {
        if (c <= 1) { clearInterval(id); return 0; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [resendCountdown]);

  const handleResend = useCallback(async () => {
    if (resendCountdown > 0 || resendLoading) return;
    setResendLoading(true);
    setResendError('');
    try {
      await authService.resendVerification(email);
      setResendCountdown(RESEND_COOLDOWN);
    } catch (err: any) {
      setResendError(err?.response?.data?.detail || 'Could not resend. Try again.');
    } finally {
      setResendLoading(false);
    }
  }, [email, resendCountdown, resendLoading]);

  const progressWidth = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  const progressColor = status === 'success' ? C.secondary : C.secondary;

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      {/* Top progress bar */}
      <View style={s.progressTrack}>
        <Animated.View
          style={[
            s.progressFill,
            { width: progressWidth, backgroundColor: progressColor },
          ]}
        />
      </View>

      {/* Decorative blobs */}
      <View style={[s.blob, s.blobTopRight]} />
      <View style={[s.blob, s.blobBottomLeft]} />

      {/* Main content */}
      <View style={s.main}>

        {/* Icon + headline */}
        <View style={s.top}>
          <View style={s.iconWrap}>
            <Text style={s.iconSymbol}>mark_email_unread</Text>
          </View>

          <Text style={s.headline}>Check your inbox</Text>
          <Text style={s.subtitle}>
            We sent a verification link to{'\n'}
            <Text style={s.emailHighlight}>{email || 'your email'}</Text>
            {'\n'}Tap the link to activate your account.
          </Text>
        </View>

        {/* Status states */}
        <View style={s.statusArea}>
          {status === 'checking' && (
            <View style={s.statusPill}>
              <Text style={s.statusPillIcon}>refresh</Text>
              <Text style={s.statusPillText}>Verifying…</Text>
            </View>
          )}
          {status === 'success' && (
            <View style={s.successBanner}>
              <Text style={s.successIcon}>verified</Text>
              <Text style={s.successText}>Email verified! Redirecting…</Text>
            </View>
          )}
          {status === 'error' && (
            <View style={s.errorBanner}>
              <View style={s.errorRow}>
                <Text style={s.errorIcon}>error</Text>
                <Text style={s.errorText}>No account found</Text>
              </View>
              <TouchableOpacity onPress={handleResend}>
                <Text style={s.errorResendLink}>Resend link</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Resend section */}
        <View style={s.resendSection}>
          <Text style={s.resendPrompt}>Didn't get it?</Text>

          <TouchableOpacity
            style={[
              s.resendBtn,
              (resendCountdown > 0 || resendLoading) && s.resendBtnDisabled,
            ]}
            onPress={handleResend}
            disabled={resendCountdown > 0 || resendLoading}
            activeOpacity={0.8}
          >
            <Text style={[
              s.resendBtnText,
              (resendCountdown > 0 || resendLoading) && s.resendBtnTextDisabled,
            ]}>
              {resendLoading ? 'Sending…' : 'Resend verification email'}
            </Text>
          </TouchableOpacity>

          {resendCountdown > 0 && (
            <Text style={s.countdownText}>Resend in {resendCountdown}s</Text>
          )}
          {!!resendError && (
            <Text style={s.resendErrorText}>{resendError}</Text>
          )}
        </View>
      </View>

      {/* Footer */}
      <View style={s.footer}>
        <Text style={s.footerText}>Wrong email? </Text>
        <TouchableOpacity onPress={() => navigation.navigate('SignUp')} activeOpacity={0.7}>
          <Text style={s.footerLink}>Sign up again</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}


const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },

  // ── Progress bar ────────────────────────────────
  progressTrack: {
    width: '100%',
    height: 3,
    backgroundColor: 'rgba(228,226,222,0.4)',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },

  // ── Blobs ───────────────────────────────────────
  blob: { position: 'absolute', borderRadius: 999 },
  blobTopRight: {
    top: -60, right: -60,
    width: 180, height: 180,
    backgroundColor: C.primaryFixed,
    opacity: 0.35,
  },
  blobBottomLeft: {
    bottom: -80, left: -80,
    width: 240, height: 240,
    backgroundColor: C.secondaryContainer,
    opacity: 0.2,
  },

  // ── Main ────────────────────────────────────────
  main: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },

  // ── Icon + headline ─────────────────────────────
  top: { alignItems: 'center', marginBottom: 24 },

  iconWrap: {
    width: 88, height: 88,
    backgroundColor: C.primaryFixed,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 28,
  },
  iconSymbol: {
    fontFamily: 'MaterialSymbols',
    fontSize: 44,
    color: C.primary,
  },

  headline: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 28,
    color: '#1e1b18',
    letterSpacing: -0.5,
    textAlign: 'center',
    marginBottom: 12,
  },
  subtitle: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: C.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 22,
  },
  emailHighlight: {
    fontFamily: 'PlusJakartaSans_700Bold',
    color: C.onSurface,
  },

  // ── Status states ───────────────────────────────
  statusArea: { width: '100%', alignItems: 'center', marginBottom: 32 },

  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.surfaceContainer,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
  },
  statusPillIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 16,
    color: C.onSurfaceVariant,
  },
  statusPillText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },

  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    width: '100%',
    backgroundColor: C.secondaryContainer,
    borderRadius: 14,
    padding: 14,
    justifyContent: 'center',
  },
  successIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.secondary,
  },
  successText: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 14,
    color: C.secondary,
  },

  errorBanner: {
    width: '100%',
    backgroundColor: C.errorContainer,
    borderRadius: 14,
    padding: 14,
    alignItems: 'center',
    gap: 8,
  },
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  errorIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 18,
    color: C.error,
  },
  errorText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: C.error,
  },
  errorResendLink: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 13,
    color: C.primary,
    textDecorationLine: 'underline',
  },

  // ── Resend section ──────────────────────────────
  resendSection: { width: '100%', alignItems: 'center', gap: 12 },

  resendPrompt: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.onSurfaceVariant,
  },

  resendBtn: {
    width: '100%',
    height: 48,
    borderWidth: 1,
    borderColor: C.outlineVariant,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resendBtnDisabled: {
    opacity: 0.45,
  },
  resendBtnText: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 14,
    color: C.onSurface,
  },
  resendBtnTextDisabled: {
    color: C.onSurfaceVariant,
  },

  countdownText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.outline,
  },
  resendErrorText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 12,
    color: C.error,
    textAlign: 'center',
  },

  // ── Footer ──────────────────────────────────────
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: 28,
  },
  footerText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: C.onSurfaceVariant,
  },
  footerLink: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 14,
    color: C.primary,
  },
});
