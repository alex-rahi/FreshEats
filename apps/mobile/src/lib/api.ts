import { API_URL, Comment, isDemoMode, isLocalYoloMode, Profile, Recipe } from '../constants/theme';
import { CDN_URL, getAccessToken, isCognitoMode } from './cognito';

const PLACEHOLDER_TOKEN = 'placeholder-access-token';
const UPLOAD_MAX_EDGE = 2048;
const UPLOAD_JPEG_QUALITY = 0.92;
/** Sample flat-lay framing (~485×297). width / height */
export const SAMPLE_UPLOAD_ASPECT = 485 / 297;

function sampleCropRect(srcW: number, srcH: number) {
  const target = SAMPLE_UPLOAD_ASPECT;
  const src = srcW / srcH;
  if (src > target) {
    const cropW = Math.round(srcH * target);
    return { sx: Math.round((srcW - cropW) / 2), sy: 0, sw: cropW, sh: srcH };
  }
  const cropH = Math.round(srcW / target);
  return { sx: 0, sy: Math.round((srcH - cropH) / 2), sw: srcW, sh: cropH };
}

/** Center-crop to the sample landscape frame, then encode a sharp JPEG. */
async function formatImageForUpload(uri: string): Promise<{ blob: Blob; fileName: string; type: string }> {
  if (typeof document === 'undefined') {
    const res = await fetch(uri);
    if (!res.ok) throw new Error('Could not read selected image');
    const blob = await res.blob();
    const type = blob.type && blob.type !== 'application/octet-stream' ? blob.type : 'image/jpeg';
    return {
      blob,
      type,
      fileName: type.includes('png') ? 'recipe.png' : 'recipe.jpg',
    };
  }

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new window.Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error('Could not decode selected image'));
    el.src = uri;
  });

  const srcW = img.naturalWidth || img.width;
  const srcH = img.naturalHeight || img.height;
  const { sx, sy, sw, sh } = sampleCropRect(srcW, srcH);

  const scale = Math.min(1, UPLOAD_MAX_EDGE / Math.max(sw, sh));
  const width = Math.max(1, Math.round(sw * scale));
  const height = Math.max(1, Math.round(sh * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not process image');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, width, height);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error('Could not encode image'))),
      'image/jpeg',
      UPLOAD_JPEG_QUALITY,
    );
  });

  return { blob, fileName: 'recipe.jpg', type: 'image/jpeg' };
}

type CreateRecipeResult =
  | Recipe
  | {
      recipe: Recipe;
      upload_url?: string;
      storage_path?: string;
      job_id?: string;
    };

