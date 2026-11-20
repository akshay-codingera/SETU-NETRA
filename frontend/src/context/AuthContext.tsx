import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, SessionInfo, UserRecord, WorkspaceRecord } from '../api/client';

interface AuthContextType {
  user: UserRecord | null;
  isAuthenticated: boolean;
  activeWorkspaceId: string;
  csrfToken: string | null;
  permissions: string[];
  workspaces: WorkspaceRecord[];
  loading: boolean;
  error: string | null;
  login: (u: string, p: string) => Promise<void>;
  register: (payload: { username: string; password: string; display_name: string; requested_role?: string }) => Promise<void>;
  logout: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  refreshSession: () => Promise<void>;
  refreshWorkspaces: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserRecord | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string>('default');
  const [csrfToken, setCsrfTokenState] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const applySession = (session: SessionInfo) => {
    setIsAuthenticated(session.authenticated);
    setUser(session.user);
    setActiveWorkspaceId(session.active_workspace_id || 'default');
    setCsrfTokenState(session.csrf_token);
    setPermissions(session.permissions || []);
  };

  const refreshSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const session = await api.auth.getSession();
      applySession(session);
      if (session.authenticated) {
        await refreshWorkspaces();
      }
    } catch (err: any) {
      setIsAuthenticated(false);
      setUser(null);
      setError(err?.detail || err?.title || 'Could not verify active session');
    } finally {
      setLoading(false);
    }
  };

  const refreshWorkspaces = async () => {
    try {
      const list = await api.workspaces.list();
      setWorkspaces(list);
    } catch (err) {
      console.warn('Failed to fetch workspaces', err);
    }
  };

  useEffect(() => {
    refreshSession();
  }, []);

  const login = async (u: string, p: string) => {
    setError(null);
    const session = await api.auth.login(u, p);
    applySession(session);
    await refreshWorkspaces();
  };

  const register = async (payload: { username: string; password: string; display_name: string; requested_role?: string }) => {
    setError(null);
    const session = await api.auth.register(payload);
    applySession(session);
    await refreshWorkspaces();
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      setCsrfTokenState(null);
      setPermissions([]);
      setWorkspaces([]);
    }
  };

  const switchWorkspace = async (wsId: string) => {
    await api.workspaces.switchActive(wsId);
    setActiveWorkspaceId(wsId);
    await refreshWorkspaces();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        activeWorkspaceId,
        csrfToken,
        permissions,
        workspaces,
        loading,
        error,
        login,
        register,
        logout,
        switchWorkspace,
        refreshSession,
        refreshWorkspaces,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
