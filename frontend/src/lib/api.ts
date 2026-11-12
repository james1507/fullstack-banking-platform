import { z } from 'zod';

const uuid = z.string().uuid();
const money = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
export const accountSchema = z.object({
  id: uuid,
  account_number: z.string(),
  name: z.string(),
  currency: z.literal('VND'),
  balance_vnd: money,
  account_type: z.enum(['CHECKING', 'SAVINGS']),
  status: z.enum(['ACTIVE', 'FROZEN', 'CLOSED']),
  daily_outgoing_limit_vnd: money.positive().nullable(),
  closed_at: z.string().datetime({ offset: true }).nullable(),
});
export const userSchema = z.object({
  id: uuid,
  email: z.string(),
  display_name: z.string(),
  role: z.enum(['CUSTOMER', 'OPERATIONS', 'AUDITOR']),
  timezone: z.string(),
  locale: z.string(),
});
const auditSchema = z.object({
  id: uuid,
  actor_user_id: uuid.nullable(),
  action: z.string(),
  target_type: z.string(),
  target_id: uuid,
  outcome: z.string(),
  request_id: z.string(),
  safe_metadata: z.record(z.string(), z.unknown()),
  created_at: z.string().datetime({ offset: true }),
});
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
const beneficiarySchema = z.object({
  id: uuid,
  destination_account_id: uuid,
  nickname: z.string(),
  archived_at: z.string().datetime({ offset: true }).nullable(),
  last_used_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
const previewSchema = z.object({
  source_account_id: uuid,
  destination_account_id: uuid,
  source_name: z.string(),
  source_number: z.string(),
  destination_masked_number: z.string(),
  amount_vnd: money.positive(),
  fee_vnd: money,
  estimated_balance_vnd: money,
  currency: z.literal('VND'),
  checked_at: z.string().datetime({ offset: true }),
});
export type Beneficiary = z.infer<typeof beneficiarySchema>;
export type TransferPreview = z.infer<typeof previewSchema>;
const decimalVND = z.string().regex(/^(0|[1-9][0-9]*)$/);
const statementSchema = z.object({
  account_id: uuid,
  account_number: z.string(),
  date_from: z.string(),
  date_to: z.string(),
  timezone: z.string(),
  effective_from: z.string().datetime({ offset: true }).nullable(),
  money_encoding: z.literal('decimal-string-vnd'),
  opening_balance_vnd: decimalVND,
  closing_balance_vnd: decimalVND,
  total_debit_vnd: decimalVND,
  total_credit_vnd: decimalVND,
  row_count: z.number().int().nonnegative(),
});
const cursorHistorySchema = z.object({
  items: z.array(transferSchema),
  next_cursor: z.string().nullable(),
  page_size: z.number().int(),
});
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
async function authorized(path: string, init: RequestInit = {}) {
  let response = await raw(path, init);
  if (response.status === 401) {
    if (await restoreSession()) response = await raw(path, init);
    else {
      window.dispatchEvent(new Event('auth-expired'));
      throw new APIError('UNAUTHENTICATED', 'Session expired. Sign in again.', 401);
    }
  }
  return response;
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  return parse(await authorized(path, init), schema);
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
  account: (id: string) => request(`/accounts/${id}`, accountSchema),
  openAccount: (payload: { name: string; account_type: 'CHECKING' | 'SAVINGS' }) =>
    request('/accounts', accountSchema, { method: 'POST', body: JSON.stringify(payload) }),
  updateAccount: (id: string, payload: { name: string; daily_outgoing_limit_vnd: number | null }) =>
    request(`/accounts/${id}`, accountSchema, { method: 'PATCH', body: JSON.stringify(payload) }),
  closeAccount: (id: string) =>
    request(`/accounts/${id}/close`, accountSchema, {
      method: 'POST',
      body: JSON.stringify({ confirmed: true }),
    }),
  freezeAccount: (id: string, frozen: boolean, reason: string) =>
    request(`/ops/accounts/${id}/${frozen ? 'freeze' : 'unfreeze'}`, accountSchema, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  audit: () => request('/audit/events', z.array(auditSchema)),
  searchTransfers: (params: string) => request(`/transfers/search?${params}`, cursorHistorySchema),
  statementSummary: (id: string, params: string) =>
    request(`/accounts/${id}/statement/summary?${params}`, statementSchema),
  async exportStatement(id: string, params: string) {
    const response = await authorized(`/accounts/${id}/statement?${params}`);
    if (!response.ok) await parse(response, z.never());
    if (!response.headers.get('content-type')?.startsWith('text/csv'))
      throw new APIError('CONTRACT_ERROR', 'Expected a CSV statement.');
    return response.blob();
  },
  beneficiaries: (search = '', includeArchived = false) =>
    request(
      `/beneficiaries?${new URLSearchParams({ search, include_archived: String(includeArchived) })}`,
      z.array(beneficiarySchema),
    ),
  addBeneficiary: (payload: { destination_account_id: string; nickname: string }) =>
    request('/beneficiaries', beneficiarySchema, { method: 'POST', body: JSON.stringify(payload) }),
  renameBeneficiary: (id: string, nickname: string) =>
    request(`/beneficiaries/${id}`, beneficiarySchema, {
      method: 'PATCH',
      body: JSON.stringify({ nickname }),
    }),
  archiveBeneficiary: (id: string) =>
    request(`/beneficiaries/${id}`, beneficiarySchema, { method: 'DELETE' }),
  restoreBeneficiary: (id: string) =>
    request(`/beneficiaries/${id}/restore`, beneficiarySchema, { method: 'POST' }),
  previewTransfer: (payload: TransferInput) =>
    request('/transfers/preview', previewSchema, { method: 'POST', body: JSON.stringify(payload) }),
  transferOutcome: (key: string) =>
    request(
      `/transfers/lookup-by-key?${new URLSearchParams({ key })}`,
      z.object({ status_code: z.number().int(), response: z.record(z.string(), z.unknown()) }),
    ),
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

const scheduleInputSchema = z.object({
  source_account_id: uuid,
  destination_account_id: uuid,
  amount_vnd: money.positive(),
  memo: z.string().nullable(),
  timezone: z.string(),
  starts_local: z.string(),
  recurrence: z.enum(['ONCE', 'WEEKLY', 'MONTHLY']),
  max_runs: z.number().int().min(1).max(120),
});
const scheduleSchema = scheduleInputSchema.extend({
  id: uuid,
  status: z.enum(['ACTIVE', 'PAUSED', 'CANCELLED', 'COMPLETED']),
  next_run_at: z.string().datetime({ offset: true }).nullable(),
  runs_completed: z.number().int(),
  version: z.number().int(),
  created_at: z.string().datetime({ offset: true }),
});
const scheduleDetailSchema = z.object({
  schedule: scheduleSchema,
  occurrences: z.array(
    z.object({
      id: uuid,
      due_at: z.string().datetime({ offset: true }),
      state: z.string(),
      attempt_count: z.number().int(),
      transfer_id: uuid.nullable(),
      last_error_code: z.string().nullable(),
      request_id: z.string(),
    }),
  ),
});
export type ScheduleInput = z.infer<typeof scheduleInputSchema>;
export type Schedule = z.infer<typeof scheduleSchema>;
export const scheduleApi = {
  list: () => request('/scheduled-transfers', z.array(scheduleSchema)),
  detail: (id: string) => request(`/scheduled-transfers/${id}`, scheduleDetailSchema),
  create: (payload: ScheduleInput, key: string) =>
    request('/scheduled-transfers', scheduleSchema, {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: JSON.stringify(payload),
    }),
  edit: (id: string, payload: ScheduleInput, version: number) =>
    request(`/scheduled-transfers/${id}`, scheduleSchema, {
      method: 'PATCH',
      body: JSON.stringify({ ...payload, version }),
    }),
  action: (id: string, action: 'pause' | 'resume' | 'cancel', version: number) =>
    request(`/scheduled-transfers/${id}/${action}`, scheduleSchema, {
      method: 'POST',
      body: JSON.stringify({ version, confirmed: true }),
    }),
};
const notificationSchema = z.object({
  id: uuid,
  kind: z.string(),
  entity_id: uuid,
  title: z.string(),
  body: z.string(),
  read_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
});
export const inboxApi = {
  list: (cursor = '') =>
    request(
      `/notifications?${new URLSearchParams({ cursor })}`,
      z.object({
        items: z.array(notificationSchema),
        next_cursor: z.string().nullable(),
        unread_count: z.number().int(),
      }),
    ),
  read: (id: string) =>
    request(`/notifications/${id}/read`, notificationSchema, { method: 'POST' }),
  readAll: () =>
    request('/notifications/read-all', z.object({ updated: z.number().int() }), { method: 'POST' }),
};
