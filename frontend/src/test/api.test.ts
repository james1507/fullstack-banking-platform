import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { accountSchema, api, APIError, request, restoreSession, setToken } from '../lib/api';
const account = {
  id: '00000000-0000-4000-8000-000000000001',
  account_number: 'DEMO-100001',
  name: 'Everyday account',
  currency: 'VND',
  balance_vnd: 5000000,
};
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const expired = () =>
  json(
    { error: { code: 'UNAUTHENTICATED', message: 'Sign in.', request_id: 'trace', details: {} } },
    401,
  );
beforeEach(() => setToken(null));
afterEach(() => vi.unstubAllGlobals());
describe('HTTP boundary', () => {
  it('maps business errors without losing code or request ID', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          {
            error: {
              code: 'INSUFFICIENT_FUNDS',
              message: 'Not enough funds.',
              request_id: 'trace-1',
              details: {},
            },
          },
          409,
        ),
      ),
    );
    await expect(request('/accounts', accountSchema)).rejects.toMatchObject({
      code: 'INSUFFICIENT_FUNDS',
      status: 409,
      requestId: 'trace-1',
    });
  });
  it('rejects renamed contract fields and unsafe integer balances', () => {
    expect(
      accountSchema.safeParse({ ...account, balance_vnd: undefined, balance: 5000000 }).success,
    ).toBe(false);
    expect(
      accountSchema.safeParse({ ...account, balance_vnd: Number.MAX_SAFE_INTEGER + 1 }).success,
    ).toBe(false);
  });
  it('reports an uncertain network outcome', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const error = await api.accounts().catch((e) => e);
    expect(error).toBeInstanceOf(APIError);
    expect(error.uncertain).toBe(true);
  });
  it('coordinates one refresh for concurrent callers', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        json({ access_token: 'new-token', token_type: 'bearer', expires_in: 900 }),
      );
    vi.stubGlobal('fetch', fetch);
    expect(await Promise.all([restoreSession(), restoreSession(), restoreSession()])).toEqual([
      true,
      true,
      true,
    ]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('retries an expired transfer with the original key and body', async () => {
    const receipt = {
      id: account.id,
      reference: 'TXN-2026-1',
      source_account_id: account.id,
      destination_account_id: '00000000-0000-4000-8000-000000000002',
      amount_vnd: 10,
      currency: 'VND',
      memo: null,
      status: 'SUCCEEDED',
      created_at: '2026-11-11T06:00:00Z',
    };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(expired())
      .mockResolvedValueOnce(
        json({ access_token: 'rotated', token_type: 'bearer', expires_in: 900 }),
      )
      .mockResolvedValueOnce(json(receipt, 201));
    vi.stubGlobal('fetch', fetch);
    await api.transfer(
      {
        source_account_id: account.id,
        destination_account_id: receipt.destination_account_id,
        amount_vnd: 10,
        memo: null,
      },
      'original-key',
    );
    expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[2][1].body);
    expect(fetch.mock.calls[2][1].headers['Idempotency-Key']).toBe('original-key');
    expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer rotated');
  });
  it('stops after rejected refresh and emits session expiry', async () => {
    const fetch = vi.fn().mockImplementation(async () => expired());
    vi.stubGlobal('fetch', fetch);
    const listener = vi.fn();
    window.addEventListener('auth-expired', listener, { once: true });
    await expect(api.accounts()).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(listener).toHaveBeenCalledOnce();
  });
});
