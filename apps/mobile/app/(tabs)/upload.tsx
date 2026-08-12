import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
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

import { colors } from '../../src/constants/theme';
import { api } from '../../src/lib/api';

export default function UploadScreen() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
    }
  };

  const submit = async () => {
    if (!title.trim()) {
      setError('Add a recipe title');
      return;
    }
    if (!imageUri) {
      setError('Choose a recipe photo');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setStatus('Creating recipe…');
      const moderated = await api.publishRecipe(
        title.trim(),
        description.trim() || undefined,
        imageUri,
      );
      if (moderated.status === 'published') {
        setStatus('Published!');
        setTitle('');
        setDescription('');
        setImageUri(null);
        router.push(`/recipe/${moderated.id}`);
      } else if (moderated.status === 'pending_review' || moderated.status === 'processing') {
        setStatus(
          moderated.status === 'processing'
            ? 'Uploaded — YOLO moderation queued.'
            : 'Sent to manual review — check the admin dashboard.',
        );
      } else {
        setStatus(`Status: ${moderated.status}`);
      }
    } catch (e: any) {
      setError(e.message || 'Upload failed');
      setStatus(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.screen} keyboardShouldPersistTaps="handled">
      <Text style={styles.heading}>Share a recipe</Text>
      <Text style={styles.sub}>Photos are moderated with YOLO before publishing.</Text>

      <Pressable style={styles.imagePicker} onPress={pickImage}>
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.preview} />
        ) : (
          <Text style={styles.pickerText}>Tap to choose a photo</Text>
        )}
      </Pressable>

      <Text style={styles.label}>Title</Text>
      <TextInput
        value={title}
        onChangeText={setTitle}
        style={styles.input}
        placeholder="Tomato basil pasta"
        placeholderTextColor={colors.muted}
      />
      <Text style={styles.label}>Short description</Text>
      <TextInput
        value={description}
        onChangeText={setDescription}
        style={[styles.input, styles.area]}
        multiline
        placeholder="A quick weeknight dish with blistered tomatoes."
        placeholderTextColor={colors.muted}
      />

      {status ? <Text style={styles.status}>{status}</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.button} onPress={submit} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Upload & moderate</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: 20, backgroundColor: colors.bg },
  heading: { fontSize: 28, fontWeight: '700', color: colors.ink, letterSpacing: -0.6 },
  sub: { marginTop: 6, marginBottom: 20, color: colors.muted },
  imagePicker: {
    height: 240,
    borderRadius: 8,
    backgroundColor: colors.accentSoft,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  preview: { width: '100%', height: '100%' },
  pickerText: { color: colors.accent, fontWeight: '600' },
  label: { marginTop: 16, marginBottom: 6, fontSize: 13, color: colors.muted },
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
  area: { minHeight: 96, textAlignVertical: 'top' },
  button: {
    marginTop: 20,
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  status: { marginTop: 12, color: colors.success },
  error: { marginTop: 12, color: colors.danger },
});
