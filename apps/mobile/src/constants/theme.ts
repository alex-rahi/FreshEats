import { Platform } from 'react-native';

export const colors = {
  bg: '#F7F3EE',
  surface: '#FFFFFF',
  ink: '#1A1714',
  muted: '#6B635B',
  line: '#E6DED4',
  accent: '#C45C26',
  accentSoft: '#F3E0D4',
  success: '#2F6B4F',
  danger: '#B42318',
  like: '#C45C26',
};

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000');

export function isDemoMode() {
  return process.env.EXPO_PUBLIC_USE_PLACEHOLDERS === 'true';
}

export function isLocalYoloMode() {
  return process.env.EXPO_PUBLIC_USE_LOCAL_YOLO === 'true';
}

export const PLACEHOLDER_USER_ID = '00000000-0000-4000-8000-000000000001';

export type Recipe = {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  status: string;
  like_count: number;
  comment_count: number;
  liked_by_me?: boolean;
  image_url?: string | null;
  author?: {
    id: string;
    username: string;
    display_name?: string | null;
    avatar_url?: string | null;
    bio?: string | null;
    recipe_count?: number;
  };
  created_at?: string;
  detection_labels?: string[];
};

export type Comment = {
  id: string;
  recipe_id: string;
  user_id: string;
  content: string;
  author?: { id: string; username: string; display_name?: string | null };
  created_at?: string;
};

export type Profile = {
  id: string;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
  recipe_count?: number;
};
