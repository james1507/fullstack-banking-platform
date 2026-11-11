import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api, restoreSession, setToken, type User } from './lib/api';
import { ErrorAlert, LoadingSkeleton } from './components/ui';

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const cache = useQueryClient();
  const boot = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (await restoreSession()) setUser(await api.me());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void boot();
  }, [boot]);
  useEffect(() => {
    const expire = () => {
      setToken(null);
      setUser(null);
      cache.clear();
    };
    window.addEventListener('auth-expired', expire);
    return () => window.removeEventListener('auth-expired', expire);
  }, [cache]);
  async function login(email: string, password: string) {
    await api.login(email, password);
    cache.clear();
    setUser(await api.me());
  }
  async function logout() {
    await api.logout();
    setUser(null);
    cache.clear();
  }
  if (error)
    return (
      <main className="session-screen">
        <div className="panel">
          <h1>Let’s reconnect</h1>
          <ErrorAlert error={error} retry={() => void boot()} />
        </div>
      </main>
    );
  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}
export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('AuthProvider required');
  return auth;
}
export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <main className="session-screen">
        <LoadingSkeleton />
      </main>
    );
  return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}
