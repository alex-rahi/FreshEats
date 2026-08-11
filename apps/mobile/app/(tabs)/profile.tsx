import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { RecipeCard } from '../../src/components/RecipeCard';
import { useAuth } from '../../src/context/AuthContext';
import { colors, Recipe } from '../../src/constants/theme';
import { api } from '../../src/lib/api';

export default function ProfileScreen() {
  const { user, profile, signOut, refreshProfile } = useAuth();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [bio, setBio] = useState(profile?.bio || '');
  const [displayName, setDisplayName] = useState(profile?.display_name || '');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!user) return;
    try {
      await refreshProfile();
      const items = await api.getUserRecipes(user.id);
      setRecipes(items);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      setBio(profile?.bio || '');
      setDisplayName(profile?.display_name || profile?.username || '');
      load();
    }, [user?.id]),
  );

  const save = async () => {
    setSaving(true);
    try {
      await api.updateProfile({ bio, display_name: displayName });
      await refreshProfile();
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <FlatList
      data={recipes}
      numColumns={2}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      columnWrapperStyle={styles.row}
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.name}>{profile?.display_name || profile?.username || 'Cook'}</Text>
          <Text style={styles.handle}>@{profile?.username || 'you'}</Text>
          <Text style={styles.count}>{profile?.recipe_count ?? recipes.length} recipes</Text>

          <Text style={styles.label}>Display name</Text>
          <TextInput value={displayName} onChangeText={setDisplayName} style={styles.input} />
          <Text style={styles.label}>Bio</Text>
          <TextInput
            value={bio}
            onChangeText={setBio}
            style={[styles.input, styles.area]}
            multiline
            placeholder="What do you like to cook?"
            placeholderTextColor={colors.muted}
          />
          <Pressable style={styles.button} onPress={save} disabled={saving}>
            <Text style={styles.buttonText}>{saving ? 'Saving…' : 'Save profile'}</Text>
          </Pressable>
          <Pressable
            style={styles.logout}
            onPress={async () => {
              await signOut();
              router.replace('/(auth)/login');
            }}
          >
            <Text style={styles.logoutText}>Log out</Text>
          </Pressable>
          <Text style={styles.section}>Your recipes</Text>
        </View>
      }
      ListEmptyComponent={<Text style={styles.empty}>No published recipes yet.</Text>}
      renderItem={({ item }) => (
        <RecipeCard recipe={item} onPress={() => router.push(`/recipe/${item.id}`)} />
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  list: { padding: 16, backgroundColor: colors.bg },
  row: { gap: 12 },
  header: { marginBottom: 12 },
  name: { fontSize: 28, fontWeight: '700', color: colors.ink, letterSpacing: -0.6 },
  handle: { marginTop: 4, color: colors.muted },
  count: { marginTop: 8, color: colors.ink, fontWeight: '600' },
  label: { marginTop: 14, marginBottom: 6, fontSize: 13, color: colors.muted },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.ink,
  },
  area: { minHeight: 72, textAlignVertical: 'top' },
  button: {
    marginTop: 14,
    backgroundColor: colors.ink,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  buttonText: { color: '#fff', fontWeight: '600' },
  logout: { marginTop: 12, alignItems: 'center', paddingVertical: 8 },
  logoutText: { color: colors.danger, fontWeight: '600' },
  section: { marginTop: 24, marginBottom: 8, fontSize: 18, fontWeight: '700', color: colors.ink },
  empty: { color: colors.muted, marginBottom: 20 },
});
