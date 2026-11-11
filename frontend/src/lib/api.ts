import { z } from 'zod';

const uuid = z.string().uuid();
const money = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
export const accountSchema = z.object({
  id: uuid,
  account_number: z.string(),
  name: z.string(),
  currency: z.literal('VND'),
  balance_vnd: money,
});
export const userSchema = z.object({ id: uuid, email: z.string(), display_name: z.string() });
export const transferSchema = z.object({
  id: uuid,
  reference: z.string(),
  status: z.literal('SUCCEEDED'),
  amount_vnd: money.positive(),
  currency: z.literal('VND'),
  source_account_id: uuid,
  destination_account_id: uuid,
  memo: z.string().nullable(),
  created_at: z.string().datetime({ offset: true }),
});
export const historySchema = z.object({
  items: z.array(transferSchema),
  page: z.number().int(),
  page_size: z.number().int(),
  total: z.number().int(),
  total_pages: z.number().int(),
});
export const summarySchema = z.object({
  total_balance_vnd: money,
  account_count: z.number().int(),
  transfer_count: z.number().int(),
  recent_transfers: z.array(transferSchema),
});
const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.literal('bearer'),
  expires_in: z.number(),
});
const errorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string(),
    details: z.record(z.string(), z.unknown()),
  }),
});
export type Account = z.infer<typeof accountSchema>;
export type User = z.infer<typeof userSchema>;
export type Transfer = z.infer<typeof transferSchema>;
export type History = z.infer<typeof historySchema>;
export type TransferInput = {
  source_account_id: string;
  destination_account_id: string;
  amount_vnd: number;
  memo: string | null;
};
export const BOB_ACCOUNT = '00000000-0000-4000-8000-000000000002';
export const ALICE_ACCOUNT = '00000000-0000-4000-8000-000000000001';

export class APIError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 0,
    public requestId?: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
  get uncertain() {
    return this.status === 0 || this.status >= 500;
  }
}
let token: string | null = null;
let refreshFlight: Promise<boolean> | null = null;
export function setToken(value: string | null) {
  token = value;
}

async function raw(path: string, init: RequestInit = {}) {
  try {
    return await fetch(`/api/v1${path}`, {
      ...init,
      credentials: 'include',
      signal: AbortSignal.timeout(12000),
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new APIError(
      'NETWORK_ERROR',
      'Connection interrupted. Retry to safely check the original request.',
    );
  }
}
async function parse<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
  if (!response.ok) {
    const parsed = errorSchema.safeParse(await response.json().catch(() => null));
    if (parsed.success) {
      const e = parsed.data.error;
      throw new APIError(e.code, e.message, response.status, e.request_id, e.details);
    }
    throw new APIError(
      'SERVER_ERROR',
      'The server could not complete this request.',
      response.status,
    );
  }
  const body = await response.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success)
    throw new APIError(
      'CONTRACT_ERROR',
      'Server response was unexpected. Retry or contact the demo maintainer.',
    );
  return parsed.data;
}
export function restoreSession(): Promise<boolean> {
  if (!refreshFlight) {
    refreshFlight = (async () => {
      try {
        const data = await parse(await raw('/auth/refresh', { method: 'POST' }), tokenSchema);
        token = data.access_token;
        return true;
      } catch (error) {
        token = null;
        if (error instanceof APIError && error.status === 401) return false;
        throw error;
      } finally {
        refreshFlight = null;
      }
    })();
  }
  return refreshFlight;
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  let response = await raw(path, init);
  if (response.status === 401) {
    if (await restoreSession()) response = await raw(path, init);
    else {
      window.dispatchEvent(new Event('auth-expired'));
      throw new APIError('UNAUTHENTICATED', 'Session expired. Sign in again.', 401);
    }
  }
  return parse(response, schema);
}
export const api = {
  async login(email: string, password: string) {
    const data = await parse(
      await raw('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
      tokenSchema,
    );
    token = data.access_token;
  },
  async logout() {
    const response = await raw('/auth/logout', { method: 'POST' });
    if (!response.ok) await parse(response, z.unknown());
    token = null;
  },
  me: () => request('/auth/me', userSchema),
  accounts: () => request('/accounts', z.array(accountSchema)),
  summary: () => request('/dashboard/summary', summarySchema),
  history: (params = '') => request(`/transfers${params ? `?${params}` : ''}`, historySchema),
  transfer: (payload: TransferInput, key: string) =>
    request('/transfers', transferSchema, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: JSON.stringify(payload),
    }),
  receipt: (id: string) => request(`/transfers/${id}`, transferSchema),
};
