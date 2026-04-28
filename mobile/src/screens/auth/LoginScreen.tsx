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
import { useAuthRequest, makeRedirectUri, ResponseType, exchangeCodeAsync } from 'expo-auth-session';
import { useRef } from 'react';
import { authService } from '../../services/authService';
import { tokenStorage } from '../../services/tokenStorage';
import { useAuthStore } from '../../stores/authStore';
import { Palette as C } from '../../theme';
import LegalFooter from '../../components/common/LegalFooter';

WebBrowser.maybeCompleteAuthSession();

type Nav = NativeStackNavigationProp<AuthStackParamList, 'Login'>;

export default function LoginScreen() {
  const navigation = useNavigation<Nav>();
  const authStore = useAuthStore();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ssoLoading, setSsoLoading] = useState(false);
  const [error, setError] = useState('');

  // ── Google OAuth (Authorization Code + PKCE) ─────────────────────
  // Force the reverse-domain redirect URI that Google's Android OAuth client expects.
  // expo-auth-session v6 generates com.choresync.app:/oauthredirect by default, which
  // Google rejects for Android clients. The intent filter for this scheme is registered
  // in app.json → android.intentFilters so Android intercepts the redirect back.
  const _androidId = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? '';
  const _iosId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? '';
  const googleRedirectUri = Platform.select({
    android: _androidId ? `${_androidId.split('.').reverse().join('.')}:/oauth2redirect` : undefined,
    ios: _iosId ? `${_iosId.split('.').reverse().join('.')}:/oauth2redirect` : undefined,
  }) ?? makeRedirectUri({ scheme: 'choresync' });

  const [googleRequest, googleResponse, promptGoogle] = Google.useAuthRequest({
    clientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? '',
    iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
    redirectUri: googleRedirectUri,
    responseType: ResponseType.Code,
    usePKCE: true,
    scopes: ['openid', 'email', 'profile'],
    shouldAutoExchangeCode: false,
  });
  // Capture codeVerifier at prompt-time — the hook may return a new object on re-render.
  const googlePKCERef = useRef<{ redirectUri: string; codeVerifier?: string } | null>(null);

  // ── Microsoft OAuth (Authorization Code + PKCE) ───────────────────
  const msTenant = process.env.EXPO_PUBLIC_MICROSOFT_TENANT_ID ?? 'common';
  const msDiscovery = {
    authorizationEndpoint: `https://login.microsoftonline.com/${msTenant}/oauth2/v2.0/authorize`,
    tokenEndpoint: `https://login.microsoftonline.com/${msTenant}/oauth2/v2.0/token`,
  };
  const msRedirectUri = makeRedirectUri({ scheme: 'choresync', path: 'auth' });
  const [msRequest, msResponse, promptMs] = useAuthRequest(
    {
      clientId: process.env.EXPO_PUBLIC_MICROSOFT_CLIENT_ID ?? '',
      scopes: ['openid', 'profile', 'email'],
      responseType: ResponseType.Code,
      usePKCE: true,
      redirectUri: msRedirectUri,
    },
    msDiscovery,
  );
  const msPKCERef = useRef<{ codeVerifier?: string } | null>(null);

  useEffect(() => {
    if (googleResponse?.type !== 'success') {
      if (googleResponse?.type === 'error') setError('Google sign-in failed. Please try again.');
      return;
    }
    const code = googleResponse.params.code;
    const clientId = Platform.select({
      android: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
      ios: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
    }) ?? process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? '';
    const redirectUri = googleRedirectUri;
    const codeVerifier = googlePKCERef.current?.codeVerifier ?? googleRequest?.codeVerifier;
    setSsoLoading(true);
    setError('');
    exchangeCodeAsync(
      {
        clientId,
        code,
        redirectUri,
        extraParams: codeVerifier ? { code_verifier: codeVerifier } : undefined,
      },
      { tokenEndpoint: 'https://oauth2.googleapis.com/token' },
    )
      .then((tokenResponse) => {
        const idToken = tokenResponse.idToken;
        if (!idToken) {
          setError('Google sign-in did not return an ID token.');
          setSsoLoading(false);
          return;
        }
        return _handleSSOLogin(() => authService.loginWithGoogle(idToken));
      })
      .catch((err: any) => {
        const detail = err?.body?.error_description ?? err?.body?.error ?? err?.message ?? '';
        setError(detail ? `Google: ${detail}` : 'Google sign-in failed. Please try again.');
        setSsoLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleResponse]);

  useEffect(() => {
    if (msResponse?.type !== 'success') {
      if (msResponse?.type === 'error') setError('Microsoft sign-in failed. Please try again.');
      return;
    }
    const code = msResponse.params.code;
    const codeVerifier = msPKCERef.current?.codeVerifier ?? msRequest?.codeVerifier;
    setSsoLoading(true);
    setError('');
    exchangeCodeAsync(
      {
        clientId: process.env.EXPO_PUBLIC_MICROSOFT_CLIENT_ID ?? '',
        code,
        redirectUri: msRedirectUri,
        extraParams: codeVerifier ? { code_verifier: codeVerifier } : undefined,
      },
      { tokenEndpoint: `https://login.microsoftonline.com/${msTenant}/oauth2/v2.0/token` },
    )
      .then((tokenResponse) => {
        const idToken = tokenResponse.idToken;
        if (!idToken) {
          setError('Microsoft sign-in did not return an ID token.');
          setSsoLoading(false);
          return;
        }
        return _handleSSOLogin(() => authService.loginWithMicrosoft(idToken));
      })
      .catch((err: any) => {
        const detail = err?.body?.error_description ?? err?.body?.error ?? err?.message ?? '';
        setError(detail ? `Microsoft: ${detail}` : 'Microsoft sign-in failed. Please try again.');
        setSsoLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msResponse]);

  async function _handleSSOLogin(callFn: () => Promise<{ data: { access: string; refresh: string } }>) {
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

  async function handleLogin() {
    if (!identifier.trim() || !password) {
      setError('Please enter your email/username and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const { data } = await authService.login({ identifier: identifier.trim(), password });
      await tokenStorage.save(data.access, data.refresh);
      const profileRes = await authService.getProfile();
      await authStore.login(data.access, data.refresh, profileRes.data);
    } catch (err: any) {
      const msg = err?.response?.data?.detail;
      if (err?.response?.status === 403) {
        setError('Account not verified. Check your email for a verification link.');
      } else {
        setError(msg || 'Invalid credentials. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  function handleGoogleSSO() {
    googlePKCERef.current = googleRequest
      ? { redirectUri: googleRequest.redirectUri, codeVerifier: googleRequest.codeVerifier }
      : null;
    promptGoogle();
  }
  function handleMicrosoftSSO() {
    msPKCERef.current = msRequest ? { codeVerifier: msRequest.codeVerifier } : null;
    promptMs();
  }

  return (
    <SafeAreaView style={s.safe}>
      {/* Decorative blobs */}
      <View style={[s.blob, s.blobBottomLeft]} />
      <View style={[s.blob, s.blobTopRight]} />

      <KeyboardAvoidingView
        style={s.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={s.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* ── Branding ─────────────────────────────────── */}
          <View style={s.brand}>
            <View style={s.iconWrap}>
              <Text style={s.iconSymbol}>home_work</Text>
            </View>
            <Text style={s.appName}>ChoreSync</Text>
            <Text style={s.tagline}>HOUSEHOLD HARMONY</Text>
          </View>

          {/* ── Form ─────────────────────────────────────── */}
          <View style={s.form}>

            {/* Email / Username */}
            <View style={s.inputWrap}>
              <Text style={s.inputIcon}>alternate_email</Text>
              <TextInput
                style={s.input}
                placeholder="Email or Username"
                placeholderTextColor="rgba(85,66,64,0.45)"
                value={identifier}
                onChangeText={setIdentifier}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                returnKeyType="next"
              />
            </View>

            {/* Password */}
            <View style={s.inputWrap}>
              <Text style={s.inputIcon}>lock</Text>
              <TextInput
                style={[s.input, s.inputFlex]}
                placeholder="Password"
                placeholderTextColor="rgba(85,66,64,0.45)"
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
                returnKeyType="done"
                onSubmitEditing={handleLogin}
              />
              <TouchableOpacity onPress={() => setShowPassword(!showPassword)} style={s.eyeBtn}>
                <Text style={s.eyeIcon}>{showPassword ? 'visibility_off' : 'visibility'}</Text>
              </TouchableOpacity>
            </View>

            {/* Forgot password */}
            <TouchableOpacity
              style={s.forgotWrap}
              onPress={() => navigation.navigate('ForgotPassword')}
            >
              <Text style={s.forgotText}>Forgot password?</Text>
            </TouchableOpacity>

            {/* Error */}
            {!!error && <Text style={s.errorText}>{error}</Text>}

            {/* Sign in button */}
            <TouchableOpacity onPress={handleLogin} disabled={loading} activeOpacity={0.88}>
              <LinearGradient
                colors={[C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={s.primaryBtn}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={s.primaryBtnText}>Sign In</Text>
                }
              </LinearGradient>
            </TouchableOpacity>

            {/* Divider */}
            <View style={s.divider}>
              <View style={s.dividerLine} />
              <Text style={s.dividerText}>or</Text>
              <View style={s.dividerLine} />
            </View>

            {/* Google */}
            <TouchableOpacity style={s.oauthBtn} onPress={handleGoogleSSO} activeOpacity={0.8} disabled={ssoLoading}>
              {ssoLoading
                ? <ActivityIndicator size="small" color={C.onSurface} />
                : <>
                    <Text style={s.googleLogo}>G</Text>
                    <Text style={s.oauthBtnText}>Continue with Google</Text>
                  </>
              }
            </TouchableOpacity>

            {/* Microsoft */}
            <TouchableOpacity style={s.oauthBtn} onPress={handleMicrosoftSSO} activeOpacity={0.8} disabled={ssoLoading}>
              <View style={s.msLogoWrap}>
                <View style={[s.msSquare, { backgroundColor: '#f25022' }]} />
                <View style={[s.msSquare, { backgroundColor: '#7fba00' }]} />
                <View style={[s.msSquare, { backgroundColor: '#00a4ef' }]} />
                <View style={[s.msSquare, { backgroundColor: '#ffb900' }]} />
              </View>
              <Text style={s.oauthBtnText}>Continue with Microsoft</Text>
            </TouchableOpacity>
          </View>

          {/* ── Footer ───────────────────────────────────── */}
          <View style={s.footer}>
            <Text style={s.footerText}>Don't have an account?</Text>
            <TouchableOpacity onPress={() => navigation.navigate('SignUp')}>
              <Text style={s.footerLink}> Sign up</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <LegalFooter />
    </SafeAreaView>
  );
}


const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 28,
    paddingVertical: 40,
    justifyContent: 'center',
  },

  // ── Decorative blobs ──────────────────────────────
  blob: {
    position: 'absolute',
    borderRadius: 999,
    opacity: 0.07,
  },
  blobBottomLeft: {
    bottom: -80, left: -80,
    width: 220, height: 220,
    backgroundColor: C.secondary,
  },
  blobTopRight: {
    top: 60, right: -40,
    width: 160, height: 160,
    backgroundColor: C.primary,
  },

  // ── Brand ─────────────────────────────────────────
  brand: { alignItems: 'center', marginBottom: 40 },
  iconWrap: {
    width: 72, height: 72,
    backgroundColor: C.primary,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 6,
  },
  iconSymbol: {
    fontFamily: 'MaterialSymbols',
    fontSize: 36,
    color: '#fff',
  },
  appName: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 28,
    color: C.primary,
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  tagline: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 10,
    color: 'rgba(85,66,64,0.6)',
    letterSpacing: 2,
  },

  // ── Form ──────────────────────────────────────────
  form: { gap: 14 },

  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.surfaceContainer,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
  },
  inputIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.onSurfaceVariant,
  },
  input: {
    flex: 1,
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 15,
    color: C.onSurface,
    padding: 0,
    margin: 0,
  },
  inputFlex: { flex: 1 },
  eyeBtn: { padding: 2 },
  eyeIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.onSurfaceVariant,
  },

  forgotWrap: { alignItems: 'flex-end', marginTop: -4 },
  forgotText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 13,
    color: C.primary,
  },

  errorText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.error,
    textAlign: 'center',
    marginTop: -4,
  },

  primaryBtn: {
    height: 52,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 12,
    elevation: 6,
  },
  primaryBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 16,
    color: '#fff',
    letterSpacing: 0.2,
  },

  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 4,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: 'rgba(218,193,189,0.35)' },
  dividerText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: 'rgba(85,66,64,0.55)',
  },

  oauthBtn: {
    height: 52,
    backgroundColor: C.surfaceContainerLowest,
    borderWidth: 1,
    borderColor: 'rgba(218,193,189,0.45)',
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  googleLogo: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 17,
    color: '#4285F4',
    width: 20,
    textAlign: 'center',
  },
  oauthBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 14,
    color: C.onSurface,
  },
  msLogoWrap: {
    width: 20, height: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 1.5,
  },
  msSquare: { width: 8.5, height: 8.5 },

  // ── Footer ────────────────────────────────────────
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 32,
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
