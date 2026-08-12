import { Link, router } from 'expo-router';
import { useState } from 'react';
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

export default function SignUpScreen() {
  const { signUp } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    if (!username.trim()) {
      setError('Choose a username');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signUp(email.trim(), password, username.trim());
      router.replace('/(tabs)/grid');
    } catch (e: any) {
      setError(e.message || 'Sign up failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.title}>Create your profile</Text>
      <Text style={styles.sub}>Join FreshEats and start sharing dishes.</Text>

      <Text style={styles.label}>Username</Text>
      <TextInput
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
        style={styles.input}
        placeholder="home_cook"
        placeholderTextColor={colors.muted}
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
      />
      <Text style={styles.label}>Password</Text>
      <TextInput
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        style={styles.input}
        placeholder="••••••••"
        placeholderTextColor={colors.muted}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable style={styles.button} onPress={onSubmit} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign up</Text>}
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
  sub: { marginTop: 8, marginBottom: 24, color: colors.muted, fontSize: 15 },
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
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  footer: { marginTop: 18, textAlign: 'center', color: colors.muted },
  link: { color: colors.accent, fontWeight: '600' },
  error: { color: colors.danger, marginTop: 8 },
});
