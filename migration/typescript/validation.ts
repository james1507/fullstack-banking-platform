const MAX_AMOUNT = Number.MAX_SAFE_INTEGER;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fields = new Set(['source_account_id', 'destination_account_id', 'amount_vnd', 'memo']);
export function validate(payload: unknown) {
  const fail = (code: string, field: string) => ({ ok: false as const, code, field });
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) return fail('INVALID_PAYLOAD', 'payload');
  const p = payload as Record<string, unknown>;
  if (Object.keys(p).some(key => !fields.has(key))) return fail('UNKNOWN_FIELD', 'payload');
  for (const field of ['source_account_id', 'destination_account_id', 'amount_vnd']) if (!Object.hasOwn(p, field)) return fail('REQUIRED', field);
  for (const field of ['source_account_id', 'destination_account_id']) if (typeof p[field] !== 'string' || !uuid.test(p[field])) return fail('INVALID_ACCOUNT_ID', field);
  const source = (p.source_account_id as string).toLowerCase(); const destination = (p.destination_account_id as string).toLowerCase();
  if (source === destination) return fail('SELF_TRANSFER', 'destination_account_id');
  const amount = p.amount_vnd;
  if (typeof amount !== 'number' || !Number.isFinite(amount) || !Number.isInteger(amount)) return fail('INVALID_AMOUNT', 'amount_vnd');
  if (amount <= 0) return fail('AMOUNT_NOT_POSITIVE', 'amount_vnd');
  if (amount > MAX_AMOUNT) return fail('AMOUNT_TOO_LARGE', 'amount_vnd');
  let memo = p.memo ?? null;
  if (memo !== null) {
    if (typeof memo !== 'string') return fail('INVALID_MEMO', 'memo');
    if (Array.from(memo).length > 200) return fail('MEMO_TOO_LONG', 'memo');
    memo = memo.replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, '') || null;
  }
  return { ok: true as const, value: { source_account_id: source, destination_account_id: destination, amount_vnd: amount, memo } };
}
