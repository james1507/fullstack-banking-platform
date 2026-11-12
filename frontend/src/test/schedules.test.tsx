import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { NewSchedulePage } from '../SchedulePages';
import { InboxPage } from '../InboxPage';
import { api, scheduleApi, inboxApi, APIError } from '../lib/api';
vi.mock('../auth', () => ({ useAuth: () => ({ user: { timezone: 'Asia/Ho_Chi_Minh' } }) }));
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  api: { accounts: vi.fn() },
  scheduleApi: { create: vi.fn() },
  inboxApi: { list: vi.fn(), readAll: vi.fn() },
}));
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
  vi.mocked(api.accounts).mockResolvedValue([
    {
      id: '00000000-0000-4000-8000-000000000001',
      name: 'Everyday',
      account_number: 'DEMO-100001',
      currency: 'VND',
      balance_vnd: 5000000,
      account_type: 'CHECKING',
      status: 'ACTIVE',
      closed_at: null,
      daily_outgoing_limit_vnd: null,
    },
  ]);
});
it('retains wall time and timezone through review; rejects unsafe money before calling API', async () => {
  const user = userEvent.setup();
  vi.mocked(scheduleApi.create).mockRejectedValue(new Error('First run must be in the future.'));
  wrap(<NewSchedulePage />);
  await screen.findByRole('combobox', { name: 'Schedule source account' });
  await user.type(screen.getByLabelText('Scheduled amount (VND)'), '9007199254740992');
  await user.type(screen.getByLabelText('First run (local time)'), '2026-12-10T09:00');
  await user.click(screen.getByRole('button', { name: 'Review schedule' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('positive whole VND');
  expect(scheduleApi.create).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText('Scheduled amount (VND)'));
  await user.type(screen.getByLabelText('Scheduled amount (VND)'), '150000');
  await user.click(screen.getByRole('button', { name: 'Review schedule' }));
  expect(await screen.findByRole('region', { name: 'Review schedule' })).toHaveTextContent(
    '2026-12-10 09:00',
  );
  expect(scheduleApi.create).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Back to edit' }));
  expect(screen.getByLabelText('Scheduled amount (VND)')).toHaveValue('150000');
  await user.click(screen.getByRole('button', { name: 'Review schedule' }));
  await user.click(screen.getByRole('button', { name: 'Confirm schedule' }));
  await waitFor(() =>
    expect(scheduleApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        amount_vnd: 150000,
        starts_local: '2026-12-10T09:00',
        timezone: 'Asia/Ho_Chi_Minh',
        max_runs: 1,
      }),
      expect.any(String),
    ),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('First run must be in the future.');
});
it('shows server unread count and marks inbox read only after API response', async () => {
  const user = userEvent.setup();
  vi.mocked(inboxApi.list).mockResolvedValue({ items: [], unread_count: 2, next_cursor: null });
  vi.mocked(inboxApi.readAll).mockResolvedValue({ updated: 2 });
  wrap(<InboxPage />);
  expect(await screen.findByText('2 unread')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Mark all read' }));
  await waitFor(() => expect(inboxApi.readAll).toHaveBeenCalledOnce());
  await waitFor(() => expect(inboxApi.list).toHaveBeenCalledTimes(2));
});

it('retries uncertain schedule creation with the same frozen intent key', async () => {
  const user = userEvent.setup();
  vi.mocked(scheduleApi.create).mockRejectedValue(
    new APIError('NETWORK_ERROR', 'Schedule status unknown.'),
  );
  wrap(<NewSchedulePage />);
  await screen.findByRole('combobox', { name: 'Schedule source account' });
  await user.type(screen.getByLabelText('Scheduled amount (VND)'), '100');
  await user.type(screen.getByLabelText('First run (local time)'), '2026-12-10T09:00');
  await user.click(screen.getByRole('button', { name: 'Review schedule' }));
  await user.click(screen.getByRole('button', { name: 'Confirm schedule' }));
  const retry = await screen.findByRole('button', { name: 'Retry original schedule' });
  expect(screen.getByRole('button', { name: 'Back to edit' })).toBeDisabled();
  await user.click(retry);
  await waitFor(() => expect(scheduleApi.create).toHaveBeenCalledTimes(2));
  expect(vi.mocked(scheduleApi.create).mock.calls[0]).toEqual(
    vi.mocked(scheduleApi.create).mock.calls[1],
  );
});
