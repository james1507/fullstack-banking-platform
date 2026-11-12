import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HistoryPage, LoginPage } from '../pages';
import { TransferForm, amountInput } from '../TransferForm';
import { api, APIError, type Account } from '../lib/api';
const mocks = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock('../auth', () => ({ useAuth: () => ({ user: null, loading: false, login: mocks.login }) }));
vi.mock('../lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../lib/api')>();
  return {
    ...original,
    api: {
      accounts: vi.fn(),
      history: vi.fn(),
      transfer: vi.fn(),
      beneficiaries: vi.fn(),
      previewTransfer: vi.fn(),
    },
  };
});
const account: Account = {
  id: '00000000-0000-4000-8000-000000000001',
  account_number: 'DEMO-100001',
  name: 'Everyday account',
  currency: 'VND',
  balance_vnd: 5000000,
  account_type: 'CHECKING',
  status: 'ACTIVE',
  daily_outgoing_limit_vnd: null,
  closed_at: null,
};
function wrap(element: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      <MemoryRouter>
        <Routes>
          <Route path="*" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.accounts).mockResolvedValue([account]);
  vi.mocked(api.beneficiaries).mockResolvedValue([]);
  vi.mocked(api.previewTransfer).mockImplementation(async (payload) => ({
    ...payload,
    source_name: account.name,
    source_number: account.account_number,
    destination_masked_number: '••••0001',
    estimated_balance_vnd: account.balance_vnd - payload.amount_vnd,
    fee_vnd: 0,
    currency: 'VND',
    checked_at: '2026-11-12T00:00:00Z',
  }));
  vi.mocked(api.history).mockResolvedValue({
    items: [],
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 0,
  });
});
describe('Sign in', () => {
  it('validates fields and renders server error', async () => {
    const user = userEvent.setup();
    wrap(<LoginPage />);
    await user.clear(screen.getByLabelText('Email address'));
    await user.type(screen.getByLabelText('Email address'), 'bad');
    await user.click(screen.getByRole('button', { name: /Sign in to/ }));
    expect(await screen.findByText('Enter a valid email address.')).toBeVisible();
    expect(mocks.login).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText('Email address'));
    await user.type(screen.getByLabelText('Email address'), 'alice@example.test');
    mocks.login.mockRejectedValueOnce(
      new APIError('INVALID_CREDENTIALS', 'Email or password is incorrect.', 401),
    );
    await user.click(screen.getByRole('button', { name: /Sign in to/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
  });
});
describe('Transfer', () => {
  it('validates safe whole VND amounts', () => {
    for (const value of ['0', '-1', '1.5', '9007199254740992', '1e4'])
      expect(amountInput.safeParse(value).success).toBe(false);
    expect(amountInput.safeParse('150,000').success).toBe(true);
  });
  it('formats input, confirms once and blocks duplicate clicks while pending', async () => {
    const user = userEvent.setup();
    vi.mocked(api.transfer).mockImplementation(() => new Promise(() => {}));
    wrap(<TransferForm accounts={[account]} />);
    await user.click(screen.getByRole('button', { name: /Use Bob/ }));
    await user.type(screen.getByLabelText('Amount'), '150000');
    expect(screen.getByLabelText('Amount')).toHaveValue('150,000');
    await user.click(screen.getByRole('button', { name: /Review transfer/ }));
    expect(await screen.findByRole('region', { name: 'Review transfer' })).toBeVisible();
    await user.dblClick(screen.getByRole('button', { name: 'Confirm & send' }));
    expect(api.transfer).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Sending…' })).toBeDisabled();
    expect(api.transfer).toHaveBeenCalledWith(
      expect.objectContaining({ amount_vnd: 150000 }),
      expect.any(String),
    );
  });
  it('preserves original key and payload on uncertain retry', async () => {
    const user = userEvent.setup();
    vi.mocked(api.transfer).mockRejectedValue(
      new APIError('NETWORK_ERROR', 'Connection interrupted.'),
    );
    wrap(<TransferForm accounts={[account]} />);
    await user.click(screen.getByRole('button', { name: /Use Bob/ }));
    await user.type(screen.getByLabelText('Amount'), '100');
    await user.click(screen.getByRole('button', { name: /Review transfer/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirm & send' }));
    await user.click(await screen.findByRole('button', { name: 'Retry original transfer' }));
    await waitFor(() => expect(api.transfer).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.transfer).mock.calls[0]).toEqual(vi.mocked(api.transfer).mock.calls[1]);
    expect(screen.getByLabelText('Amount')).toBeDisabled();
  });
  it('submits the source selected through the account dropdown', async () => {
    const user = userEvent.setup();
    const savings = {
      ...account,
      id: '00000000-0000-4000-8000-000000000003',
      name: 'Savings',
      account_number: 'DEMO-100002',
    };
    vi.mocked(api.transfer).mockImplementation(() => new Promise(() => {}));
    wrap(<TransferForm accounts={[account, savings]} />);
    await user.click(screen.getByRole('combobox', { name: 'From account' }));
    await user.click(screen.getByRole('option', { name: /Savings/ }));
    await user.click(screen.getByRole('button', { name: /Use Bob/ }));
    await user.type(screen.getByLabelText('Amount'), '100');
    await user.click(screen.getByRole('button', { name: /Review transfer/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirm & send' }));
    expect(api.transfer).toHaveBeenCalledWith(
      expect.objectContaining({ source_account_id: savings.id }),
      expect.any(String),
    );
    expect(screen.getByRole('combobox', { name: 'From account' })).toBeDisabled();
  });
  it('shows amount validation before sending', async () => {
    const user = userEvent.setup();
    wrap(<TransferForm accounts={[account]} />);
    await user.click(screen.getByRole('button', { name: /Review transfer/ }));
    expect(await screen.findByText('Enter a whole VND amount.')).toBeVisible();
    expect(api.transfer).not.toHaveBeenCalled();
  });
  it('does not allow confirmation when the server preview rejects a stale account', async () => {
    const user = userEvent.setup();
    vi.mocked(api.previewTransfer).mockRejectedValueOnce(
      new APIError('ACCOUNT_NOT_ACTIVE', 'Source account is frozen.', 409),
    );
    wrap(<TransferForm accounts={[account]} />);
    await user.click(screen.getByRole('button', { name: /Use Bob/ }));
    await user.type(screen.getByLabelText('Amount'), '100');
    await user.click(screen.getByRole('button', { name: 'Review transfer' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Source account is frozen.');
    expect(screen.queryByRole('button', { name: 'Confirm & send' })).not.toBeInTheDocument();
    expect(api.transfer).not.toHaveBeenCalled();
  });
  it('excludes frozen and closed accounts from the source picker', async () => {
    const user = userEvent.setup();
    wrap(<TransferForm accounts={[{ ...account, status: 'FROZEN' }]} />);
    expect(screen.getByRole('button', { name: 'Review transfer' })).toBeDisabled();
    await user.click(screen.getByRole('combobox', { name: 'From account' }));
    expect(screen.queryByRole('option', { name: /Everyday account/ })).not.toBeInTheDocument();
  });
});
describe('History', () => {
  it('shows loading, empty results and sends filters to server', async () => {
    const user = userEvent.setup();
    wrap(<HistoryPage />);
    expect(screen.getByRole('status', { name: 'Loading' })).toBeVisible();
    expect(await screen.findByText('A fresh start')).toBeVisible();
    await user.click(screen.getByRole('combobox', { name: 'Filter direction' }));
    await user.click(screen.getByRole('option', { name: /Money in/ }));
    await waitFor(() =>
      expect(api.history).toHaveBeenLastCalledWith(expect.stringContaining('direction=INCOMING')),
    );
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  });
  it('pages on server and resets page when filter changes', async () => {
    const user = userEvent.setup();
    vi.mocked(api.history).mockResolvedValue({
      items: [],
      page: 1,
      page_size: 10,
      total: 21,
      total_pages: 3,
    });
    wrap(<HistoryPage />);
    await screen.findByText('21 transactions found');
    await user.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() =>
      expect(api.history).toHaveBeenLastCalledWith(expect.stringContaining('page=2')),
    );
    await user.click(screen.getByRole('combobox', { name: 'Filter direction' }));
    await user.click(screen.getByRole('option', { name: /Money out/ }));
    await waitFor(() =>
      expect(api.history).toHaveBeenLastCalledWith(expect.stringContaining('page=1')),
    );
  });
});
