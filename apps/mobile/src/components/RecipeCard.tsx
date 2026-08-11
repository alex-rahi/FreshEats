import React from 'react';
import {
  Image,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { colors, Recipe } from '../constants/theme';
import { mediaUrl } from '../lib/api';

type Props = {
  recipe: Recipe;
  onPress: () => void;
};

export function RecipeCard({ recipe, onPress }: Props) {
  const { width } = useWindowDimensions();
  const columns = width >= 1100 ? 4 : width >= 800 ? 3 : 2;
  const gap = 12;
  const horizontalPad = 16;
  const cardWidth = (width - horizontalPad * 2 - gap * (columns - 1)) / columns;
  const imageUrl = mediaUrl(recipe.image_url);

  return (
    <Pressable onPress={onPress} style={[styles.card, { width: cardWidth }]}>
      <View style={styles.imageWrap}>
        {imageUrl ? (
          <Image source={{ uri: imageUrl }} style={styles.image} />
        ) : (
          <View style={[styles.image, styles.placeholder]}>
            <Text style={styles.placeholderText}>No image</Text>
          </View>
        )}
      </View>
      <Text style={styles.title} numberOfLines={2}>
        {recipe.title}
      </Text>
      <Text style={styles.meta} numberOfLines={1}>
        @{recipe.author?.username || 'cook'} · ♥ {recipe.like_count} · 💬 {recipe.comment_count}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    marginBottom: 18,
  },
  imageWrap: {
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: colors.line,
  },
  image: {
    width: '100%',
    aspectRatio: 0.85,
  },
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  placeholderText: {
    color: colors.muted,
    fontSize: 13,
  },
  title: {
    marginTop: 8,
    fontSize: 15,
    fontWeight: '600',
    color: colors.ink,
    letterSpacing: -0.2,
  },
  meta: {
    marginTop: 3,
    fontSize: 12,
    color: colors.muted,
  },
});
