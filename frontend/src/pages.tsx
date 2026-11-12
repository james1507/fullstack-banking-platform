import { useState } from 'react';
import { Link, Navigate, useLocation, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  ArrowDownLeft,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  CreditCard,
  Fingerprint,
  Landmark,
  LockKeyhole,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from './auth';
import { api } from './lib/api';
import { formatDate, formatVND } from './lib/format';
import {
  AccountCard,
  BalanceSummary,
  EmptyState,
  ErrorAlert,
  LoadingSkeleton,
  Pagination,
  StatusBadge,
  TransactionTable,
} from './components/ui';
import { Select } from './components/Select';
import { TransferForm } from './TransferForm';

const loginSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});
export function LoginPage() {
  const { user, loading, login } = useAuth();
  const [error, setError] = useState<unknown>(null);
  const location = useLocation();
  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: 'alice@example.test', password: 'DemoPass123!' },
  });
  async function submit(values: z.infer<typeof loginSchema>) {
    setError(null);
    try {
      await login(values.email, values.password);
    } catch (e) {
      setError(e);
    }
  }
  if (loading)
    return (
      <main className="session-screen">
        <LoadingSkeleton />
      </main>
    );
  const from =
    typeof location.state?.from === 'string' &&
    location.state.from.startsWith('/') &&
    !location.state.from.startsWith('//')
      ? location.state.from
      : '/';
  if (user) return <Navigate to={from} replace />;
  return (
    <main className="login-layout">
      <section className="login-story">
        <Link to="/" className="brand">
          <span className="brand-symbol">m</span> moneta.
        </Link>
        <div className="login-story-content">
          <span className="eyebrow light">FICTIONAL MONEY. REAL POSSIBILITIES.</span>
          <h1>
            Make room
            <br />
            for better
            <br />
            <em>banking.</em>
          </h1>
          <p>
            A little clarity. A lot of confidence.
            <br />
            Your everyday finances, thoughtfully connected.
          </p>
          <div className="login-feature">
            <ShieldCheck size={20} />
            <span>
              Secure by design.<small>Atomic transfers. Protected sessions. Peace of mind.</small>
            </span>
          </div>
        </div>
        <span className="login-story-footer">
          A full-stack banking simulation · Portfolio edition
        </span>
        <div className="login-orbit" aria-hidden="true" />
      </section>
      <section className="login-form-side">
        <span className="demo-badge">
          <span /> Demo · Simulated money
        </span>
        <div className="login-form-wrap">
          <div className="login-lock">
            <Fingerprint size={28} />
          </div>
          <span className="eyebrow">YOUR PERSONAL WORKSPACE</span>
          <h2>Welcome back.</h2>
          <p className="muted">Sign in. Take a look around. Make yourself at home.</p>
          <form onSubmit={form.handleSubmit(submit)} noValidate>
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                {...form.register('email')}
                aria-invalid={!!form.formState.errors.email}
                aria-describedby="email-error"
              />
              {form.formState.errors.email && (
                <p className="field-error" id="email-error">
                  {form.formState.errors.email.message}
                </p>
              )}
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                {...form.register('password')}
                aria-invalid={!!form.formState.errors.password}
                aria-describedby="password-error"
              />
              {form.formState.errors.password && (
                <p className="field-error" id="password-error">
                  {form.formState.errors.password.message}
                </p>
              )}
            </div>
            {error != null && <ErrorAlert error={error} />}
            <button className="button primary login-submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? 'Signing in…' : 'Sign in to your workspace'}{' '}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="demo-credentials">
            <span className="eyebrow">TAKE IT FOR A TEST DRIVE</span>
            <p>
              Demo credentials are prefilled. Switch to{' '}
              <button
                className="text-button"
                onClick={() =>
                  form.setValue(
                    'email',
                    form.getValues('email') === 'alice@example.test'
                      ? 'bob@example.test'
                      : 'alice@example.test',
                  )
                }
              >
                {form.watch('email') === 'alice@example.test' ? 'Bob' : 'Alice'}’s account
              </button>{' '}
              to see the other side.
            </p>
            <code>DemoPass123!</code>
            <small>Development credentials only. Never use real banking details.</small>
          </div>
        </div>
        <div className="login-bottom">
          <LockKeyhole size={13} /> No real money or personal information required.
        </div>
      </section>
    </main>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function DashboardPage() {
  const { user } = useAuth();
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary });
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  if (summary.isPending || accounts.isPending) return <LoadingSkeleton />;
  if (summary.error || accounts.error)
    return (
      <ErrorAlert
        error={summary.error || accounts.error}
        retry={() => {
          void summary.refetch();
          void accounts.refetch();
        }}
      />
    );
  const s = summary.data;
  const items = accounts.data || [];
  if (user?.role === 'OPERATIONS') return <Navigate to="/ops" replace />;
  if (user?.role === 'AUDITOR') return <Navigate to="/audit" replace />;
  return (
    <>
      <PageHeading
        eyebrow="A LITTLE CLARITY FOR YOUR DAY"
        title={`Looking good, ${user?.display_name}.`}
        description="Here’s what’s happening with your money today."
        action={
          <Link className="button primary" to="/transfers/new">
            <ArrowUpRight size={17} /> Send money
          </Link>
        }
      />
      <div className="dashboard-grid">
        <div className="dashboard-main">
          <BalanceSummary balance={s.total_balance_vnd} count={s.account_count} />
          <div className="stats-row">
            <div className="stat">
              <span className="stat-icon">
                <CreditCard size={18} />
              </span>
              <div>
                <p>Active accounts</p>
                <strong>
                  {String(items.filter((account) => account.status === 'ACTIVE').length).padStart(
                    2,
                    '0',
                  )}
                </strong>
              </div>
              <span className="stat-label">All in VND</span>
            </div>
            <div className="stat">
              <span className="stat-icon">
                <ArrowLeftRightIcon />
              </span>
              <div>
                <p>Total transfers</p>
                <strong>{String(s.transfer_count).padStart(2, '0')}</strong>
              </div>
              <span className="stat-label">Completed</span>
            </div>
          </div>
          <section className="panel transactions-panel">
            <div className="section-heading">
              <div>
                <h2>Recent activity</h2>
                <p>Your latest moves, all in one place.</p>
              </div>
              <Link className="text-link" to="/transfers">
                View all <ArrowRight size={14} />
              </Link>
            </div>
            <TransactionTable transfers={s.recent_transfers} accounts={items} />
          </section>
        </div>
        <aside className="dashboard-aside">
          <section>
            <div className="section-heading compact">
              <h2>Your accounts</h2>
              <Link className="text-link" to="/accounts">
                View all <ArrowUpRight size={14} />
              </Link>
            </div>
            {items[0] && <AccountCard account={items[0]} />}
            <Link to="/transfers/new" className="quick-transfer">
              <span className="quick-icon">
                <ArrowUpRight size={20} />
              </span>
              <div>
                <strong>Make someone’s day</strong>
                <small>Send a demo transfer</small>
              </div>
              <ArrowRight size={16} />
            </Link>
          </section>
          <section className="peace-card">
            <div className="peace-illustration">
              <div className="shield-ring">
                <ShieldCheck size={34} strokeWidth={1.4} />
              </div>
              <span className="check-orbit">
                <Check size={12} />
              </span>
            </div>
            <span className="eyebrow">BUILT FOR PEACE OF MIND</span>
            <h3>
              Every transfer.
              <br />
              Accounted for.
            </h3>
            <p>
              Protected sessions, balanced ledgers and safe retries. Good engineering works quietly.
            </p>
            <Link className="text-link" to="/about">
              Under the hood <ArrowUpRight size={14} />
            </Link>
          </section>
          <div className="environment-note">
            <span className="live-dot" />
            <span>
              Sandbox is ready<small>Explore freely. It’s all simulated.</small>
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
function ArrowLeftRightIcon() {
  return (
    <>
      <ArrowUpRight size={18} />
    </>
  );
}
export function AccountsPage() {
  const query = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  return (
    <>
      <PageHeading
        eyebrow="A HOME FOR YOUR MONEY"
        title="Your accounts."
        description="Every balance. Every account. One clear picture."
        action={
          <Link className="button primary" to="/accounts/new">
            Open demo account <ArrowUpRight size={17} />
          </Link>
        }
      />
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.error ? (
        <ErrorAlert error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <div className="accounts-grid">
            {query.data.map((a) => (
              <AccountCard key={a.id} account={a} dark />
            ))}
          </div>
          <section className="panel account-details">
            <h2>Account details</h2>
            <p className="muted">Share a demo account ID to receive a simulated transfer.</p>
            {query.data.map((a) => (
              <div key={a.id}>
                <Landmark size={21} />
                <span>
                  <strong>{a.account_number}</strong>
                  <code>{a.id}</code>
                </span>
                <span className="status-badge">
                  {a.status} · {a.account_type}
                </span>
              </div>
            ))}
          </section>
        </>
      )}
    </>
  );
}
export function NewTransferPage() {
  const query = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  return (
    <>
      <PageHeading
        eyebrow="GOOD THINGS ARE MEANT TO MOVE"
        title="Send a little possibility."
        description="A simple, secure transfer. From your account to theirs."
      />
      <div className="transfer-layout">
        <section className="panel">
          {query.isPending ? (
            <LoadingSkeleton />
          ) : query.error ? (
            <ErrorAlert error={query.error} retry={() => void query.refetch()} />
          ) : !query.data.length ? (
            <EmptyState title="No source accounts" />
          ) : (
            <TransferForm accounts={query.data} />
          )}
        </section>
        <aside>
          <div className="transfer-guide">
            <span className="guide-icon">
              <ArrowDownLeft size={26} />
            </span>
            <h3>
              Small steps.
              <br />
              Safely delivered.
            </h3>
            <p>
              Every transfer in this workspace uses fictional VND. No fees, no real-world payments.
            </p>
            <ul>
              <li>
                <CheckCheck size={17} /> Review before you send
              </li>
              <li>
                <CheckCheck size={17} /> Instant balance updates
              </li>
              <li>
                <CheckCheck size={17} /> Safe to retry after a timeout
              </li>
            </ul>
          </div>
          <p className="transfer-hint">
            <LockKeyhole size={15} /> Your transfer is protected against duplicate processing, even
            if your connection drops.
          </p>
        </aside>
      </div>
    </>
  );
}
export function HistoryPage() {
  const [page, setPage] = useState(1);
  const [direction, setDirection] = useState('');
  const [reference, setReference] = useState('');
  const [accountId, setAccountId] = useState('');
  const params = new URLSearchParams({
    page: String(page),
    page_size: '10',
    ...(direction && { direction }),
    ...(reference && { reference }),
    ...(accountId && { account_id: accountId }),
  }).toString();
  const query = useQuery({ queryKey: ['history', params], queryFn: () => api.history(params) });
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  return (
    <>
      <div className="action-row">
        <Link className="text-link" to="/transfers/search">
          Advanced search
        </Link>
        <Link className="text-link" to="/statements">
          Account statements
        </Link>
      </div>
      <PageHeading
        eyebrow="EVERY MOVE TELLS A STORY"
        title="Your transactions."
        description="Follow your money. Find the details. Stay in the know."
        action={
          <Link className="button primary" to="/transfers/new">
            <ArrowUpRight size={17} /> Send money
          </Link>
        }
      />
      <section className="panel history-panel">
        <div className="history-filters">
          <div className="search-field">
            <Search size={17} />
            <input
              aria-label="Search reference"
              placeholder="Search by reference…"
              value={reference}
              maxLength={50}
              onChange={(e) => {
                setReference(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <Select
            aria-label="Filter direction"
            value={direction}
            onChange={(value) => {
              setDirection(value);
              setPage(1);
            }}
            options={[
              {
                value: '',
                label: 'All directions',
                description: 'Incoming and outgoing transfers',
              },
              { value: 'OUTGOING', label: 'Money out', description: 'Sent from your accounts' },
              { value: 'INCOMING', label: 'Money in', description: 'Received by your accounts' },
            ]}
          />
          <Select
            aria-label="Filter account"
            value={accountId}
            onChange={(value) => {
              setAccountId(value);
              setPage(1);
            }}
            options={[
              { value: '', label: 'All accounts', description: 'Activity across your accounts' },
              ...(accounts.data || []).map((a) => ({
                value: a.id,
                label: a.account_number,
                description: a.name,
              })),
            ]}
          />
        </div>
        {query.isPending || accounts.isPending ? (
          <LoadingSkeleton />
        ) : query.error || accounts.error ? (
          <ErrorAlert
            error={query.error || accounts.error}
            retry={() => {
              void query.refetch();
              void accounts.refetch();
            }}
          />
        ) : (
          query.data && (
            <>
              <div className="history-count">
                {query.data.total} {query.data.total === 1 ? 'transaction' : 'transactions'} found
              </div>
              <TransactionTable transfers={query.data.items} accounts={accounts.data || []} />
              <Pagination page={page} totalPages={query.data.total_pages} onChange={setPage} />
            </>
          )
        )}
      </section>
    </>
  );
}
export function ReceiptPage() {
  const { id } = useParams();
  const location = useLocation();
  const query = useQuery({ queryKey: ['receipt', id], queryFn: () => api.receipt(id!) });
  if (query.isPending) return <LoadingSkeleton />;
  if (query.error) return <ErrorAlert error={query.error} retry={() => void query.refetch()} />;
  const t = query.data;
  return (
    <div className="receipt-wrap">
      <Link className="text-link" to="/transfers">
        <ArrowLeft size={16} /> Back to transactions
      </Link>
      <article className="panel receipt">
        <div className="receipt-check">
          <Check size={32} />
        </div>
        <span className="eyebrow">
          {location.state?.fresh ? 'NICE. YOU MADE YOUR MOVE.' : 'TRANSFER RECEIPT'}
        </span>
        <h1>Transfer complete.</h1>
        <p>Your simulated money is right where it should be.</p>
        <h2>{formatVND(t.amount_vnd)}</h2>
        <StatusBadge />
        <dl>
          <div>
            <dt>Reference</dt>
            <dd className="reference-code">{t.reference}</dd>
          </div>
          <div>
            <dt>Date</dt>
            <dd>{formatDate(t.created_at)}</dd>
          </div>
          <div>
            <dt>From account</dt>
            <dd>
              <code>{t.source_account_id}</code>
            </dd>
          </div>
          <div>
            <dt>To account</dt>
            <dd>
              <code>{t.destination_account_id}</code>
            </dd>
          </div>
          <div>
            <dt>Memo</dt>
            <dd>{t.memo || '—'}</dd>
          </div>
          <div>
            <dt>Transfer fee</dt>
            <dd>{formatVND(0)}</dd>
          </div>
        </dl>
        <Link className="button primary" to="/transfers/new">
          Make another transfer <ArrowUpRight size={16} />
        </Link>
        <button className="button secondary" onClick={() => window.print()}>
          Print receipt
        </button>
        <Link className="text-link receipt-home" to="/">
          Back to overview
        </Link>
        <small className="muted">Demo receipt · Simulated money only</small>
      </article>
    </div>
  );
}
export function AboutPage() {
  return (
    <>
      <PageHeading
        eyebrow="FICTIONAL MONEY. REAL ENGINEERING."
        title="Thoughtfully built."
        description="Moneta is a full-stack portfolio project, built to make the invisible work visible."
      />
      <section className="panel about-panel">
        <ShieldCheck size={36} />
        <h2>A safe banking simulation</h2>
        <p>
          Explore sign-in, account balances, transfers and transaction history with synthetic
          accounts. No real banks, payments or customer information are involved.
        </p>
        <h3>What happens when you send money?</h3>
        <p>
          FastAPI validates your request and account ownership. PostgreSQL locks both accounts in a
          consistent order, updates balances and writes two immutable ledger entries in one
          transaction. Your request key and exact result commit together, so retries cannot send
          twice.
        </p>
        <h3>What protects your session?</h3>
        <p>
          Short-lived access tokens stay in memory. HttpOnly refresh cookies rotate on use. Reusing
          a rotated token revokes its session family. Origin checks protect cookie-based actions.
        </p>
        <h3>Built with</h3>
        <p>
          React · TypeScript · Tailwind CSS · TanStack Query · FastAPI · SQLAlchemy · PostgreSQL 16
          · Playwright
        </p>
        <Link className="button secondary" to="/">
          Back to workspace <ArrowRight size={16} />
        </Link>
      </section>
    </>
  );
}
export function NotFoundPage() {
  return (
    <div className="not-found">
      <span className="eyebrow">404 · A LITTLE OFF THE PATH</span>
      <h1>Nothing here. Yet.</h1>
      <p>This page doesn’t exist. Your workspace is right this way.</p>
      <Link to="/" className="button primary">
        <ArrowLeft size={16} /> Back to overview
      </Link>
    </div>
  );
}
