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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { AuthStackParamList } from '../../navigation/types';
import { authService } from '../../services/authService';
import { Palette as C } from '../../theme';

type Nav = NativeStackNavigationProp<AuthStackParamList, 'ForgotPassword'>;

export default function ForgotPasswordScreen() {
  const navigation = useNavigation<Nav>();

  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  async function handleSend() {
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await authService.forgotPassword(email.trim());
      setSent(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Something went wrong. Please try again.');
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
        <TouchableOpacity
          style={s.backBtn}
          onPress={() => navigation.goBack()}
          activeOpacity={0.8}
        >
          <Text style={s.backIcon}>arrow_back</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>Reset Password</Text>
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
          {/* Icon */}
          <View style={s.iconWrap}>
            <Text style={s.iconSymbol}>lock_reset</Text>
          </View>

          {/* Headline */}
          <View style={s.headlineWrap}>
            <Text style={s.headline}>Forgot password?</Text>
            <Text style={s.subtitle}>
              Enter your email and we'll send{'\n'}a reset link.
            </Text>
          </View>

          {/* Form */}
          <View style={s.form}>
            {/* Email input */}
            <View style={s.inputWrap}>
              <Text style={s.inputIcon}>alternate_email</Text>
              <TextInput
                style={s.input}
                placeholder="Email address"
                placeholderTextColor="rgba(85,66,64,0.45)"
                value={email}
                onChangeText={text => {
                  setEmail(text);
                  if (sent) setSent(false);
                  if (error) setError('');
                }}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                returnKeyType="send"
                onSubmitEditing={handleSend}
                editable={!sent}
              />
            </View>

            {/* Error */}
            {!!error && <Text style={s.errorText}>{error}</Text>}

            {/* Success banner */}
            {sent && (
              <View style={s.successBanner}>
                <Text style={s.successIcon}>check_circle</Text>
                <Text style={s.successText}>Reset link sent — check your inbox</Text>
              </View>
            )}

            {/* Send button */}
            <TouchableOpacity
              onPress={handleSend}
              disabled={loading || sent}
              activeOpacity={0.88}
            >
              <LinearGradient
                colors={sent ? [C.disabledStart, C.disabledEnd] : [C.primary, C.primaryContainer]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={s.primaryBtn}
              >
                {loading
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={s.primaryBtnText}>
                      {sent ? 'Link sent' : 'Send reset link'}
                    </Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>

          {/* Footer */}
          <View style={s.footer}>
            <TouchableOpacity
              onPress={() => navigation.navigate('Login')}
              activeOpacity={0.7}
              style={s.backToSignIn}
            >
              <Text style={s.backArrowIcon}>arrow_back</Text>
              <Text style={s.footerLink}>Back to Sign In</Text>
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

  // ── Blobs ───────────────────────────────────────
  blob: {
    position: 'absolute',
    borderRadius: 999,
    opacity: 0.3,
  },
  blobTopRight: {
    top: -80, right: -80,
    width: 220, height: 220,
    backgroundColor: C.primaryFixed,
  },
  blobBottomLeft: {
    bottom: -100, left: -100,
    width: 280, height: 280,
    backgroundColor: C.secondaryContainer,
    opacity: 0.2,
  },

  // ── Header ──────────────────────────────────────
  header: {
    flexDirection: 'row',
    alignItems: 'center',
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
  headerTitle: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 18,
    color: C.onSurface,
    marginLeft: 14,
  },

  // ── Scroll content ──────────────────────────────
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 28,
    paddingBottom: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // ── Icon ────────────────────────────────────────
  iconWrap: {
    width: 80, height: 80,
    backgroundColor: C.primaryFixed,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  iconSymbol: {
    fontFamily: 'MaterialSymbols',
    fontSize: 40,
    color: C.primary,
  },

  // ── Headline ────────────────────────────────────
  headlineWrap: {
    alignItems: 'center',
    marginBottom: 32,
  },
  headline: {
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 26,
    color: '#1e1b18',
    letterSpacing: -0.5,
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 14,
    color: '#837570',
    textAlign: 'center',
    lineHeight: 20,
  },

  // ── Form ────────────────────────────────────────
  form: {
    width: '100%',
    gap: 14,
  },

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

  errorText: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13,
    color: C.error,
    textAlign: 'center',
  },

  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.secondaryContainer,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 10,
  },
  successIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 20,
    color: C.secondary,
  },
  successText: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 13,
    color: C.secondary,
    flex: 1,
  },

  primaryBtn: {
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: C.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 5,
  },
  primaryBtnText: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 16,
    color: '#fff',
    letterSpacing: 0.2,
  },

  // ── Footer ──────────────────────────────────────
  footer: {
    marginTop: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backToSignIn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  backArrowIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 14,
    color: C.primary,
  },
  footerLink: {
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 13,
    color: C.primary,
  },
});
