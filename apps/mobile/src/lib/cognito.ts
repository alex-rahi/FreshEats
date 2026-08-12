import { API_URL, isDemoMode, isLocalYoloMode } from '../constants/theme';

export const COGNITO_USER_POOL_ID = process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID || '';
export const COGNITO_CLIENT_ID = process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID || '';
export const AWS_REGION = process.env.EXPO_PUBLIC_AWS_REGION || 'us-east-1';
export const CDN_URL = process.env.EXPO_PUBLIC_CDN_URL || '';

export function isCognitoMode() {
  return Boolean(COGNITO_USER_POOL_ID && COGNITO_CLIENT_ID) && !isDemoMode() && !isLocalYoloMode();
}

type CognitoTokens = {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresAt: number;
  email: string;
  sub: string;
};

const TOKEN_KEY = 'fresheats.cognito.tokens';

async function storageGet(key: string) {
  try {
    const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
    return AsyncStorage.getItem(key);
  } catch {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key);
    return null;
  }
}

async function storageSet(key: string, value: string) {
  try {
    const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
    await AsyncStorage.setItem(key, value);
  } catch {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, value);
  }
}

async function storageRemove(key: string) {
  try {
    const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
    await AsyncStorage.removeItem(key);
  } catch {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(key);
  }
}

function cognitoEndpoint() {
  return `https://cognito-idp.${AWS_REGION}.amazonaws.com/`;
}

async function cognitoCall(target: string, body: Record<string, unknown>) {
  const res = await fetch(cognitoEndpoint(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.message || data.__type || 'Cognito request failed');
  }
  return data;
}

function decodeJwtPayload(token: string): Record<string, any> {
  const part = token.split('.')[1];
  const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
  return JSON.parse(json);
}

export async function cognitoSignUp(email: string, password: string, username: string) {
  await cognitoCall('SignUp', {
    ClientId: COGNITO_CLIENT_ID,
    Username: email,
    Password: password,
    UserAttributes: [
      { Name: 'email', Value: email },
      { Name: 'preferred_username', Value: username },
    ],
  });
}

export async function cognitoSignIn(email: string, password: string): Promise<CognitoTokens> {
  const data = await cognitoCall('InitiateAuth', {
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: {
      USERNAME: email,
      PASSWORD: password,
    },
  });
  const result = data.AuthenticationResult;
  if (!result?.AccessToken) {
    throw new Error(data.ChallengeName ? `Auth challenge: ${data.ChallengeName}` : 'Login failed');
  }
  const payload = decodeJwtPayload(result.IdToken || result.AccessToken);
  const tokens: CognitoTokens = {
    accessToken: result.AccessToken,
    idToken: result.IdToken,
    refreshToken: result.RefreshToken,
    expiresAt: Date.now() + (result.ExpiresIn || 3600) * 1000,
    email: payload.email || email,
    sub: payload.sub,
  };
  await storageSet(TOKEN_KEY, JSON.stringify(tokens));
  return tokens;
}

export async function cognitoSignOut() {
  await storageRemove(TOKEN_KEY);
}

export async function getCognitoSession(): Promise<CognitoTokens | null> {
  const raw = await storageGet(TOKEN_KEY);
  if (!raw) return null;
  try {
    const tokens = JSON.parse(raw) as CognitoTokens;
    if (tokens.expiresAt && tokens.expiresAt < Date.now() + 60_000 && tokens.refreshToken) {
      return refreshCognitoSession(tokens.refreshToken, tokens.email);
    }
    return tokens;
  } catch {
    return null;
  }
}

async function refreshCognitoSession(refreshToken: string, email: string): Promise<CognitoTokens> {
  const data = await cognitoCall('InitiateAuth', {
    AuthFlow: 'REFRESH_TOKEN_AUTH',
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: { REFRESH_TOKEN: refreshToken },
  });
  const result = data.AuthenticationResult;
  const payload = decodeJwtPayload(result.IdToken || result.AccessToken);
  const tokens: CognitoTokens = {
    accessToken: result.AccessToken,
    idToken: result.IdToken,
    refreshToken,
    expiresAt: Date.now() + (result.ExpiresIn || 3600) * 1000,
    email: payload.email || email,
    sub: payload.sub,
  };
  await storageSet(TOKEN_KEY, JSON.stringify(tokens));
  return tokens;
}

export async function getAccessToken(): Promise<string | null> {
  const session = await getCognitoSession();
  return session?.accessToken ?? null;
}

// Keep API_URL referenced so bundlers retain the env linkage in AWS builds.
void API_URL;