class ApiClient {
  private async getToken(): Promise<string | null> {
    if (isDemoMode() || isLocalYoloMode()) return PLACEHOLDER_TOKEN;
    if (isCognitoMode()) return getAccessToken();
    return null;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = await this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    if (token) headers.Authorization = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/v1${path}`, { ...options, headers });
    } catch {
      throw new Error(`Cannot reach API at ${API_URL}. Is the backend running on port 8000?`);
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const detail = err.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.message
            ? detail.message
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(', ')
              : res.statusText;
      throw new Error(message || 'Request failed');
    }
    if (res.status === 204) return undefined as T;
    return res.json();
  }

  getProfile = () => this.request<Profile>('/profiles/me');

  updateProfile = (data: Partial<Profile>) =>
    this.request<Profile>('/profiles/me', { method: 'PATCH', body: JSON.stringify(data) });

  getRecipes = async () => {
    const data = await this.request<{ items: Recipe[] }>('/recipes');
    return data.items;
  };

  getModerationHealth = () =>
    this.request<{
      enabled: boolean;
      engine?: string;
      mode?: string;
      status?: string;
      detail?: string;
      pipeline?: string[];
      detects?: string[];
      local_yolo?: boolean;
      placeholder_mode?: boolean;
      worker?: { status?: string; model_ready?: boolean; error?: string } | null;
    }>('/moderation/health');

  getRecipe = (id: string) => this.request<Recipe>(`/recipes/${id}`);

  getUserRecipes = (userId: string) => this.request<Recipe[]>(`/recipes/user/${userId}`);

  createRecipe = (title: string, description?: string) =>
    this.request<CreateRecipeResult>('/recipes', {
      method: 'POST',
      body: JSON.stringify({ title, description }),
    });

  confirmUpload = (recipeId: string) =>
    this.request<Recipe>(`/recipes/${recipeId}/confirm-upload`, { method: 'POST' });

  uploadRecipeImage = async (recipeId: string, uri: string, fileName = 'recipe.jpg') => {
    const form = new FormData();
    try {
      const isWebUri =
        typeof window !== 'undefined' &&
        (uri.startsWith('blob:') || uri.startsWith('data:') || uri.startsWith('http'));

      if (isWebUri) {
        const { blob, fileName: name, type } = await formatImageForUpload(uri);
        try {
          form.append('file', blob, name);
        } catch {
          form.append('file', new File([blob], name, { type }));
        }
      } else {
        form.append('file', {
          uri,
          name: fileName,
          type: 'image/jpeg',
        } as any);
      }
    } catch (e: any) {
      const msg = e?.message || String(e);
      if (/Load failed|Failed to fetch|NetworkError/i.test(msg)) {
        throw new Error(`Cannot reach API at ${API_URL}. Is the backend running on port 8000?`);
      }
      throw new Error(msg || 'Could not prepare image for upload');
    }

    return this.request<Recipe>(`/moderation/recipes/${recipeId}/upload`, {
      method: 'POST',
      body: form,
      headers: {},
    });
  };

  uploadToPresignedUrl = async (uploadUrl: string, uri: string) => {
    const { blob, type } = await formatImageForUpload(uri);
    const put = await fetch(uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': type },
      body: blob,
    });
    if (!put.ok) {
      throw new Error(`S3 upload failed (${put.status})`);
    }
  };

  /**
   * Demo/local: multipart + sync YOLO.
   * AWS: create → PUT presigned → confirm-upload (SQS).
   */
  publishRecipe = async (title: string, description: string | undefined, imageUri: string) => {
    const created = await this.createRecipe(title, description);

    if (isCognitoMode() && created && typeof created === 'object' && 'recipe' in created) {
      const { recipe, upload_url } = created;
      if (!upload_url) throw new Error('Missing presigned upload URL');
      await this.uploadToPresignedUrl(upload_url, imageUri);
      return this.confirmUpload(recipe.id);
    }

    const recipe = created as Recipe;
    await this.uploadRecipeImage(recipe.id, imageUri);
    return this.runModeration(recipe.id);
  };

  runModeration = (recipeId: string) =>
    this.request<Recipe>(`/moderation/recipes/${recipeId}/run`, { method: 'POST' });

  likeRecipe = (recipeId: string) =>
    this.request<Recipe>(`/recipes/${recipeId}/like`, { method: 'POST' });

  unlikeRecipe = (recipeId: string) =>
    this.request<Recipe>(`/recipes/${recipeId}/like`, { method: 'DELETE' });

  getComments = (recipeId: string) => this.request<Comment[]>(`/recipes/${recipeId}/comments`);

  addComment = (recipeId: string, content: string) =>
    this.request<Comment>(`/recipes/${recipeId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });

  deleteComment = (commentId: string) =>
    this.request<void>(`/comments/${commentId}`, { method: 'DELETE' });
}

export const api = new ApiClient();

export function mediaUrl(path?: string | null) {
  if (!path) return null;
  if (path.startsWith('http')) return path;
  if (CDN_URL && !path.startsWith('/')) {
    return `${CDN_URL.replace(/\/$/, '')}/${path}`;
  }
  return `${API_URL}${path.startsWith('/') ? '' : '/'}${path}`;
}
