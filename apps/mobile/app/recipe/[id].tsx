import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useAuth } from '../../src/context/AuthContext';
import { colors, Comment, Recipe } from '../../src/constants/theme';
import { ModerationRulesPanel } from '../../src/components/ModerationRulesPanel';
import { api, mediaUrl } from '../../src/lib/api';

export default function RecipeDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!id) return;
    try {
      const [r, c] = await Promise.all([api.getRecipe(id), api.getComments(id)]);
      setRecipe(r);
      setComments(c);
    } catch (e: any) {
      setError(e.message || 'Failed to load recipe');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const toggleLike = async () => {
    if (!recipe) return;
    const updated = recipe.liked_by_me
      ? await api.unlikeRecipe(recipe.id)
      : await api.likeRecipe(recipe.id);
    setRecipe(updated);
  };

  const addComment = async () => {
    if (!recipe || !text.trim()) return;
    const comment = await api.addComment(recipe.id, text.trim());
    setComments((prev) => [...prev, comment]);
    setRecipe({ ...recipe, comment_count: recipe.comment_count + 1 });
    setText('');
  };

  const removeComment = async (commentId: string) => {
    if (!recipe) return;
    await api.deleteComment(commentId);
    setComments((prev) => prev.filter((c) => c.id !== commentId));
    setRecipe({ ...recipe, comment_count: Math.max(recipe.comment_count - 1, 0) });
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (!recipe) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error || 'Recipe not found'}</Text>
      </View>
    );
  }

  const imageUrl = mediaUrl(recipe.image_url);

  return (
    <ScrollView contentContainerStyle={styles.screen}>
      {imageUrl ? <Image source={{ uri: imageUrl }} style={styles.hero} resizeMode="cover" /> : null}
      <Text style={styles.title}>{recipe.title}</Text>
      <Text style={styles.author}>@{recipe.author?.username || 'cook'}</Text>
      {recipe.description ? <Text style={styles.description}>{recipe.description}</Text> : null}

      <View style={styles.actions}>
        <Pressable style={styles.likeBtn} onPress={toggleLike}>
          <Text style={styles.likeText}>
            {recipe.liked_by_me ? '♥ Liked' : '♡ Like'} · {recipe.like_count}
          </Text>
        </Pressable>
        <Text style={styles.commentCount}>{recipe.comment_count} comments</Text>
      </View>

      <ModerationRulesPanel
        rules={recipe.moderation_rules}
        decision={recipe.moderation_decision}
        reason={recipe.moderation_reason}
        whatHappens={recipe.what_happens}
        labels={recipe.detection_labels}
      />

      <Text style={styles.section}>Comments</Text>
      {comments.map((c) => (
        <View key={c.id} style={styles.comment}>
          <View style={{ flex: 1 }}>
            <Text style={styles.commentAuthor}>@{c.author?.username || 'cook'}</Text>
            <Text style={styles.commentBody}>{c.content}</Text>
          </View>
          {user?.id === c.user_id ? (
            <Pressable onPress={() => removeComment(c.id)}>
              <Text style={styles.delete}>Delete</Text>
            </Pressable>
          ) : null}
        </View>
      ))}

      <View style={styles.composer}>
        <TextInput
          value={text}
          onChangeText={setText}
          style={styles.input}
          placeholder="Add a comment"
          placeholderTextColor={colors.muted}
        />
        <Pressable style={styles.send} onPress={addComment}>
          <Text style={styles.sendText}>Post</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  screen: { paddingBottom: 40, backgroundColor: colors.bg },
  hero: { width: '100%', aspectRatio: 1, backgroundColor: colors.line },
  title: {
    marginTop: 16,
    marginHorizontal: 16,
    fontSize: 28,
    fontWeight: '700',
    color: colors.ink,
    letterSpacing: -0.6,
  },
  author: { marginHorizontal: 16, marginTop: 6, color: colors.muted },
  description: { marginHorizontal: 16, marginTop: 12, fontSize: 16, lineHeight: 24, color: colors.ink },
  actions: {
    marginTop: 18,
    marginHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  likeBtn: {
    backgroundColor: colors.accentSoft,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  likeText: { color: colors.accent, fontWeight: '700' },
  commentCount: { color: colors.muted },
  section: {
    marginTop: 28,
    marginHorizontal: 16,
    marginBottom: 10,
    fontSize: 18,
    fontWeight: '700',
    color: colors.ink,
  },
  comment: {
    marginHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    gap: 12,
  },
  commentAuthor: { fontWeight: '600', color: colors.ink, marginBottom: 4 },
  commentBody: { color: colors.ink, lineHeight: 20 },
  delete: { color: colors.danger, fontSize: 12, fontWeight: '600' },
  composer: {
    marginTop: 16,
    marginHorizontal: 16,
    flexDirection: 'row',
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.ink,
  },
  send: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingHorizontal: 16,
    justifyContent: 'center',
  },
  sendText: { color: '#fff', fontWeight: '700' },
  error: { color: colors.danger },
});
