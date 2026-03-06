"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { LoginRequest, RegisterRequest, User } from "./types";
import * as api from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  // Check for existing session on mount
  useEffect(() => {
    const token = api.getAccessToken();
    if (!token) {
      setState({ user: null, loading: false, error: null });
      return;
    }
    api
      .getMe()
      .then((user) => setState({ user, loading: false, error: null }))
      .catch(() => {
        api.clearTokens();
        setState({ user: null, loading: false, error: null });
      });
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      await api.login(data);
      const user = await api.getMe();
      setState({ user, loading: false, error: null });
    } catch (err) {
      const msg =
        err && typeof err === "object" && "detail" in err
          ? (err as { detail: string }).detail
          : "Login failed";
      setState((s) => ({ ...s, loading: false, error: msg }));
      throw err;
    }
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      await api.register(data);
      const user = await api.getMe();
      setState({ user, loading: false, error: null });
    } catch (err) {
      const msg =
        err && typeof err === "object" && "detail" in err
          ? (err as { detail: string }).detail
          : "Registration failed";
      setState((s) => ({ ...s, loading: false, error: msg }));
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setState({ user: null, loading: false, error: null });
  }, []);

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout, clearError }),
    [state, login, register, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
