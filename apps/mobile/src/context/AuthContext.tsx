import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { isDemoMode, isLocalYoloMode, PLACEHOLDER_USER_ID, Profile } from '../constants/theme';
import { api } from '../lib/api';
import {
  cognitoSignIn,
  cognitoSignOut,
  cognitoSignUp,
  getCognitoSession,
  isCognitoMode,
} from '../lib/cognito';

type SessionUser = {
  id: string;
  email: string;
};

type AuthContextValue = {
  user: SessionUser | null;
  profile: Profile | null;
  loading: boolean;
  signUp: (email: string, password: string, username: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const DEMO_KEY = 'fresheats.demo.session';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProfile = async () => {
    try {
      const p = await api.getProfile();
      setProfile(p);
    } catch {
      // ignore in cold start
    }
  };

  useEffect(() => {
    (async () => {
      try {
        if (isDemoMode() || isLocalYoloMode()) {
          const raw = await AsyncStorage.getItem(DEMO_KEY);
          if (raw) {
            setUser(JSON.parse(raw) as SessionUser);
            await refreshProfile();
          }
        } else if (isCognitoMode()) {
          const session = await getCognitoSession();
          if (session) {
            setUser({ id: session.sub, email: session.email });
            await refreshProfile();
          }
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      profile,
      loading,
      refreshProfile,
      signUp: async (email, password, username) => {
        if (isDemoMode() || isLocalYoloMode()) {
          const demoUser = { id: PLACEHOLDER_USER_ID, email };
          await AsyncStorage.setItem(DEMO_KEY, JSON.stringify(demoUser));
          setUser(demoUser);
          await api.updateProfile({ username, display_name: username });
          await refreshProfile();
          return;
        }
        if (!isCognitoMode()) {
          throw new Error('Cognito is not configured. Set EXPO_PUBLIC_COGNITO_* env vars.');
        }
        await cognitoSignUp(email, password, username);
        const session = await cognitoSignIn(email, password);
        setUser({ id: session.sub, email: session.email });
        await api.updateProfile({ username, display_name: username });
        await refreshProfile();
      },
      signIn: async (email, password) => {
        if (isDemoMode() || isLocalYoloMode()) {
          const demoUser = { id: PLACEHOLDER_USER_ID, email };
          await AsyncStorage.setItem(DEMO_KEY, JSON.stringify(demoUser));
          setUser(demoUser);
          await refreshProfile();
          return;
        }
        if (!isCognitoMode()) {
          throw new Error('Cognito is not configured. Set EXPO_PUBLIC_COGNITO_* env vars.');
        }
        const session = await cognitoSignIn(email, password);
        setUser({ id: session.sub, email: session.email });
        await refreshProfile();
      },
      signOut: async () => {
        await AsyncStorage.removeItem(DEMO_KEY);
        await cognitoSignOut();
        setUser(null);
        setProfile(null);
      },
    }),
    [user, profile, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
