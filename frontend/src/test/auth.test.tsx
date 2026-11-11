import { expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider, ProtectedRoute, useAuth } from '../auth';
import { api, restoreSession } from '../lib/api';
vi.mock('../lib/api', () => ({
  restoreSession: vi.fn(),
  setToken: vi.fn(),
  api: { me: vi.fn(), logout: vi.fn() },
}));
beforeEach(() => vi.clearAllMocks());
function Private() {
  const { user, logout } = useAuth();
  return (
    <div>
      {user?.display_name}
      <button onClick={() => void logout()}>Logout</button>
    </div>
  );
}
function renderApp() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Sign-in page</div>} />
            <Route element={<ProtectedRoute />}>
              <Route index element={<Private />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it('redirects unauthenticated protected route', async () => {
  vi.mocked(restoreSession).mockResolvedValue(false);
  renderApp();
  expect(await screen.findByText('Sign-in page')).toBeVisible();
  expect(api.me).not.toHaveBeenCalled();
});
it('restores session and clears view on logout', async () => {
  vi.mocked(restoreSession).mockResolvedValue(true);
  vi.mocked(api.me).mockResolvedValue({
    id: 'id',
    email: 'alice@example.test',
    display_name: 'Alice',
  });
  vi.mocked(api.logout).mockResolvedValue(undefined);
  renderApp();
  expect(await screen.findByText('Alice')).toBeVisible();
  screen.getByRole('button', { name: 'Logout' }).click();
  expect(await screen.findByText('Sign-in page')).toBeVisible();
});
it('responds to session expiry', async () => {
  vi.mocked(restoreSession).mockResolvedValue(true);
  vi.mocked(api.me).mockResolvedValue({
    id: 'id',
    email: 'alice@example.test',
    display_name: 'Alice',
  });
  renderApp();
  await screen.findByText('Alice');
  window.dispatchEvent(new Event('auth-expired'));
  expect(await screen.findByText('Sign-in page')).toBeVisible();
});
