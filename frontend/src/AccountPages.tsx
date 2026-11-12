import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from './lib/api';
import { formatVND } from './lib/format';
import { PageHeading } from './pages';
import { Select } from './components/Select';
import { ErrorAlert, LoadingSkeleton, TransactionTable } from './components/ui';

export function NewAccountPage() {
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [type, setType] = useState<'CHECKING' | 'SAVINGS'>('SAVINGS');
  const mutation = useMutation({
    mutationFn: api.openAccount,
    onSuccess: async (account) => {
      await Promise.all(
        ['accounts', 'summary'].map((key) => cache.invalidateQueries({ queryKey: [key] })),
      );
      navigate(`/accounts/${account.id}`);
    },
  });
  return (
    <>
      <PageHeading
        eyebrow="MAKE ROOM FOR YOUR PLANS"
        title="Open a demo account."
        description="A fresh start at zero VND. Move fictional funds from another account whenever you’re ready."
      />
      <section className="panel settings-panel">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            mutation.mutate({ name: String(data.get('name')).trim(), account_type: type });
          }}
        >
          <div className="field">
            <label htmlFor="account-name">Account nickname</label>
            <input
              id="account-name"
              name="name"
              required
              maxLength={100}
              placeholder="Travel savings"
            />
          </div>
          <div className="field">
            <label htmlFor="account-type">Account type</label>
            <Select
              id="account-type"
              value={type}
              onChange={(value) => setType(value as typeof type)}
              options={[
                {
                  value: 'SAVINGS',
                  label: 'Savings',
                  description: 'A separate place for your plans. No interest is simulated.',
                },
                {
                  value: 'CHECKING',
                  label: 'Checking',
                  description: 'Everyday internal demo transfers.',
                },
              ]}
            />
          </div>
          <p className="muted">
            Opening an account creates no money. No fees, interest or real bank connection.
          </p>
          {mutation.error && <ErrorAlert error={mutation.error} />}
          <div className="action-row">
            <Link className="button secondary" to="/accounts">
              Cancel
            </Link>
            <button className="button primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Opening…' : 'Open zero-balance account'}
            </button>
          </div>
        </form>
      </section>
    </>
  );
}

export function AccountDetailPage() {
  const { id = '' } = useParams();
  const cache = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [validation, setValidation] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const account = useQuery({ queryKey: ['account', id], queryFn: () => api.account(id) });
  const history = useQuery({
    queryKey: ['history', 'account', id],
    queryFn: () => api.history(`account_id=${id}&page_size=10`),
  });
  async function refresh() {
    await Promise.all(
      ['account', 'accounts', 'summary', 'history'].map((key) =>
        cache.invalidateQueries({ queryKey: [key] }),
      ),
    );
  }
  const update = useMutation({
    mutationFn: (payload: { name: string; daily_outgoing_limit_vnd: number | null }) =>
      api.updateAccount(id, payload),
    onSuccess: async () => {
      setNotice('Account settings saved.');
      await refresh();
    },
  });
  const close = useMutation({
    mutationFn: () => api.closeAccount(id),
    onSuccess: async () => {
      setNotice('Account closed. History remains available.');
      setConfirmed(false);
      await refresh();
    },
  });
  if (account.isPending) return <LoadingSkeleton />;
  if (account.error)
    return <ErrorAlert error={account.error} retry={() => void account.refetch()} />;
  const row = account.data;
  return (
    <>
      <PageHeading
        eyebrow={`${row.account_type} · ${row.status}`}
        title={row.name}
        description={`${row.account_number} · Fictional VND account`}
        action={
          <Link className="button secondary" to="/accounts">
            All accounts
          </Link>
        }
      />
      <div className="detail-grid">
        <section className="panel settings-panel">
          <span className="eyebrow">CURRENT BALANCE</span>
          <h2 className="detail-balance">{formatVND(row.balance_vnd)}</h2>
          <code className="break-id">{row.id}</code>
          {notice && (
            <p role="status" className="success-notice">
              {notice}
            </p>
          )}
          <form
            key={row.id}
            onSubmit={(event) => {
              event.preventDefault();
              setValidation(null);
              setNotice('');
              const data = new FormData(event.currentTarget);
              const raw = String(data.get('limit')).trim();
              const limit = raw ? Number(raw) : null;
              if (raw && (!/^\d+$/.test(raw) || !Number.isSafeInteger(limit) || limit! <= 0)) {
                setValidation(new Error('Enter a positive whole VND limit, or leave it empty.'));
                return;
              }
              update.mutate({
                name: String(data.get('name')).trim(),
                daily_outgoing_limit_vnd: limit,
              });
            }}
          >
            <fieldset disabled={row.status === 'CLOSED' || update.isPending || close.isPending}>
              <div className="field">
                <label htmlFor="rename">Account nickname</label>
                <input id="rename" name="name" defaultValue={row.name} required maxLength={100} />
              </div>
              <div className="field">
                <label htmlFor="daily-limit">Daily outgoing limit (VND)</label>
                <input
                  id="daily-limit"
                  name="limit"
                  inputMode="numeric"
                  defaultValue={row.daily_outgoing_limit_vnd ?? ''}
                  aria-describedby="limit-help"
                />
                <small id="limit-help">
                  UTC calendar day. Includes transfers between your accounts. Leave empty for no
                  configured daily limit.
                </small>
              </div>
              {(validation || update.error) && <ErrorAlert error={validation || update.error} />}
              <button className="button primary">
                {update.isPending ? 'Saving…' : 'Save account settings'}
              </button>
            </fieldset>
          </form>
        </section>
        <section className="panel settings-panel">
          <h2>Account controls</h2>
          <Link className="button secondary" to={`/statements?account=${row.id}`}>
            View statements
          </Link>
          <p className="muted">
            Frozen accounts can receive funds but cannot send. Closed accounts cannot send or
            receive and remain visible in history.
          </p>
          {row.status === 'ACTIVE' && (
            <Link className="button secondary" to={`/transfers/new?source=${row.id}`}>
              Move money
            </Link>
          )}
          <div className="close-account">
            <h3>Close this demo account</h3>
            <p className="muted">
              Move all funds and cancel your linked schedules first. Closure is permanent;
              transaction history stays intact.
            </p>
            <label className="check-label">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={row.status === 'CLOSED' || row.balance_vnd !== 0}
                onChange={(event) => setConfirmed(event.target.checked)}
              />{' '}
              I confirm this account should be closed.
            </label>
            {close.error && <ErrorAlert error={close.error} />}
            <button
              className="button secondary"
              disabled={
                !confirmed || close.isPending || row.status === 'CLOSED' || row.balance_vnd !== 0
              }
              onClick={() => close.mutate()}
            >
              {close.isPending ? 'Closing…' : 'Close account'}
            </button>
          </div>
        </section>
      </div>
      <section className="panel transactions-panel">
        <div className="section-heading">
          <h2>Account activity</h2>
          <Link to="/transfers" className="text-link">
            All transactions
          </Link>
        </div>
        {history.isPending ? (
          <LoadingSkeleton />
        ) : history.error ? (
          <ErrorAlert error={history.error} retry={() => void history.refetch()} />
        ) : (
          <TransactionTable transfers={history.data.items} accounts={[row]} />
        )}
      </section>
    </>
  );
}
