import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
} from "react";
import type { ReactNode } from "react";

import * as authApi from "../api/auth";
import { setAccessToken } from "../api/client";
import type { AuthState, LoginRequest, RegisterRequest, TokenResponse, User } from "../types/auth";
import type { Permission } from "../types/permissions";
import { getPermissionsForRoles } from "../types/permissions";
import { storage } from "../utils/storage";

type AuthAction =
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "LOGIN_SUCCESS"; payload: { user: User; accessToken: string } }
  | { type: "LOGOUT" }
  | { type: "SET_USER"; payload: User }
  | { type: "SET_ERROR"; payload: string };

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<User>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  handleOAuthSuccess?: (tokens: TokenResponse) => Promise<User>;
  permissions: Set<Permission>;
  can: (permission: Permission) => boolean;
}

const initialState: AuthState = {
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,
};

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, isLoading: action.payload };
    case "LOGIN_SUCCESS":
      return {
        ...state,
        user: action.payload.user,
        accessToken: action.payload.accessToken,
        isAuthenticated: true,
        isLoading: false,
      };
    case "LOGOUT":
      return { ...initialState, isLoading: false };
    case "SET_USER":
      return { ...state, user: action.payload };
    case "SET_ERROR":
      return { ...state, isLoading: false };
    default:
      return state;
  }
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  const clearAuth = useCallback(() => {
    setAccessToken(null);
    storage.removeRefreshToken();
    dispatch({ type: "LOGOUT" });
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    const tokens = await authApi.login(data);
    setAccessToken(tokens.access_token);
    storage.setRefreshToken(tokens.refresh_token);

    let user: User;
    if (tokens.user) {
      user = tokens.user as User;
    } else {
      user = await authApi.getMe();
    }
    dispatch({ type: "LOGIN_SUCCESS", payload: { user, accessToken: tokens.access_token } });
    return user;
  }, []);

  const handleOAuthSuccess = useCallback(async (tokens: TokenResponse) => {
    setAccessToken(tokens.access_token);
    storage.setRefreshToken(tokens.refresh_token);

    let user: User;
    if (tokens.user) {
      user = tokens.user as User;
    } else {
      user = await authApi.getMe();
    }
    dispatch({ type: "LOGIN_SUCCESS", payload: { user, accessToken: tokens.access_token } });
    return user;
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    await authApi.register(data);
  }, []);

  const logout = useCallback(async () => {
    try {
      const refreshToken = storage.getRefreshToken();
      await authApi.logout(refreshToken);
    } finally {
      clearAuth();
    }
  }, [clearAuth]);

  const refreshAuth = useCallback(async () => {
    const refreshToken = storage.getRefreshToken();
    if (!refreshToken) {
      dispatch({ type: "SET_LOADING", payload: false });
      return;
    }
    try {
      const tokens = await authApi.refreshToken(refreshToken);
      setAccessToken(tokens.access_token);
      storage.setRefreshToken(tokens.refresh_token);

      let user: User;
      if (tokens.user) {
        user = tokens.user as User;
      } else {
        user = await authApi.getMe();
      }
      dispatch({ type: "LOGIN_SUCCESS", payload: { user, accessToken: tokens.access_token } });
    } catch {
      clearAuth();
    }
  }, [clearAuth]);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  const permissions = useMemo(() => {
    if (!state.user) return new Set<Permission>();
    return getPermissionsForRoles(state.user.roles);
  }, [state.user]);

  const can = useCallback(
    (permission: Permission) => {
      if (!state.user) return false;
      return permissions.has(permission);
    },
    [state.user, permissions],
  );

  const value = useMemo(
    () => ({ ...state, login, register, logout, refreshAuth, handleOAuthSuccess, permissions, can }),
    [state, login, register, logout, refreshAuth, handleOAuthSuccess, permissions, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
