import type { ReactNode } from 'react';
import {
  AlertCircle,
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Inbox,
  Landmark,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { APIError, type Account, type Transfer } from '../lib/api';
import { formatDate, formatVND, shortId } from '../lib/format';

export function ErrorAlert({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof Error ? error.message : 'Something went wrong. Please try again.';
  return (
    <div role="alert" className="error-alert">
      <AlertCircle size={18} />
      <div>
        <strong>{message}</strong>
        {error instanceof APIError && error.requestId && (
          <small>Request ID: {error.requestId}</small>
        )}
        {retry && (
          <button className="text-button" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function LoadingSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="skeleton-stack">
      <span className="sr-only">Loading…</span>
      <div className="skeleton h-32" />
      <div className="skeleton h-20" />
      <div className="skeleton h-20" />
    </div>
  );
}
export function EmptyState({
  title = 'A fresh start',
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Inbox size={26} />
      </span>
      <h3>{title}</h3>
      <p>
        {children ??
          'Your transfers will appear here. Send your first simulated transfer to get started.'}
      </p>
    </div>
  );
}
export function StatusBadge() {
  return (
    <span className="status-badge">
      <Check size={12} /> Completed
    </span>
  );
}
export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  return (
    <nav aria-label="Pagination" className="pagination">
      <span>
        Page {page} of {Math.max(totalPages, 1)}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <button
          className="icon-button"
          aria-label="Next page"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </nav>
  );
}
export function AccountCard({ account, dark = false }: { account: Account; dark?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(account.id);
      setCopied(true);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  }
  return (
    <article className={`account-card ${dark ? 'dark-card' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="card-icon">
          <Landmark size={19} />
        </span>
        <span className="account-currency">VND ACCOUNT</span>
      </div>
      <div>
        <p>{account.name}</p>
        <h3>{formatVND(account.balance_vnd)}</h3>
      </div>
      <div className="card-bottom">
        <span>{account.account_number}</span>
        <button
          title={account.id}
          aria-label={`Copy account ID for ${account.name}`}
          onClick={() => void copy()}
        >
          {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? 'Copied' : 'Copy ID'}
        </button>
      </div>
      {copyError && <small role="alert">Copy manually: {account.id}</small>}
    </article>
  );
}
export function BalanceSummary({ balance, count }: { balance: number; count: number }) {
  return (
    <section className="balance-hero">
      <div className="balance-content">
        <span className="eyebrow light">YOUR MONEY, AT A GLANCE</span>
        <p>Total available balance</p>
        <h2>{formatVND(balance)}</h2>
        <span className="balance-foot">
          <span className="live-dot" /> Across {count} {count === 1 ? 'account' : 'accounts'} ·
          Vietnamese đồng
        </span>
      </div>
      <div className="hero-mark" aria-hidden="true">
        m.
      </div>
      <Link className="hero-link" to="/accounts">
        View accounts <ArrowUpRight size={17} />
      </Link>
    </section>
  );
}
export function TransactionTable({
  transfers,
  accounts,
}: {
  transfers: Transfer[];
  accounts: Account[];
}) {
  if (!transfers.length) return <EmptyState />;
  const ids = new Set(accounts.map((a) => a.id));
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Date</th>
            <th>Status</th>
            <th className="text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {transfers.map((t) => {
            const outgoing = ids.has(t.source_account_id);
            const internal = outgoing && ids.has(t.destination_account_id);
            return (
              <tr key={t.id}>
                <td>
                  <Link className="transaction-cell" to={`/transfers/${t.id}`}>
                    <span className={`transaction-icon ${outgoing ? '' : 'incoming'}`}>
                      {outgoing ? <ArrowUpRight size={19} /> : <ArrowDownLeft size={19} />}
                    </span>
                    <span>
                      <strong>
                        {t.memo ||
                          (internal
                            ? 'Between your accounts'
                            : outgoing
                              ? 'Transfer sent'
                              : 'Transfer received')}
                      </strong>
                      <small title={t.reference}>
                        {outgoing ? 'To' : 'From'}{' '}
                        {shortId(outgoing ? t.destination_account_id : t.source_account_id)} ·{' '}
                        {t.reference.slice(-8)}
                      </small>
                    </span>
                  </Link>
                </td>
                <td className="muted whitespace-nowrap">{formatDate(t.created_at)}</td>
                <td>
                  <StatusBadge />
                </td>
                <td className="amount text-right whitespace-nowrap">
                  {outgoing ? '−' : '+'}
                  {formatVND(t.amount_vnd)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
