import { useRef, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check, LockKeyhole, UserRound } from 'lucide-react';
import {
  ALICE_ACCOUNT,
  api,
  APIError,
  BOB_ACCOUNT,
  type Account,
  type TransferInput,
  type TransferPreview,
} from './lib/api';
import { formatVND } from './lib/format';
import { ErrorAlert } from './components/ui';
import { Select } from './components/Select';

export const amountInput = z
  .string()
  .regex(/^(?:\d+|\d{1,3}(?:,\d{3})+)$/, 'Enter a whole VND amount.')
  .refine(
    (v) => Number.isSafeInteger(Number(v.replaceAll(',', ''))) && Number(v.replaceAll(',', '')) > 0,
    'Enter a positive whole amount within the safe limit.',
  );
const schema = z
  .object({
    source_account_id: z.string().uuid('Choose a source account.'),
    destination_account_id: z.string().uuid('Enter a valid recipient account ID.'),
    amount: amountInput,
    memo: z.string().max(200, 'Memo must be 200 characters or fewer.'),
  })
  .refine((v) => v.source_account_id !== v.destination_account_id, {
    message: 'Choose a different recipient account.',
    path: ['destination_account_id'],
  });
type FormValues = z.infer<typeof schema>;
type Attempt = { payload: TransferInput; key: string; preview: TransferPreview };

