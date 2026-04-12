import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import type { AuthStackParamList } from '../../navigation/types';
import { authService } from '../../services/authService';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<AuthStackParamList, 'ResetPassword'>;
type Route = RouteProp<AuthStackParamList, 'ResetPassword'>;

function evalStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pw.length >= 8)  score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { score: 0.2, label: 'Weak',   color: '#ba1a1a' };
  if (score === 2) return { score: 0.4, label: 'Fair',   color: '#e6821e' };
  if (score === 3) return { score: 0.6, label: 'Good',   color: '#d4a017' };
  if (score === 4) return { score: 0.8, label: 'Strong', color: '#496640' };
  return             { score: 1.0, label: 'Great',   color: '#2e7d32' };
}

export default function ResetPasswordScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const token = route.params?.token ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const strength = evalStrength(password);
  const mismatch = confirm.length > 0 && password !== confirm;

  async function handleReset() {
    if (!password || !confirm) {
      setError('Please fill in both password fields.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await authService.resetPassword(token, password, confirm);
      setSuccess(true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.response?.data?.token;
      setError(detail || 'Reset failed. The link may have expired.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      {/* Decorative blobs */}
      <View style={[s.blob, s.blobTopRight]} />
      <View style={[s.blob, s.blobBottomLeft]} />

      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()} activeOpacity={0.8}>
          <Text style={s.backIcon}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={s.headerBrand}>ChoreSync</Text>
        <View style={{ width: 40 }} />
      </View>

      <KeyboardAvoidingView
        style={s.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={s.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {success ? (
            /* ── Success state ─────────────────────────── */
            <View style={s.card}>
              <Text style={s.successCheck}>check_circle</Text>
              <Text style={s.successHeadline}>Password updated!</Text>
              <Text style={s.successBody}>
                You can now use your new password{'\n'}to access ChoreSync.
              </Text>
              <TouchableOpacity
                style={s.signInBtn}
                onPress={() => navigation.navigate('Login')}
                activeOpacity={0.8}
              >
                <Text style={s.signInBtnText}>Go to Sign In</Text>
                <Text style={s.signInArrow}>arrow_forward</Text>
              </TouchableOpacity>
            </View>
          ) : (
            /* ── Form ─────────────────────────────────── */
            <View style={s.card}>
              {/* Icon */}
              <View style={s.iconWrap}>
                <Text style={s.iconSymbol}>key</Text>
              </View>

              <Text style={s.headline}>Set new password</Text>
              <Text style={s.subtitle}>Must be at least 8 characters</Text>

              <View style={s.fields}>
                {/* New password */}
                <View>
                  <Text style={s.fieldLabel}>New password</Text>
                  <View style={s.inputWrap}>
                    <TextInput
                      style={s.input}
                      placeholder="••••••••"
                      placeholderTextColor="rgba(85,66,64,0.4)"
                      value={password}
                      onChangeText={setPassword}
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="next"
                    />
                    <TouchableOpacity onPress={() => setShowPassword(v => !v)} style={s.eyeBtn}>
                      <Text style={s.eyeIcon}>{showPassword ? 'visibility_off' : 'visibility'}</Text>
                    </TouchableOpacity>
                  </View>
                  {password.length > 0 && (
                    <View style={s.strengthRow}>
                      <View style={s.strengthTrack}>
                        <View
                          style={[
                            s.strengthFill,
                            { width: `${strength.score * 100}%` as any, backgroundColor: strength.color },
                          ]}
                        />
                      </View>
                      <Text style={[s.strengthLabel, { color: strength.color }]}>{strength.label}</Text>
                    </View>
                  )}
                </View>

                {/* Confirm password */}
                <View>
                  <Text style={s.fieldLabel}>Confirm password</Text>
                  <View style={[s.inputWrap, mismatch && s.inputWrapError]}>
                    <TextInput
                      style={s.input}
                      placeholder="••••••••"
                      placeholderTextColor="rgba(85,66,64,0.4)"
                      value={confirm}
                      onChangeText={setConfirm}
                      secureTextEntry={!showConfirm}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="done"
                      onSubmitEditing={handleReset}
                    />
                    <TouchableOpacity onPress={() => setShowConfirm(v => !v)} style={s.eyeBtn}>
                      <Text style={s.eyeIcon}>{showConfirm ? 'visibility_off' : 'visibility'}</Text>
                    </TouchableOpacity>
                  </View>
                  {mismatch && (
                    <View style={s.mismatchRow}>
                      <Text style={s.mismatchIcon}>error</Text>
                      <Text style={s.mismatchText}>Passwords do not match</Text>
                    </View>
                  )}
                </View>

                {!!error && <Text style={s.errorText}>{error}</Text>}

                {/* Submit */}
                <TouchableOpacity onPress={handleReset} disabled={loading || mismatch} activeOpacity={0.88}>
                  <LinearGradient
                    colors={mismatch ? [C.disabledStart, C.disabledEnd] : [C.primary, C.primaryContainer]}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={s.primaryBtn}
                  >
                    {loading
                      ? <ActivityIndicator color="#fff" />
                      : <Text style={s.primaryBtnText}>Reset Password</Text>
                    }
                  </LinearGradient>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Footer */}
          <View style={s.footer}>
            <Text style={s.footerText}>Having trouble?</Text>
            <TouchableOpacity
              style={s.mailBtn}
              onPress={() => Linking.openURL('mailto:syncchore@gmail.com')}
              activeOpacity={0.7}
            >
              <Text style={s.mailIcon}>mail</Text>
              <Text style={s.mailLabel}>syncchore@gmail.com</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}


const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },

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

  // ── Header ──────────────────────────────────────
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    height: 64,
  },
  backBtn: {
    width: 40, height: 40,
    borderRadius: 20,
    backgroundColor: C.surfaceContainer,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.primary,
  },
  headerBrand: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 18,
    color: C.primary,
  },

  // ── Scroll ──────────────────────────────────────
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingBottom: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // ── Card ────────────────────────────────────────
  card: {
    width: '100%',
    backgroundColor: C.surfaceContainer,
    borderRadius: 24,
    padding: 28,
    alignItems: 'center',
  },

  iconWrap: {
    width: 72, height: 72,
    backgroundColor: C.primaryFixed,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  iconSymbol: {
    fontFamily: 'MaterialSymbols',
    fontSize: 36,
    color: C.primary,
  },

  headline: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 24,
    color: C.onSurface,
    textAlign: 'center',
    letterSpacing: -0.5,
    marginBottom: 6,
  },
  subtitle: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.onSurfaceVariant,
    textAlign: 'center',
    marginBottom: 24,
  },

  // ── Fields ──────────────────────────────────────
  fields: { width: '100%', gap: 16 },

  fieldLabel: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 13,
    color: C.onSurfaceVariant,
    marginBottom: 6,
    marginLeft: 2,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 8,
  },
  inputWrapError: {
    borderWidth: 1,
    borderColor: 'rgba(186,26,26,0.25)',
  },
  input: {
    flex: 1,
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 15,
    color: C.onSurface,
    padding: 0,
    margin: 0,
  },
  eyeBtn: { padding: 2 },
  eyeIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.onSurfaceVariant,
  },

  strengthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 8,
  },
  strengthTrack: {
    flex: 1,
    height: 4,
    backgroundColor: C.surfaceContainerHighest,
    borderRadius: 2,
    overflow: 'hidden',
  },
  strengthFill: { height: '100%', borderRadius: 2 },
  strengthLabel: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 11,
    width: 44,
  },

  mismatchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
    marginLeft: 2,
  },
  mismatchIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 14,
    color: C.error,
  },
  mismatchText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 12,
    color: C.error,
  },

  errorText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.error,
    textAlign: 'center',
  },

  primaryBtn: {
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.22,
    shadowRadius: 12,
    elevation: 5,
  },
  primaryBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 16,
    color: '#fff',
    letterSpacing: 0.2,
  },

  // ── Success ─────────────────────────────────────
  successCheck: {
    fontFamily: 'MaterialSymbols',
    fontSize: 64,
    color: C.secondary,
    marginBottom: 16,
    textAlign: 'center',
  },
  successHeadline: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 24,
    color: C.onSurface,
    textAlign: 'center',
    marginBottom: 10,
  },
  successBody: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: C.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 28,
  },
  signInBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 2,
    borderColor: 'rgba(135,114,111,0.2)',
    borderRadius: 14,
    paddingHorizontal: 24,
    height: 52,
  },
  signInBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 15,
    color: C.onSurface,
  },
  signInArrow: {
    fontFamily: 'MaterialSymbols',
    fontSize: 18,
    color: C.onSurface,
  },

  // ── Footer ──────────────────────────────────────
  footer: {
    marginTop: 28,
    alignItems: 'center',
    gap: 10,
  },
  footerText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 12,
    color: 'rgba(85,66,64,0.5)',
  },
  mailBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: C.surfaceContainer,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  mailIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 16,
    color: C.onSurfaceVariant,
  },
  mailLabel: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 12,
    color: C.onSurfaceVariant,
  },
});
