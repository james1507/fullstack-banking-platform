import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { inboxApi } from './lib/api';
import { formatDate } from './lib/format';
import { PageHeading } from './pages';
import { EmptyState, ErrorAlert, LoadingSkeleton } from './components/ui';

export function InboxPage() {
  const [cursor, setCursor] = useState('');
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ['inbox', cursor],
    queryFn: () => inboxApi.list(cursor),
    refetchInterval: 10000,
  });
  const mutation = useMutation({
    mutationFn: async (id: string) => {
      if (id === 'all') await inboxApi.readAll();
      else await inboxApi.read(id);
    },
    onSuccess: () => cache.invalidateQueries({ queryKey: ['inbox'] }),
  });
  return (
    <>
      <PageHeading
        eyebrow="COMMITTED EVENTS, DELIVERED DURABLY"
        title="Your inbox."
        description="Internal demo notifications from the PostgreSQL outbox. No emails or SMS are sent."
        action={
          <button
            className="button secondary"
            disabled={mutation.isPending || !query.data?.unread_count}
            onClick={() => mutation.mutate('all')}
          >
            Mark all read
          </button>
        }
      />
      {mutation.error && <ErrorAlert error={mutation.error} />}
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.error ? (
        <ErrorAlert error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <p role="status">{query.data.unread_count} unread</p>
          {!query.data.items.length ? (
            <EmptyState title="All quiet here">
              Committed transfer and schedule updates appear after worker delivery.
            </EmptyState>
          ) : (
            <div className="recipient-grid">
              {query.data.items.map((row) => (
                <article className="panel settings-panel" key={row.id}>
                  <span className="eyebrow">
                    {row.read_at ? 'READ' : 'UNREAD'} · {formatDate(row.created_at)}
                  </span>
                  <h2>{row.title}</h2>
                  <p>{row.body}</p>
                  <div className="action-row">
                    <Link
                      className="button secondary"
                      to={
                        row.kind === 'TRANSFER_POSTED'
                          ? `/transfers/${row.entity_id}`
                          : '/scheduled-transfers'
                      }
                    >
                      View details
                    </Link>
                    {!row.read_at && (
                      <button
                        className="button secondary"
                        disabled={mutation.isPending}
                        onClick={() => mutation.mutate(row.id)}
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
          <div className="action-row">
            <button className="button secondary" disabled={!cursor} onClick={() => setCursor('')}>
              Newest notifications
            </button>
            <button
              className="button secondary"
              disabled={!query.data.next_cursor}
              onClick={() => setCursor(query.data.next_cursor!)}
            >
              Older notifications
            </button>
          </div>
        </>
      )}
    </>
  );
}
