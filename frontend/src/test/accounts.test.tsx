import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AccountDetailPage, NewAccountPage } from '../AccountPages';
import { api, type Account } from '../lib/api';
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  api: {
    openAccount: vi.fn(),
    account: vi.fn(),
    history: vi.fn(),
    updateAccount: vi.fn(),
    closeAccount: vi.fn(),
  },
}));
const account: Account = {
  id: '00000000-0000-4000-8000-000000000003',
  account_number: 'DEMO-SAVINGS',
  name: 'Travel',
  currency: 'VND',
  balance_vnd: 0,
  account_type: 'SAVINGS',
  status: 'ACTIVE',
  daily_outgoing_limit_vnd: null,
  closed_at: null,
};
function wrap(element: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[`/accounts/${account.id}`]}>
        <Routes>
          <Route path="/accounts/:id" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.account).mockResolvedValue(account);
  vi.mocked(api.history).mockResolvedValue({
    items: [],
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 0,
  });
  vi.mocked(api.updateAccount).mockResolvedValue(account);
  vi.mocked(api.closeAccount).mockResolvedValue({ ...account, status: 'CLOSED' });
});
it('opens a zero-funded savings account without accepting a balance input', async () => {
  const user = userEvent.setup();
  vi.mocked(api.openAccount).mockResolvedValue(account);
  wrap(<NewAccountPage />);
  await user.type(screen.getByLabelText('Account nickname'), 'Travel');
  await user.click(screen.getByRole('button', { name: 'Open zero-balance account' }));
  await waitFor(() =>
    expect(api.openAccount).toHaveBeenCalledWith(
      { name: 'Travel', account_type: 'SAVINGS' },
      expect.anything(),
    ),
  );
  expect(screen.queryByLabelText(/initial balance/i)).not.toBeInTheDocument();
});
it('rejects fractional daily limits and requires closure confirmation', async () => {
  const user = userEvent.setup();
  wrap(<AccountDetailPage />);
  const input = await screen.findByLabelText('Daily outgoing limit (VND)');
  await user.type(input, '1.5');
  await user.click(screen.getByRole('button', { name: 'Save account settings' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('positive whole VND limit');
  expect(api.updateAccount).not.toHaveBeenCalled();
  await user.clear(input);
  await user.type(input, '150000');
  await user.click(screen.getByRole('button', { name: 'Save account settings' }));
  await waitFor(() =>
    expect(api.updateAccount).toHaveBeenCalledWith(account.id, {
      name: 'Travel',
      daily_outgoing_limit_vnd: 150000,
    }),
  );
  expect(screen.getByRole('button', { name: 'Close account' })).toBeDisabled();
  await user.click(screen.getByLabelText('I confirm this account should be closed.'));
  await user.click(screen.getByRole('button', { name: 'Close account' }));
  await waitFor(() => expect(api.closeAccount).toHaveBeenCalledWith(account.id));
});
it('keeps funded accounts protected against closure', async () => {
  vi.mocked(api.account).mockResolvedValue({ ...account, balance_vnd: 100 });
  wrap(<AccountDetailPage />);
  expect(await screen.findByRole('button', { name: 'Close account' })).toBeDisabled();
  expect(screen.getByLabelText('I confirm this account should be closed.')).toBeDisabled();
});
