import React, { useState, useEffect } from 'react';
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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { AuthStackParamList } from '../../navigation/types';
import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import { useAuthRequest, makeRedirectUri, ResponseType } from 'expo-auth-session';
import { authService } from '../../services/authService';
import { tokenStorage } from '../../services/tokenStorage';
import { useAuthStore } from '../../stores/authStore';
import { Palette as C } from '../../theme';

WebBrowser.maybeCompleteAuthSession();

type Nav = NativeStackNavigationProp<AuthStackParamList, 'SignUp'>;

// ── Password strength ─────────────────────────────────────
function evalStrength(pw: string): { score: number; label: string; color: string; hint: string } {
  if (!pw) return { score: 0, label: '', color: '#d5c6c0', hint: '' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 1) return { score: 0.2, label: 'Weak',   color: '#ba1a1a', hint: 'Add uppercase letters & numbers' };
  if (score === 2) return { score: 0.4, label: 'Fair',   color: '#e8a020', hint: 'Add a special character' };
  if (score === 3) return { score: 0.6, label: 'Good',   color: '#496640', hint: 'Include a special character' };
  if (score === 4) return { score: 0.8, label: 'Strong', color: '#496640', hint: 'Looking solid!' };
  return                { score: 1.0,  label: 'Great',  color: '#496640', hint: 'Excellent password' };
}

