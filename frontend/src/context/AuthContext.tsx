"use client";

/**
 * Authentication context.
 *
 * Holds the JWT in localStorage + React state, hydrates the current user on
 * mount, and exposes `login`, `register`, `logout` and `refresh`. Every client
 * component reads the token through the typed `api` module, which falls back to
 * localStorage automatically.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, authApi, getToken, setToken } from "@/lib/api";
import type { UserMe } from "@/lib/types";

interface AuthContextValue {
  user: UserMe | null;
  token: string | null;
  /** True while the initial `/auth/me` hydration is in flight. */
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<UserMe>;
  register: (input: {
    username: string;
    email: string;
    password: string;
    display_name?: string;
  }) => Promise<UserMe>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  setUser: (user: UserMe | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ------------------------------------------------------------ hydration
  useEffect(() => {
    const stored = getToken();
    setTokenState(stored);

    if (!stored) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const me = await authApi.me(stored);
        if (!cancelled) setUser(me);
      } catch (err) {
        // Expired or invalid token — drop it silently.
        if (!cancelled && err instanceof ApiError && err.status === 401) {
          setToken(null);
          setTokenState(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ---------------------------------------------------------------- login
  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      const result = await authApi.login(username, password);
      setToken(result.access_token);
      setTokenState(result.access_token);
      setUser(result.user);
      return result.user;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Login failed.";
      setError(message);
      throw err;
    }
  }, []);

  // ------------------------------------------------------------- register
  const register = useCallback(
    async (input: { username: string; email: string; password: string; display_name?: string }) => {
      setError(null);
      try {
        const result = await authApi.register(input);
        setToken(result.access_token);
        setTokenState(result.access_token);
        setUser(result.user);
        return result.user;
      } catch (err) {
        const message = err instanceof ApiError ? err.detail : "Registration failed.";
        setError(message);
        throw err;
      }
    },
    [],
  );

  // --------------------------------------------------------------- logout
  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  // --------------------------------------------------------------- refresh
  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch {
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      error,
      login,
      register,
      logout,
      refreshUser,
      setUser,
    }),
    [user, token, loading, error, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Access the auth context (throws when used outside the provider). */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return context;
}
