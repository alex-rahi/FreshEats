import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { RecipeCard } from '../../src/components/RecipeCard';
import { colors, Recipe } from '../../src/constants/theme';
import { api } from '../../src/lib/api';

export default function GridScreen() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { width } = useWindowDimensions();
  const columns = width >= 1100 ? 4 : width >= 800 ? 3 : 2;

  const load = async () => {
    try {
      const items = await api.getRecipes();
      setRecipes(items);
    } catch (e) {
      console.warn(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      load();
    }, []),
  );

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
      key={columns}
      numColumns={columns}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      columnWrapperStyle={columns > 1 ? styles.row : undefined}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
      ListEmptyComponent={<Text style={styles.empty}>No recipes yet. Upload the first dish.</Text>}
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
  empty: { textAlign: 'center', color: colors.muted, marginTop: 40 },
});