export default function SignUpScreen() {
  const navigation = useNavigation<Nav>();
  const authStore = useAuthStore();

  const [firstName, setFirstName]     = useState('');
  const [lastName, setLastName]       = useState('');
  const [username, setUsername]       = useState('');
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [confirm, setConfirm]         = useState('');
  const [showPw, setShowPw]           = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading]         = useState(false);
  const [ssoLoading, setSsoLoading]   = useState(false);
  const [error, setError]             = useState('');

  // ── Google OAuth ──────────────────────────────────────────────────
  const [, googleResponse, promptGoogle] = Google.useAuthRequest({
    clientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? '',
    iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
    responseType: ResponseType.IdToken,
    usePKCE: false,
  });

  // ── Microsoft OAuth ───────────────────────────────────────────────
  const msTenant = process.env.EXPO_PUBLIC_MICROSOFT_TENANT_ID ?? 'common';
  const msDiscovery = {
    authorizationEndpoint: `https://login.microsoftonline.com/${msTenant}/oauth2/v2.0/authorize`,
    tokenEndpoint: `https://login.microsoftonline.com/${msTenant}/oauth2/v2.0/token`,
  };
  const [, msResponse, promptMs] = useAuthRequest(
    {
      clientId: process.env.EXPO_PUBLIC_MICROSOFT_CLIENT_ID ?? '',
      scopes: ['openid', 'profile', 'email'],
      responseType: ResponseType.IdToken,
      usePKCE: false,
      redirectUri: makeRedirectUri({ scheme: 'choresync', path: 'auth' }),
    },
    msDiscovery,
  );

  useEffect(() => {
    if (googleResponse?.type === 'success') {
      const idToken = googleResponse.params.id_token;
      if (idToken) _handleSSOSignIn(() => authService.loginWithGoogle(idToken));
      else setError('Google sign-in did not return a token.');
    } else if (googleResponse?.type === 'error') {
      setError('Google sign-in failed. Please try again.');
    }
  }, [googleResponse]);

  useEffect(() => {
    if (msResponse?.type === 'success') {
      const idToken = msResponse.params.id_token;
      if (idToken) _handleSSOSignIn(() => authService.loginWithMicrosoft(idToken));
      else setError('Microsoft sign-in did not return a token.');
    } else if (msResponse?.type === 'error') {
      setError('Microsoft sign-in failed. Please try again.');
    }
  }, [msResponse]);

  async function _handleSSOSignIn(callFn: () => Promise<{ data: { access: string; refresh: string } }>) {
    setSsoLoading(true);
    setError('');
    try {
      const { data } = await callFn();
      await tokenStorage.save(data.access, data.refresh);
      const profileRes = await authService.getProfile();
      await authStore.login(data.access, data.refresh, profileRes.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Sign-in failed. Please try again.');
    } finally {
      setSsoLoading(false);
    }
  }

  const strength = evalStrength(password);
  const pwMismatch = confirm.length > 0 && confirm !== password;

  async function handleSignUp() {
    setError('');
    if (!firstName.trim() || !lastName.trim()) { setError('Please enter your full name.'); return; }
    if (!username.trim())  { setError('Please choose a username.'); return; }
    if (!email.trim())     { setError('Please enter your email.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (password !== confirm)  { setError('Passwords do not match.'); return; }

    setLoading(true);
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      await authService.signup({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        username: username.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
        password,
        timezone,
      });
      navigation.navigate('VerifyEmail', { email: email.trim().toLowerCase() });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function handleGoogleSSO() { promptGoogle(); }
  function handleMicrosoftSSO() { promptMs(); }

  return (
    <SafeAreaView style={s.safe} edges={['top', 'bottom']}>
      {/* Decorative blobs */}
      <View style={[s.blob, s.blobBR]} />
      <View style={[s.blob, s.blobTL]} />

      {/* Back button */}
      <View style={s.topBar}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()}>
          <Text style={s.backIcon}>arrow_back</Text>
        </TouchableOpacity>
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
          {/* ── Header ─────────────────────────────────── */}
          <View style={s.header}>
            <Text style={s.title}>Create account</Text>
            <Text style={s.subtitle}>Join your household · verify email after signup</Text>
          </View>

          {/* ── Form ───────────────────────────────────── */}
          <View style={s.form}>

            {/* Name row */}
            <View style={s.nameRow}>
              <View style={s.nameField}>
                <Text style={s.label}>FIRST NAME</Text>
                <TextInput
                  style={s.input}
                  placeholder="Alex"
                  placeholderTextColor="rgba(85,66,64,0.4)"
                  value={firstName}
                  onChangeText={setFirstName}
                  autoCorrect={false}
                  returnKeyType="next"
                />
              </View>
              <View style={s.nameField}>
                <Text style={s.label}>LAST NAME</Text>
                <TextInput
                  style={s.input}
                  placeholder="Rivers"
                  placeholderTextColor="rgba(85,66,64,0.4)"
                  value={lastName}
                  onChangeText={setLastName}
                  autoCorrect={false}
                  returnKeyType="next"
                />
              </View>
            </View>

            {/* Username */}
            <View>
              <Text style={s.label}>USERNAME</Text>
              <TextInput
                style={s.input}
                placeholder="alex_rivers24"
                placeholderTextColor="rgba(85,66,64,0.4)"
                value={username}
                onChangeText={setUsername}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="next"
              />
            </View>

            {/* Email */}
            <View>
              <Text style={s.label}>EMAIL</Text>
              <TextInput
                style={s.input}
                placeholder="alex@example.com"
                placeholderTextColor="rgba(85,66,64,0.4)"
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                autoCorrect={false}
                returnKeyType="next"
              />
            </View>

            {/* Password */}
            <View>
              <Text style={s.label}>PASSWORD</Text>
              <View style={s.inputRow}>
                <TextInput
                  style={[s.input, s.inputFlex]}
                  placeholder="••••••••"
                  placeholderTextColor="rgba(85,66,64,0.4)"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPw}
                  returnKeyType="next"
                />
                <TouchableOpacity style={s.eyeBtn} onPress={() => setShowPw(!showPw)}>
                  <Text style={s.eyeIcon}>{showPw ? 'visibility_off' : 'visibility'}</Text>
                </TouchableOpacity>
              </View>
              {/* Strength bar */}
              {password.length > 0 && (
                <View style={s.strengthWrap}>
                  <View style={s.strengthTrack}>
                    <View style={[s.strengthFill, {
                      width: `${strength.score * 100}%` as any,
                      backgroundColor: strength.color,
                    }]} />
                  </View>
                  <View style={s.strengthRow}>
                    <Text style={[s.strengthLabel, { color: strength.color }]}>{strength.label}</Text>
                    <Text style={s.strengthHint}>{strength.hint}</Text>
                  </View>
                </View>
              )}
            </View>

            {/* Confirm password */}
            <View>
              <Text style={s.label}>CONFIRM PASSWORD</Text>
              <View style={s.inputRow}>
                <TextInput
                  style={[s.input, s.inputFlex]}
                  placeholder="••••••••"
                  placeholderTextColor="rgba(85,66,64,0.4)"
                  value={confirm}
                  onChangeText={setConfirm}
                  secureTextEntry={!showConfirm}
                  returnKeyType="done"
                  onSubmitEditing={handleSignUp}
                />
                <TouchableOpacity style={s.eyeBtn} onPress={() => setShowConfirm(!showConfirm)}>
                  <Text style={s.eyeIcon}>{showConfirm ? 'visibility_off' : 'visibility'}</Text>
                </TouchableOpacity>
              </View>
              {pwMismatch && (
                <Text style={s.mismatchText}>Passwords don't match</Text>
              )}
            </View>

            {/* Error */}
            {!!error && <Text style={s.errorText}>{error}</Text>}

            {/* Submit */}
            <TouchableOpacity
              onPress={handleSignUp}
              disabled={loading || pwMismatch}
              activeOpacity={0.88}
              style={{ marginTop: 8 }}
            >
              <LinearGradient
                colors={loading || pwMismatch ? [C.primaryDisabled, C.primaryDisabled] : [C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={s.primaryBtn}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={s.primaryBtnText}>Create account</Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>

          {/* ── Divider ─────────────────────────────────── */}
          <View style={s.divider}>
            <View style={s.dividerLine} />
            <Text style={s.dividerText}>OR</Text>
            <View style={s.dividerLine} />
          </View>

          {/* ── OAuth ────────────────────────────────────── */}
          <View style={s.oauthGroup}>
            <TouchableOpacity style={s.oauthBtn} onPress={handleGoogleSSO} activeOpacity={0.8} disabled={ssoLoading}>
              {ssoLoading
                ? <ActivityIndicator size="small" color="#1b1c1a" />
                : <>
                    <Text style={s.googleG}>G</Text>
                    <Text style={s.oauthText}>Continue with Google</Text>
                  </>
              }
            </TouchableOpacity>

            <TouchableOpacity style={s.oauthBtn} onPress={handleMicrosoftSSO} activeOpacity={0.8} disabled={ssoLoading}>
              <View style={s.msGrid}>
                <View style={[s.msSq, { backgroundColor: '#f25022' }]} />
                <View style={[s.msSq, { backgroundColor: '#7fba00' }]} />
                <View style={[s.msSq, { backgroundColor: '#00a4ef' }]} />
                <View style={[s.msSq, { backgroundColor: '#ffb900' }]} />
              </View>
              <Text style={s.oauthText}>Continue with Microsoft</Text>
            </TouchableOpacity>
          </View>

          {/* ── Footer ───────────────────────────────────── */}
          <View style={s.footer}>
            <Text style={s.footerText}>Already have an account?</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Login')}>
              <Text style={s.footerLink}> Sign in</Text>
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

  blob: { position: 'absolute', borderRadius: 999, opacity: 0.06 },
  blobBR: { bottom: -80, right: -80, width: 220, height: 220, backgroundColor: C.primary },
  blobTL: { top: -80, left: -80, width: 220, height: 220, backgroundColor: '#496640' },

  topBar: {
    paddingHorizontal: 20,
    paddingTop: 4,
    paddingBottom: 8,
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
    color: C.onSurfaceVariant,
  },

  scroll: {
    paddingHorizontal: 24,
    paddingBottom: 48,
  },

  header: { marginBottom: 28 },
  title: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 28,
    color: C.onSurface,
    letterSpacing: -0.5,
    marginBottom: 6,
  },
  subtitle: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.onSurfaceVariant,
    opacity: 0.8,
  },

  form: { gap: 16 },

  label: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 10,
    letterSpacing: 1,
    color: C.onSurfaceVariant,
    marginBottom: 6,
    paddingHorizontal: 2,
  },

  input: {
    height: 52,
    backgroundColor: C.surfaceContainer,
    borderRadius: 14,
    paddingHorizontal: 16,
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 15,
    color: C.onSurface,
  },

  nameRow: { flexDirection: 'row', gap: 10 },
  nameField: { flex: 1 },

  inputRow: { position: 'relative' },
  inputFlex: { paddingRight: 48 },
  eyeBtn: {
    position: 'absolute',
    right: 14,
    top: 0, bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
  },
  eyeIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: 'rgba(85,66,64,0.55)',
  },

  strengthWrap: { marginTop: 8, paddingHorizontal: 2 },
  strengthTrack: {
    height: 4,
    backgroundColor: '#e4e2de',
    borderRadius: 4,
    overflow: 'hidden',
  },
  strengthFill: {
    height: '100%',
    borderRadius: 4,
  },
  strengthRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  strengthLabel: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 11,
  },
  strengthHint: {
    fontFamily: 'PlusJakartaSans_400Regular',
    fontSize: 10,
    color: 'rgba(85,66,64,0.55)',
    fontStyle: 'italic',
  },

  mismatchText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 11,
    color: C.error,
    marginTop: 5,
    paddingHorizontal: 2,
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
  },

  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginVertical: 28,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: 'rgba(218,193,189,0.3)' },
  dividerText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 10,
    letterSpacing: 2,
    color: 'rgba(85,66,64,0.45)',
  },

  oauthGroup: { gap: 12 },
  oauthBtn: {
    height: 48,
    backgroundColor: C.white,
    borderWidth: 1,
    borderColor: 'rgba(213,198,192,0.6)',
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  googleG: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 17,
    color: '#4285F4',
    width: 20,
    textAlign: 'center',
  },
  oauthText: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 14,
    color: C.onSurface,
  },
  msGrid: {
    width: 20, height: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 1.5,
  },
  msSq: { width: 8.5, height: 8.5 },

  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 32,
    paddingBottom: 8,
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
