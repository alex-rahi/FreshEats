import { Link, router } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useAuth } from '../../src/context/AuthContext';
import { colors } from '../../src/constants/theme';
import { api } from '../../src/lib/api';

type SignupStatus = {
  limit: number;
  count: number;
  remaining: number;
  open: boolean;
};

export default function SignUpScreen() {
  const { signUp } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<SignupStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await api.getSignupStatus();
        if (!cancelled) setStatus(s);
      } catch (e: any) {
        if (!cancelled) setStatusError(e.message || 'Could not load signup capacity');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = async () => {
    if (!username.trim()) {
      setError('Choose a username');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (status && !status.open) {
      setError(`Private beta is full (${status.limit} users max).`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signUp(email.trim(), password, username.trim());
      router.replace('/(tabs)/grid');
    } catch (e: any) {
      setError(e.message || 'Sign up failed');
      try {
        setStatus(await api.getSignupStatus());
      } catch {
        // ignore
      }
    } finally {
      setBusy(false);
    }
  };

  const full = status ? !status.open : false;

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.title}>Create your profile</Text>
      <Text style={styles.sub}>Join FreshEats and start sharing dishes.</Text>

      {status ? (
        <View style={[styles.badge, full ? styles.badgeFull : styles.badgeOpen]}>
          <Text style={styles.badgeText}>
            {full
              ? `Private beta full — ${status.limit} of ${status.limit} users`
              : `Private beta — ${status.remaining} of ${status.limit} spots left`}
          </Text>
        </View>
      ) : statusError ? (
        <Text style={styles.warn}>{statusError}</Text>
      ) : (
        <Text style={styles.meta}>Checking available spots…</Text>
      )}

      <Text style={styles.label}>Username</Text>
      <TextInput
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
        style={styles.input}
        placeholder="home_cook"
        placeholderTextColor={colors.muted}
        editable={!full}
      />
      <Text style={styles.label}>Email</Text>
      <TextInput
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        style={styles.input}
        placeholder="you@email.com"
        placeholderTextColor={colors.muted}
        editable={!full}
      />
      <Text style={styles.label}>Password</Text>
      <TextInput
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        style={styles.input}
        placeholder="e.g. FreshEats1"
        placeholderTextColor={colors.muted}
        editable={!full}
      />
      <Text style={styles.hint}>At least 8 characters, with upper, lower, and a number.</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable
        style={[styles.button, (busy || full) && styles.buttonDisabled]}
        onPress={onSubmit}
        disabled={busy || full}
      >
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>{full ? 'Beta full' : 'Sign up'}</Text>
        )}
      </Pressable>
      <Text style={styles.footer}>
        Already have an account?{' '}
        <Link href="/(auth)/login" style={styles.link}>
          Log in
        </Link>
      </Text>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 24, justifyContent: 'center' },
  title: { fontSize: 32, fontWeight: '700', color: colors.ink, letterSpacing: -0.8 },
  sub: { marginTop: 8, marginBottom: 16, color: colors.muted, fontSize: 15 },
  badge: {
    marginBottom: 16,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  badgeOpen: { backgroundColor: '#E8F5E9' },
  badgeFull: { backgroundColor: '#FCE8E6' },
  badgeText: { fontSize: 13, fontWeight: '600', color: colors.ink },
  meta: { marginBottom: 12, color: colors.muted, fontSize: 13 },
  warn: { marginBottom: 12, color: colors.danger, fontSize: 13 },
  hint: { marginTop: 6, fontSize: 12, color: colors.muted },
  label: { fontSize: 13, color: colors.muted, marginTop: 8 },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.ink,
  },
  button: {
    marginTop: 16,
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.55 },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  footer: { marginTop: 18, textAlign: 'center', color: colors.muted },
  link: { color: colors.accent, fontWeight: '600' },
  error: { color: colors.danger, marginTop: 8 },
});
