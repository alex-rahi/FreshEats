const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET || 'placeholder-admin-secret';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': ADMIN_SECRET,
      ...(options.headers || {}),
    },
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Request failed');
  }
  return res.json();
}

export type AdminStats = {
  pending_reviews: number;
  published_today: number;
  rejected_today: number;
  total_recipes: number;
  total_users: number;
};

export type ReviewItem = {
  id: string;
  recipe_id: string;
  priority: number;
  review_status: string;
  detections: Array<{ label: string; confidence: number }>;
  moderation_scores: Array<{ category: string; score: number }>;
  recipe?: {
    id: string;
    title: string;
    description?: string;
    image_url?: string;
    author?: { username: string };
  };
  created_at?: string;
};

export const adminApi = {
  stats: () => request<AdminStats>('/admin/stats'),
  queue: () => request<ReviewItem[]>('/admin/review-queue'),
  decide: (reviewId: string, outcome: 'publish' | 'reject', notes?: string) =>
    request(`/admin/review/${reviewId}`, {
      method: 'POST',
      body: JSON.stringify({ outcome, notes }),
    }),
};

export function mediaUrl(path?: string | null) {
  if (!path) return null;
  if (path.startsWith('http')) return path;
  return `${API_URL}${path.startsWith('/') ? '' : '/'}${path}`;
}