export function ConfirmTransferDialog({
  attempt,
  pending,
  confirm,
  cancel,
}: {
  attempt: Attempt;
  pending: boolean;
  confirm: () => void;
  cancel: () => void;
}) {
  return (
    <section className="confirmation" aria-label="Review transfer">
      <span className="eyebrow">REVIEW BEFORE SENDING</span>
      <h3>{formatVND(attempt.payload.amount_vnd)}</h3>
      <p>
        From {attempt.preview.source_name} · {attempt.preview.source_number}
      </p>
      <p>
        To <strong>{attempt.preview.destination_masked_number}</strong>
      </p>
      <p>{attempt.payload.memo || 'No memo added'}</p>
      <p>
        No transfer fee. Estimated source balance after sending:{' '}
        <strong>{formatVND(attempt.preview.estimated_balance_vnd)}</strong>.
      </p>
      <small>
        Checked with the server. Balance, account status and limits are checked again when you
        confirm.
      </small>
      <div className="flex gap-3">
        <button className="button secondary" disabled={pending} onClick={cancel}>
          Back to edit
        </button>
        <button className="button primary" disabled={pending} onClick={confirm}>
          {pending ? 'Sending…' : 'Confirm & send'} <ArrowRight size={16} />
        </button>
      </div>
    </section>
  );
}
export function TransferForm({ accounts }: { accounts: Account[] }) {
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [params] = useSearchParams();
  const eligible = accounts.filter((account) => account.status === 'ACTIVE');
  const recipients = useQuery({ queryKey: ['beneficiaries'], queryFn: () => api.beneficiaries() });
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const guard = useRef(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      source_account_id:
        eligible.find((account) => account.id === params.get('source'))?.id ||
        eligible[0]?.id ||
        '',
      destination_account_id: z.string().uuid().safeParse(params.get('recipient')).success
        ? params.get('recipient')!
        : '',
      amount: '',
      memo: '',
    },
  });
  const preview = useMutation({
    mutationFn: api.previewTransfer,
    onSuccess: (data, payload) => setAttempt({ payload, key: crypto.randomUUID(), preview: data }),
  });
  const mutation = useMutation({
    mutationFn: (a: Attempt) => api.transfer(a.payload, a.key),
    retry: false,
    onSuccess: async (t) => {
      await Promise.all(
        ['accounts', 'account', 'summary', 'history', 'statement', 'beneficiaries', 'inbox'].map(
          (key) => cache.invalidateQueries({ queryKey: [key] }),
        ),
      );
      navigate(`/transfers/${t.id}`, { state: { fresh: true } });
    },
    onError: (error) => {
      const unknown = !(error instanceof APIError) || error.uncertain;
      setUncertain(unknown);
      if (!unknown) setAttempt(null);
    },
    onSettled: () => {
      guard.current = false;
    },
  });
  const locked = mutation.isPending || preview.isPending || uncertain || attempt !== null;
  const source = accounts.find((a) => a.id === form.watch('source_account_id'));
  function review(values: FormValues) {
    mutation.reset();
    preview.mutate({
      source_account_id: values.source_account_id,
      destination_account_id: values.destination_account_id,
      amount_vnd: Number(values.amount.replaceAll(',', '')),
      memo: values.memo.trim() || null,
    });
  }
  function send() {
    if (!attempt || guard.current) return;
    guard.current = true;
    mutation.mutate(attempt);
  }
  const fieldError = (name: keyof FormValues) =>
    form.formState.errors[name] ? (
      <p className="field-error" id={`${name}-error`}>
        {form.formState.errors[name]?.message}
      </p>
    ) : null;
  return (
    <div className="transfer-form">
      <form onSubmit={form.handleSubmit(review)} noValidate>
        <fieldset disabled={locked}>
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h3>Where is it coming from?</h3>
              <p>Choose an account to send from.</p>
            </div>
          </div>
          <div className="field">
            <label htmlFor="source">From account</label>
            <Controller
              name="source_account_id"
              control={form.control}
              render={({ field }) => (
                <Select
                  {...field}
                  id="source"
                  aria-label="From account"
                  disabled={locked}
                  aria-invalid={!!form.formState.errors.source_account_id}
                  aria-describedby={
                    form.formState.errors.source_account_id
                      ? 'source_account_id-error'
                      : 'source-balance'
                  }
                  options={eligible.map((a) => ({
                    value: a.id,
                    label: `${a.name} · ${a.account_number}`,
                    description: `${formatVND(a.balance_vnd)} available · VND account`,
                  }))}
                />
              )}
            />
            {source && (
              <small className="available" id="source-balance">
                Available balance <strong>{formatVND(source.balance_vnd)}</strong>
              </small>
            )}
            {fieldError('source_account_id')}
          </div>
          <div className="form-section-heading">
            <span>02</span>
            <div>
              <h3>Who are you sending to?</h3>
              <p>Only fictional accounts in this demo.</p>
            </div>
          </div>
          <div className="field">
            <div className="label-row">
              <label htmlFor="saved-recipient">Saved recipient</label>
              <Link className="text-link" to="/beneficiaries">
                Manage recipients
              </Link>
            </div>
            <Select
              id="saved-recipient"
              disabled={locked}
              value={
                recipients.data?.find(
                  (row) => row.destination_account_id === form.watch('destination_account_id'),
                )?.id || ''
              }
              onChange={(value) =>
                form.setValue(
                  'destination_account_id',
                  recipients.data?.find((row) => row.id === value)?.destination_account_id || '',
                  { shouldValidate: true },
                )
              }
              options={[
                { value: '', label: 'Enter an account ID manually' },
                ...(recipients.data || []).map((row) => ({
                  value: row.id,
                  label: row.nickname,
                  description: `Fictional account · ${row.destination_account_id.slice(-6)}`,
                })),
              ]}
            />
          </div>
          <div className="field">
            <div className="label-row">
              <label htmlFor="recipient">Recipient account ID</label>
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  form.setValue(
                    'destination_account_id',
                    source?.id === BOB_ACCOUNT ? ALICE_ACCOUNT : BOB_ACCOUNT,
                    { shouldValidate: true },
                  )
                }
              >
                <UserRound size={13} /> Use {source?.id === BOB_ACCOUNT ? 'Alice' : 'Bob'}’s demo
                account
              </button>
            </div>
            <input
              id="recipient"
              placeholder="00000000-0000-4000-8000-000000000002"
              {...form.register('destination_account_id')}
              aria-invalid={!!form.formState.errors.destination_account_id}
              aria-describedby="destination_account_id-error"
            />
            {fieldError('destination_account_id')}
          </div>
          <div className="form-section-heading">
            <span>03</span>
            <div>
              <h3>A few final details</h3>
              <p>VND is a whole-number currency.</p>
            </div>
          </div>
          <div className="field">
            <label htmlFor="amount">Amount</label>
            <div className="amount-input">
              <input
                id="amount"
                inputMode="numeric"
                placeholder="0"
                {...form.register('amount', {
                  onChange: (e) => {
                    const v = e.target.value.replaceAll(',', '');
                    if (/^\d*$/.test(v)) e.target.value = v.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                  },
                })}
                aria-invalid={!!form.formState.errors.amount}
                aria-describedby="amount-error"
              />
              <span>VND</span>
            </div>
            {fieldError('amount')}
          </div>
          <div className="field">
            <label htmlFor="memo">
              Memo <span className="muted">(optional)</span>
            </label>
            <input
              id="memo"
              placeholder="What’s this transfer for?"
              maxLength={200}
              {...form.register('memo')}
              aria-describedby="memo-error"
            />
            {fieldError('memo')}
          </div>
          <div className="form-footer">
            <span>
              <LockKeyhole size={14} /> Secure, simulated transfer
            </span>
            <button className="button primary" disabled={locked || !eligible.length}>
              {preview.isPending ? 'Checking transfer…' : 'Review transfer'}{' '}
              <ArrowRight size={16} />
            </button>
          </div>
        </fieldset>
      </form>
      {attempt && !uncertain && (
        <ConfirmTransferDialog
          attempt={attempt}
          pending={mutation.isPending}
          confirm={send}
          cancel={() => setAttempt(null)}
        />
      )}
      {(mutation.error || preview.error) && <ErrorAlert error={mutation.error || preview.error} />}
      {!eligible.length && (
        <p role="status">No active source accounts. Frozen and closed accounts cannot send.</p>
      )}
      {recipients.error && (
        <ErrorAlert error={recipients.error} retry={() => void recipients.refetch()} />
      )}
      {uncertain && (
        <div className="retry-panel">
          <p>
            Status unknown — check transaction history or retry safely. Your original amount,
            recipient and request key are preserved.
          </p>
          <button className="button primary" disabled={mutation.isPending} onClick={send}>
            {mutation.isPending ? 'Checking…' : 'Retry original transfer'} <Check size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
