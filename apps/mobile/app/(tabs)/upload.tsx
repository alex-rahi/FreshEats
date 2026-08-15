import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import { ModerationRulesPanel } from '../../src/components/ModerationRulesPanel';
import { colors, ModerationRule, Recipe } from '../../src/constants/theme';
import { api, SAMPLE_UPLOAD_ASPECT } from '../../src/lib/api';

type ModerationHealth = {
  enabled: boolean;
  engine?: string;
  mode?: string;
  status?: string;
  detail?: string;
  pipeline?: string[];
  detects?: string[];
  rules?: ModerationRule[];
  worker?: { status?: string; model_ready?: boolean; error?: string } | null;
};

function previewBoxWidth(screenWidth: number) {
  const content = screenWidth - 40;
  if (screenWidth >= 1100) return Math.min(content, 520);
  if (screenWidth >= 800) return Math.min(content, 460);
  if (screenWidth >= 600) return Math.min(content, 400);
  return content;
}

function statusColor(status?: string) {
  if (status === 'ready') return colors.success;
  if (status === 'unreachable' || status === 'disabled') return colors.danger;
  return colors.accent;
}

export default function UploadScreen() {
  const { width: screenWidth } = useWindowDimensions();
  const boxWidth = previewBoxWidth(screenWidth);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState<ModerationHealth | null>(null);
  const [lastResult, setLastResult] = useState<Recipe | null>(null);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      api
        .getModerationHealth()
        .then((h) => {
          if (active) setEngine(h);
        })
        .catch(() => {
          if (active) {
            setEngine({
              enabled: false,
              engine: 'YOLOv8',
              mode: 'off',
              status: 'unreachable',
              detail: 'Cannot reach moderation API.',
            });
          }
        });
      return () => {
        active = false;
      };
    }, []),
  );

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
      setLastResult(null);
    }
  };

  const submit = async () => {
    if (!title.trim()) {
      setError('Add a recipe title');
      return;
    }
    if (!imageUri) {
      setError('Choose a recipe photo first (tap the image area above)');
      return;
    }
    setBusy(true);
    setError(null);
    setLastResult(null);
    try {
      setStatus('Running YOLO moderation…');
      const moderated = await api.publishRecipe(
        title.trim(),
        description.trim() || undefined,
        imageUri,
      );
      setLastResult(moderated);

      if (moderated.status === 'published') {
        setStatus('Published!');
        setTitle('');
        setDescription('');
        setImageUri(null);
        router.replace('/(tabs)/grid');
      } else if (moderated.status === 'rejected') {
        setStatus('Rejected — food only. Not published.');
      } else if (moderated.status === 'pending_review' || moderated.status === 'processing') {
        setStatus(
          moderated.status === 'processing'
            ? 'Uploaded — YOLO moderation queued.'
            : 'Held for manual review — not on the grid yet.',
        );
      } else {
        setStatus(`Status: ${moderated.status}`);
      }
    } catch (e: any) {
      console.error('Upload failed', e);
      setError(e.message || 'Upload failed');
      setStatus(null);
    } finally {
      setBusy(false);
    }
  };

  const modeLabel =
    engine?.mode === 'live' ? 'Live worker' : engine?.mode === 'demo' ? 'Demo engine' : 'Offline';

  const catalogRules: ModerationRule[] = (engine?.rules || []).map((r) => ({
    ...r,
    outcome: 'catalog',
  }));

  return (
    <ScrollView contentContainerStyle={styles.screen} keyboardShouldPersistTaps="handled">
      <Text style={styles.heading}>Share a recipe</Text>
      <Text style={styles.sub}>YOLO moderation is food only — non-food photos are rejected.</Text>

      <View style={styles.engine}>
        <View style={styles.engineHeader}>
          <Text style={styles.engineTitle}>{engine?.engine || 'YOLOv8'} · Food only</Text>
          <Text style={[styles.engineBadge, { color: statusColor(engine?.status) }]}>
            {engine ? `${modeLabel} · ${engine.status || '…'}` : 'Checking…'}
          </Text>
        </View>
        <Text style={styles.engineBody}>
          {engine?.detail ||
            'Food only: detect plated food or ingredients, then publish or reject.'}
        </Text>
        {engine?.pipeline?.length ? (
          <Text style={styles.engineMeta}>Pipeline: {engine.pipeline.join(' → ')}</Text>
        ) : null}
        {engine?.detects?.length ? (
          <Text style={styles.engineMeta}>Looks for: {engine.detects.join(', ')}</Text>
        ) : null}
      </View>

      {catalogRules.length ? (
        <ModerationRulesPanel
          compact
          rules={catalogRules}
          whatHappens="Food only: if YOLO does not see food, the post is rejected and never appears on the grid."
        />
      ) : null}

      <Pressable style={[styles.imagePicker, { width: boxWidth }]} onPress={pickImage}>
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.preview} resizeMode="cover" />
        ) : (
          <Text style={styles.pickerText}>Tap to choose a photo</Text>
        )}
      </Pressable>

      <Text style={styles.hint}>
        Try failing samples in demo-fail-images/: fail-cellphone.jpg, fail-car.jpg, fail-laptop.jpg, fail-blank.jpg
      </Text>

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

      {lastResult && lastResult.status !== 'published' ? (
        <ModerationRulesPanel
          compact
          rules={lastResult.moderation_rules}
          decision={lastResult.moderation_decision}
          reason={lastResult.moderation_reason}
          whatHappens={lastResult.what_happens}
          labels={lastResult.detection_labels}
        />
      ) : null}

      <Pressable style={styles.button} onPress={submit} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Upload & moderate</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: 20, backgroundColor: colors.bg, paddingBottom: 40 },
  heading: { fontSize: 28, fontWeight: '700', color: colors.ink, letterSpacing: -0.6 },
  sub: { marginTop: 6, marginBottom: 16, color: colors.muted },
  engine: {
    marginBottom: 16,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  engineHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap',
  },
  engineTitle: { fontSize: 15, fontWeight: '700', color: colors.ink },
  engineBadge: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  engineBody: { marginTop: 8, fontSize: 14, lineHeight: 20, color: colors.ink },
  engineMeta: { marginTop: 6, fontSize: 12, lineHeight: 18, color: colors.muted },
  imagePicker: {
    alignSelf: 'center',
    aspectRatio: SAMPLE_UPLOAD_ASPECT,
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
  hint: { marginTop: 10, marginBottom: 4, fontSize: 12, color: colors.muted, lineHeight: 17 },
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
