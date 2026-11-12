import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './lib/api';
import { formatDate } from './lib/format';
import { PageHeading } from './pages';
import { ErrorAlert, LoadingSkeleton, EmptyState } from './components/ui';
import { Select } from './components/Select';

export function OperationsPage() {
  const [reason, setReason] = useState('CUSTOMER_REQUEST');
  const [frozen, setFrozen] = useState('freeze');
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (id: string) => api.freezeAccount(id, frozen === 'freeze', reason),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['audit'] }),
  });
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONS · SIMULATION"
        title="Account controls."
        description="Freeze outgoing transfers with an audited reason. Ledger entries and balances cannot be edited here."
      />
      <section className="panel settings-panel">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate(String(new FormData(event.currentTarget).get('account')));
          }}
        >
          <div className="field">
            <label htmlFor="controlled-account">Fictional account ID</label>
            <input id="controlled-account" name="account" required pattern="[0-9a-fA-F-]{36}" />
          </div>
          <div className="field">
            <label htmlFor="control-action">Action</label>
            <Select
              id="control-action"
              value={frozen}
              onChange={setFrozen}
              options={[
                { value: 'freeze', label: 'Freeze outgoing transfers' },
                { value: 'unfreeze', label: 'Unfreeze account' },
              ]}
            />
          </div>
          <div className="field">
            <label htmlFor="control-reason">Reason</label>
            <Select
              id="control-reason"
              value={reason}
              onChange={setReason}
              options={[
                { value: 'CUSTOMER_REQUEST', label: 'Customer request' },
                { value: 'RISK_REVIEW', label: 'Risk review' },
                { value: 'TEST_INCIDENT', label: 'Controlled test incident' },
              ]}
            />
          </div>
          <p className="muted">
            Incoming transfers to frozen accounts remain allowed. Closed accounts cannot be
            reopened.
          </p>
          {mutation.error && <ErrorAlert error={mutation.error} />}
          {mutation.data && (
            <p role="status" className="success-notice">
              {mutation.data.account_number}: {mutation.data.status}. Audit event recorded.
            </p>
          )}
          <button className="button primary" disabled={mutation.isPending}>
            {mutation.isPending ? 'Applying…' : 'Confirm account action'}
          </button>
        </form>
      </section>
    </>
  );
}

export function AuditPage() {
  const query = useQuery({ queryKey: ['audit'], queryFn: api.audit });
  return (
    <>
      <PageHeading
        eyebrow="READ-ONLY · AUDIT TRAIL"
        title="Actions, accounted for."
        description="Latest 50 durable events. UTC timestamps are displayed in your browser timezone; request IDs link actions to API logs."
        action={
          <button
            className="button secondary"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            Refresh events
          </button>
        }
      />
      <section className="panel transactions-panel">
        {query.isPending ? (
          <LoadingSkeleton />
        ) : query.error ? (
          <ErrorAlert error={query.error} retry={() => void query.refetch()} />
        ) : !query.data.length ? (
          <EmptyState title="No audit events yet">
            Account actions and committed transfers appear here.
          </EmptyState>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Action / date</th>
                  <th>Target</th>
                  <th>Outcome</th>
                  <th>Correlation</th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <strong>{event.action}</strong>
                      <p className="muted">{formatDate(event.created_at)}</p>
                    </td>
                    <td>
                      {event.target_type}
                      <code className="break-id">{event.target_id}</code>
                    </td>
                    <td>{event.outcome}</td>
                    <td>
                      <code className="break-id">{event.request_id}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
