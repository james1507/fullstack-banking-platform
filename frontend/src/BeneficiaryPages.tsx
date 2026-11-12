import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './lib/api';
import { formatDate } from './lib/format';
import { PageHeading } from './pages';
import { EmptyState, ErrorAlert, LoadingSkeleton } from './components/ui';

export function BeneficiariesPage() {
  const [search, setSearch] = useState('');
  const [archived, setArchived] = useState(false);
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ['beneficiaries', search, archived],
    queryFn: () => api.beneficiaries(search, archived),
  });
  const mutation = useMutation({
    mutationFn: (action: {
      id: string;
      kind: 'rename' | 'archive' | 'restore';
      nickname?: string;
    }) =>
      action.kind === 'rename'
        ? api.renameBeneficiary(action.id, action.nickname!)
        : action.kind === 'restore'
          ? api.restoreBeneficiary(action.id)
          : api.archiveBeneficiary(action.id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['beneficiaries'] }),
  });
  return (
    <>
      <PageHeading
        eyebrow="FAMILIAR NAMES. FEWER DETAILS TO TYPE."
        title="Saved recipients."
        description="Your private address book for fictional internal accounts. Saving a recipient never moves funds."
        action={
          <Link className="button primary" to="/beneficiaries/new">
            Add recipient
          </Link>
        }
      />
      <section className="panel settings-panel">
        <form
          className="recipient-search"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(String(new FormData(event.currentTarget).get('search')).trim());
          }}
        >
          <div className="field">
            <label htmlFor="recipient-search">Search nickname</label>
            <input id="recipient-search" name="search" maxLength={100} />
          </div>
          <button className="button secondary">Search recipients</button>
        </form>
        <label className="check-label">
          <input
            type="checkbox"
            checked={archived}
            onChange={(event) => setArchived(event.target.checked)}
          />{' '}
          Show archived recipients
        </label>
        <small className="muted">
          Up to 100 matching recipients, sorted by nickname. Narrow the search to find another
          entry.
        </small>
      </section>
      {mutation.error && <ErrorAlert error={mutation.error} />}
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.error ? (
        <ErrorAlert error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.length ? (
        <section className="panel">
          <EmptyState title="No saved recipients">
            Add a fictional account, or adjust your search.
          </EmptyState>
        </section>
      ) : (
        <div className="accounts-grid">
          {query.data.map((row) => (
            <article className="panel settings-panel" key={row.id}>
              <div>
                <span className="eyebrow">{row.archived_at ? 'ARCHIVED' : 'SAVED RECIPIENT'}</span>
                <h2>{row.nickname}</h2>
              </div>
              <code className="break-id">{row.destination_account_id}</code>
              <small className="muted">
                {row.last_used_at
                  ? `Last used ${formatDate(row.last_used_at)}`
                  : 'Not used for a transfer yet.'}
              </small>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  mutation.mutate({
                    id: row.id,
                    kind: 'rename',
                    nickname: String(new FormData(event.currentTarget).get('nickname')).trim(),
                  });
                }}
              >
                <div className="field">
                  <label htmlFor={`nickname-${row.id}`}>Nickname</label>
                  <input
                    id={`nickname-${row.id}`}
                    name="nickname"
                    defaultValue={row.nickname}
                    required
                    maxLength={100}
                  />
                </div>
                <button className="button secondary" disabled={mutation.isPending}>
                  Save nickname
                </button>
              </form>
              <div className="action-row">
                {!row.archived_at && (
                  <Link
                    className="button primary"
                    to={`/transfers/new?recipient=${row.destination_account_id}`}
                  >
                    Send to recipient
                  </Link>
                )}
                <button
                  className="text-button"
                  disabled={mutation.isPending}
                  onClick={() =>
                    mutation.mutate({ id: row.id, kind: row.archived_at ? 'restore' : 'archive' })
                  }
                >
                  {row.archived_at ? 'Restore recipient' : 'Archive recipient'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function NewBeneficiaryPage() {
  const [editing, setEditing] = useState(true);
  const [draft, setDraft] = useState<{ nickname: string; destination_account_id: string }>({
    nickname: '',
    destination_account_id: '00000000-0000-4000-8000-000000000002',
  });
  const cache = useQueryClient();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: api.addBeneficiary,
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['beneficiaries'] });
      navigate('/beneficiaries');
    },
  });
  return (
    <>
      <PageHeading
        eyebrow="A LITTLE LESS TO REMEMBER"
        title="Add a recipient."
        description="Use a fictional account ID. Server checks its availability without revealing the account holder’s personal details."
      />
      <section className="panel settings-panel">
        {!editing ? (
          <section aria-label="Review recipient">
            <h2>{draft.nickname}</h2>
            <code className="break-id">{draft.destination_account_id}</code>
            <p className="muted">
              Confirm this destination. Only your chosen nickname is saved; no transfer will be
              made.
            </p>
            {mutation.error && <ErrorAlert error={mutation.error} />}
            <div className="action-row">
              <button
                className="button secondary"
                disabled={mutation.isPending}
                onClick={() => {
                  setEditing(true);
                  mutation.reset();
                }}
              >
                Back to edit
              </button>
              <button
                className="button primary"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(draft)}
              >
                {mutation.isPending ? 'Checking & saving…' : 'Confirm & save recipient'}
              </button>
            </div>
          </section>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              setDraft({
                nickname: String(data.get('nickname')).trim(),
                destination_account_id: String(data.get('destination')).trim(),
              });
              setEditing(false);
            }}
          >
            <div className="field">
              <label htmlFor="new-nickname">Nickname</label>
              <input
                id="new-nickname"
                name="nickname"
                required
                maxLength={100}
                placeholder="Monthly savings recipient"
                defaultValue={draft.nickname}
              />
            </div>
            <div className="field">
              <label htmlFor="new-destination">Fictional destination account ID</label>
              <input
                id="new-destination"
                name="destination"
                required
                pattern="[0-9a-fA-F-]{36}"
                defaultValue={draft.destination_account_id}
              />
            </div>
            <div className="action-row">
              <Link className="button secondary" to="/beneficiaries">
                Cancel
              </Link>
              <button className="button primary">Review recipient</button>
            </div>
          </form>
        )}
      </section>
    </>
  );
}
