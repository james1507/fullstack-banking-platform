import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AdvancedHistoryPage, StatementsPage } from '../ReportingPages';
import { api, type Account } from '../lib/api';
import { formatVND } from '../lib/format';
vi.mock('../auth', () => ({ useAuth: () => ({ user: { timezone: 'Asia/Ho_Chi_Minh' } }) }));
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  api: { accounts: vi.fn(), searchTransfers: vi.fn(), statementSummary: vi.fn() },
}));
const account: Account = {
  id: '00000000-0000-4000-8000-000000000001',
  account_number: 'DEMO-100001',
  name: 'Everyday',
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
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.accounts).mockResolvedValue([account]);
  vi.mocked(api.searchTransfers).mockResolvedValue({ items: [], next_cursor: null, page_size: 10 });
});
it('rejects half a date range and sends exact integer text to the search API', async () => {
  const user = userEvent.setup();
  wrap(<AdvancedHistoryPage />);
  await screen.findByText('A fresh start');
  await user.type(screen.getByLabelText('From date'), '2026-11-01');
  await user.click(screen.getByRole('button', { name: 'Apply search filters' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Choose both start and end dates.');
  await user.type(screen.getByLabelText('Through date'), '2026-11-12');
  await user.type(screen.getByLabelText('Minimum VND'), '9007199254740991');
  await user.click(screen.getByRole('button', { name: 'Apply search filters' }));
  await waitFor(() =>
    expect(api.searchTransfers).toHaveBeenLastCalledWith(
      expect.stringContaining('min_amount=9007199254740991'),
    ),
  );
});
it('uses server-provided cursors and resets pagination when filters change', async () => {
  const user = userEvent.setup();
  vi.mocked(api.searchTransfers).mockResolvedValue({
    items: [],
    next_cursor: 'opaque-cursor',
    page_size: 10,
  });
  wrap(<AdvancedHistoryPage />);
  await user.click(await screen.findByRole('button', { name: 'Next results' }));
  await waitFor(() =>
    expect(api.searchTransfers).toHaveBeenLastCalledWith(
      expect.stringContaining('cursor=opaque-cursor'),
    ),
  );
  await user.click(screen.getByRole('button', { name: 'Apply search filters' }));
  await waitFor(() => expect(api.searchTransfers).toHaveBeenLastCalledWith('page_size=10'));
});
it('renders statement totals as exact BigInt values beyond the safe-number range', async () => {
  const user = userEvent.setup();
  vi.mocked(api.statementSummary).mockResolvedValue({
    account_id: account.id,
    account_number: account.account_number,
    date_from: '2026-11-01',
    date_to: '2026-11-12',
    timezone: 'Asia/Ho_Chi_Minh',
    effective_from: '2026-11-01T00:00:00Z',
    money_encoding: 'decimal-string-vnd',
    opening_balance_vnd: '5000000',
    closing_balance_vnd: '5000000',
    total_credit_vnd: '9007199254740993',
    total_debit_vnd: '9007199254740993',
    row_count: 2,
  });
  wrap(<StatementsPage />);
  const button = screen.getByRole('button', { name: 'Build statement' });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  expect(await screen.findByRole('heading', { name: 'Statement summary' })).toBeVisible();
  expect(screen.getAllByText('9,007,199,254,740,993 ₫')).toHaveLength(2);
  expect(formatVND(9007199254740993n)).toBe('9,007,199,254,740,993 ₫');
});
