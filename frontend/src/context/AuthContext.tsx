/**
 * Authentication context provider.
 * Manages user authentication state, JWT tokens, and session persistence.
 * Supports both local authentication and Azure AD SSO.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { authApi, type User } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  ssoEnabled: boolean;
  login: (user: User, token: string) => void;
  loginWithToken: (token: string) => Promise<void>;
  loginWithSSO: () => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [ssoEnabled, setSsoEnabled] = useState(false);

  // Check SSO status on mount
  useEffect(() => {
    const checkSSOStatus = async () => {
      try {
        const { data } = await authApi.ssoStatus();
        setSsoEnabled(data.enabled);
      } catch {
        setSsoEnabled(false);
      }
    };
    checkSSOStatus();
  }, []);

  // Load saved auth state on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback((user: User, token: string) => {
    setUser(user);
    setToken(token);
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('token', token);
  }, []);

  /**
   * Login using only a JWT token (for SSO callback).
   * Fetches user info from the /me endpoint.
   */
  const loginWithToken = useCallback(async (token: string) => {
    // Temporarily set token to make authenticated request
    localStorage.setItem('token', token);
    setToken(token);

    try {
      const { data: user } = await authApi.me();
      setUser(user);
      localStorage.setItem('user', JSON.stringify(user));
    } catch (error) {
      // Clear token if user fetch fails
      localStorage.removeItem('token');
      setToken(null);
      throw error;
    }
  }, []);

  /**
   * Initiate Azure AD SSO login flow.
   * Redirects user to Microsoft login page.
   */
  const loginWithSSO = useCallback(async () => {
    try {
      const { data } = await authApi.ssoLogin();
      // Store state for CSRF validation
      sessionStorage.setItem('sso_state', data.state);
      // Redirect to Azure AD
      window.location.href = data.auth_url;
    } catch (error) {
      throw new Error('Failed to initiate SSO login');
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    sessionStorage.removeItem('sso_state');
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      token,
      isLoading,
      ssoEnabled,
      login,
      loginWithToken,
      loginWithSSO,
      logout,
      isAuthenticated: !!token && !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
