import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from './auth';
import { api } from './lib/api';
import { formatVND } from './lib/format';
import { PageHeading } from './pages';
import { Select } from './components/Select';
import { EmptyState, ErrorAlert, LoadingSkeleton, TransactionTable } from './components/ui';

export function AdvancedHistoryPage() {
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  const [account, setAccount] = useState('');
  const [direction, setDirection] = useState('');
  const [filters, setFilters] = useState('page_size=10');
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [error, setError] = useState<Error | null>(null);
  const params = new URLSearchParams(filters);
  const cursor = cursors.at(-1);
  if (cursor) params.set('cursor', cursor);
  const history = useQuery({
    queryKey: ['history', 'search', filters, cursor],
    queryFn: () => api.searchTransfers(params.toString()),
  });
  return (
    <>
      <PageHeading
        eyebrow="FIND THE DETAILS THAT MATTER"
        title="Explore transactions."
        description="Server-side filters and stable cursor navigation. Only committed internal transfers involving your accounts appear."
        action={
          <Link className="button secondary" to="/transfers">
            Simple history
          </Link>
        }
      />
      <section className="panel settings-panel search-panel">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setError(null);
            const data = new FormData(event.currentTarget);
            const from = String(data.get('date_from'));
            const to = String(data.get('date_to'));
            if (Boolean(from) !== Boolean(to)) {
              setError(new Error('Choose both start and end dates.'));
              return;
            }
            const next = new URLSearchParams({ page_size: '10' });
            for (const key of ['reference', 'date_from', 'date_to', 'min_amount', 'max_amount']) {
              const value = String(data.get(key)).trim();
              if (value) next.set(key, value);
            }
            if (account) next.set('account_id', account);
            if (direction) next.set('direction', direction);
            setFilters(next.toString());
            setCursors([null]);
          }}
        >
          <div className="filter-grid">
            <div className="field">
              <label htmlFor="search-account">Account</label>
              <Select
                id="search-account"
                value={account}
                onChange={setAccount}
                options={[
                  { value: '', label: 'All your accounts' },
                  ...(accounts.data || []).map((row) => ({
                    value: row.id,
                    label: row.name,
                    description: row.account_number,
                  })),
                ]}
              />
            </div>
            <div className="field">
              <label htmlFor="search-direction">Direction</label>
              <Select
                id="search-direction"
                value={direction}
                onChange={setDirection}
                options={[
                  { value: '', label: 'All directions' },
                  { value: 'OUTGOING', label: 'Outgoing' },
                  { value: 'INCOMING', label: 'Incoming' },
                ]}
              />
            </div>
            <div className="field">
              <label htmlFor="search-reference">Reference contains</label>
              <input id="search-reference" name="reference" maxLength={50} />
            </div>
            <div className="field">
              <label htmlFor="search-from">From date</label>
              <input id="search-from" name="date_from" type="date" />
            </div>
            <div className="field">
              <label htmlFor="search-to">Through date</label>
              <input id="search-to" name="date_to" type="date" />
            </div>
            <div className="field">
              <label htmlFor="search-minimum">Minimum VND</label>
              <input id="search-minimum" name="min_amount" inputMode="numeric" pattern="[0-9]+" />
            </div>
            <div className="field">
              <label htmlFor="search-maximum">Maximum VND</label>
              <input id="search-maximum" name="max_amount" inputMode="numeric" pattern="[0-9]+" />
            </div>
          </div>
          <p className="muted">
            Newest first, using timestamp and ID. Dates follow your profile timezone; both bounds
            are inclusive, up to 366 days.
          </p>
          {error && <ErrorAlert error={error} />}
          <button className="button primary" disabled={history.isFetching}>
            Apply search filters
          </button>
        </form>
      </section>
      {accounts.error && (
        <ErrorAlert error={accounts.error} retry={() => void accounts.refetch()} />
      )}
      <section className="panel transactions-panel">
        {history.isPending ? (
          <LoadingSkeleton />
        ) : history.error ? (
          <ErrorAlert error={history.error} retry={() => void history.refetch()} />
        ) : (
          <>
            <TransactionTable transfers={history.data.items} accounts={accounts.data || []} />
            <nav className="pagination" aria-label="Cursor pagination">
              <span>Page {cursors.length} · Committed transfers</span>
              <div>
                <button
                  className="button secondary"
                  disabled={cursors.length === 1 || history.isFetching}
                  onClick={() => setCursors((value) => value.slice(0, -1))}
                >
                  Previous results
                </button>
                <button
                  className="button secondary"
                  disabled={!history.data.next_cursor || history.isFetching}
                  onClick={() => setCursors((value) => [...value, history.data.next_cursor])}
                >
                  Next results
                </button>
              </div>
            </nav>
          </>
        )}
      </section>
    </>
  );
}

function localDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

export function StatementsPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  const [selected, setSelected] = useState(params.get('account') || '');
  const [filters, setFilters] = useState<{ accountId: string; params: string } | null>(null);
  const accountId =
    accounts.data?.find((row) => row.id === selected)?.id || accounts.data?.[0]?.id || '';
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const report = useQuery({
    queryKey: ['statement', filters],
    queryFn: () => api.statementSummary(filters!.accountId, filters!.params),
    enabled: filters !== null,
  });
  const download = useMutation({
    mutationFn: () => api.exportStatement(filters!.accountId, filters!.params),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `moneta-${filters!.accountId}.csv`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
  const data = report.data;
  return (
    <>
      <PageHeading
        eyebrow="EVERY MOVEMENT. A CLEAR RECORD."
        title="Account statements."
        description="Reconciled from immutable ledger entries and the account’s opening baseline. Fictional internal transfers only."
      />
      <section className="panel settings-panel search-panel">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            download.reset();
            const values = new FormData(event.currentTarget);
            setFilters({
              accountId,
              params: new URLSearchParams({
                date_from: String(values.get('from')),
                date_to: String(values.get('to')),
                timezone: user!.timezone,
              }).toString(),
            });
          }}
        >
          <div className="filter-grid">
            <div className="field">
              <label htmlFor="statement-account">Statement account</label>
              <Select
                id="statement-account"
                value={accountId}
                onChange={setSelected}
                options={(accounts.data || []).map((row) => ({
                  value: row.id,
                  label: row.name,
                  description: `${row.account_number} · ${row.status}`,
                }))}
              />
            </div>
            <div className="field">
              <label htmlFor="statement-from">Statement from</label>
              <input
                id="statement-from"
                name="from"
                type="date"
                required
                defaultValue={localDate(first)}
              />
            </div>
            <div className="field">
              <label htmlFor="statement-to">Statement through</label>
              <input
                id="statement-to"
                name="to"
                type="date"
                required
                defaultValue={localDate(now)}
              />
            </div>
          </div>
          <p className="muted">
            Timezone: {user?.timezone}. Inclusive local dates, up to 366 days and 5,000 rows. If the
            account opened later, the statement begins at account creation.
          </p>
          <button className="button primary" disabled={!accountId || report.isFetching}>
            Build statement
          </button>
        </form>
      </section>
      {accounts.error && (
        <ErrorAlert error={accounts.error} retry={() => void accounts.refetch()} />
      )}
      {!filters ? (
        <section className="panel">
          <EmptyState title="Choose your account and period">
            A consistent database snapshot produces each statement. Exported CSV includes UTC/local
            timestamps and safe spreadsheet text.
          </EmptyState>
        </section>
      ) : report.isPending ? (
        <LoadingSkeleton />
      ) : report.error ? (
        <ErrorAlert error={report.error} retry={() => void report.refetch()} />
      ) : (
        data && (
          <section className="panel settings-panel search-panel">
            <span className="eyebrow">
              {data.account_number} · {data.date_from} — {data.date_to}
            </span>
            <h2>Statement summary</h2>
            <dl className="statement-totals">
              <div>
                <dt>Opening balance</dt>
                <dd>{formatVND(BigInt(data.opening_balance_vnd))}</dd>
              </div>
              <div>
                <dt>Total credits</dt>
                <dd>{formatVND(BigInt(data.total_credit_vnd))}</dd>
              </div>
              <div>
                <dt>Total debits</dt>
                <dd>{formatVND(BigInt(data.total_debit_vnd))}</dd>
              </div>
              <div>
                <dt>Closing balance</dt>
                <dd>{formatVND(BigInt(data.closing_balance_vnd))}</dd>
              </div>
            </dl>
            <p className="muted">
              {data.row_count} posted movements. Opening + credits − debits = closing. Synthetic
              seed funding is an opening baseline, not a customer top-up.
            </p>
            <button
              className="button primary"
              disabled={download.isPending}
              onClick={() => download.mutate()}
            >
              {download.isPending ? 'Preparing CSV…' : 'Download CSV statement'}
            </button>
            {download.error && <ErrorAlert error={download.error} />}
            <small>
              Exports are owner-only and audited. No real banking statement or regulatory document
              is produced.
            </small>
          </section>
        )
      )}
    </>
  );
}
