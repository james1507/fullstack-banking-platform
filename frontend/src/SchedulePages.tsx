import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from './auth';
import {
  api,
  scheduleApi,
  BOB_ACCOUNT,
  APIError,
  type Schedule,
  type ScheduleInput,
} from './lib/api';
import { formatDate, formatVND } from './lib/format';
import { PageHeading } from './pages';
import { Select } from './components/Select';
import { EmptyState, ErrorAlert, LoadingSkeleton } from './components/ui';

export function SchedulesPage() {
  const query = useQuery({ queryKey: ['schedules'], queryFn: scheduleApi.list });
  return (
    <>
      <PageHeading
        eyebrow="PLANS WITH A CLEAR NEXT STEP"
        title="Scheduled transfers."
        description="One-time, weekly or monthly internal transfers. Funds move only when a due run succeeds. Latest 200 schedules."
        action={
          <Link className="button primary" to="/scheduled-transfers/new">
            Create schedule
          </Link>
        }
      />
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.error ? (
        <ErrorAlert error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.length ? (
        <EmptyState title="No scheduled transfers">
          Plan a future transfer without reserving or moving any funds today.
        </EmptyState>
      ) : (
        <div className="recipient-grid">
          {query.data.map((row) => (
            <article className="panel settings-panel" key={row.id}>
              <span className="eyebrow">
                {row.status} · {row.recurrence}
              </span>
              <h2>{formatVND(row.amount_vnd)}</h2>
              <p>{row.memo || 'Internal transfer plan'}</p>
              <p className="muted">
                {row.next_run_at ? `Next: ${formatDate(row.next_run_at)}` : 'No future run'}
                <br />
                Schedule timezone: {row.timezone}
              </p>
              <p>
                {row.runs_completed} / {row.max_runs} runs completed
              </p>
              <Link className="button secondary" to={`/scheduled-transfers/${row.id}`}>
                View schedule
              </Link>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

function ScheduleForm({
  initial,
  onSaved,
}: {
  initial?: Schedule;
  onSaved: (row: Schedule) => void;
}) {
  const { user } = useAuth();
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  const [source, setSource] = useState(initial?.source_account_id || '');
  const [recurrence, setRecurrence] = useState<ScheduleInput['recurrence']>(
    initial?.recurrence || 'ONCE',
  );
  const [draft, setDraft] = useState<ScheduleInput | null>(null);
  const [intentKey, setIntentKey] = useState(() => crypto.randomUUID());
  const [validation, setValidation] = useState<Error | null>(null);
  const mutation = useMutation({
    mutationFn: (payload: ScheduleInput) =>
      initial
        ? scheduleApi.edit(initial.id, payload, initial.version)
        : scheduleApi.create(payload, intentKey),
    onSuccess: onSaved,
  });
  if (accounts.isPending) return <LoadingSkeleton />;
  if (accounts.error) return <ErrorAlert error={accounts.error} />;
  const eligible = accounts.data.filter((row) => row.status === 'ACTIVE');
  const selected = source || eligible[0]?.id || '';
  return (
    <section className="panel settings-panel">
      <form
        hidden={draft !== null}
        onSubmit={(event) => {
          event.preventDefault();
          setValidation(null);
          const data = new FormData(event.currentTarget);
          const raw = String(data.get('amount')).trim();
          const amount = Number(raw);
          if (!/^\d+$/.test(raw) || !Number.isSafeInteger(amount) || amount <= 0 || !selected) {
            setValidation(
              new Error('Choose an active source and enter a positive whole VND amount.'),
            );
            return;
          }
          setIntentKey(crypto.randomUUID());
          setDraft({
            source_account_id: selected,
            destination_account_id: String(data.get('destination')).trim(),
            amount_vnd: amount,
            memo: String(data.get('memo')).trim() || null,
            timezone: String(data.get('timezone')).trim(),
            starts_local: String(data.get('starts')),
            recurrence,
            max_runs: recurrence === 'ONCE' ? 1 : Number(data.get('runs')),
          });
        }}
      >
        <div className="field">
          <label htmlFor="schedule-source">Schedule source account</label>
          <Select
            id="schedule-source"
            value={selected}
            onChange={setSource}
            options={eligible.map((row) => ({
              value: row.id,
              label: row.name,
              description: `${row.account_number} · ${formatVND(row.balance_vnd)} available now`,
            }))}
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-destination">Destination account ID</label>
          <input
            id="schedule-destination"
            name="destination"
            required
            pattern="[0-9a-fA-F-]{36}"
            defaultValue={initial?.destination_account_id || BOB_ACCOUNT}
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-amount">Scheduled amount (VND)</label>
          <input
            id="schedule-amount"
            name="amount"
            inputMode="numeric"
            required
            defaultValue={initial?.amount_vnd || ''}
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-memo">Schedule memo</label>
          <input
            id="schedule-memo"
            name="memo"
            maxLength={200}
            defaultValue={initial?.memo || ''}
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-frequency">Frequency</label>
          <Select
            id="schedule-frequency"
            value={recurrence}
            onChange={(value) => setRecurrence(value as typeof recurrence)}
            options={[
              { value: 'ONCE', label: 'One time', description: 'One future attempt.' },
              {
                value: 'WEEKLY',
                label: 'Every week',
                description: 'Same local weekday and clock time.',
              },
              {
                value: 'MONTHLY',
                label: 'Every month',
                description: 'Same local day; shorter months use their final day.',
              },
            ]}
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-starts">First run (local time)</label>
          <input
            id="schedule-starts"
            name="starts"
            type="datetime-local"
            step="1"
            required
            defaultValue={initial?.starts_local.slice(0, 16) || ''}
            aria-describedby="schedule-time-help"
          />
        </div>
        <div className="field">
          <label htmlFor="schedule-zone">IANA timezone</label>
          <input
            id="schedule-zone"
            name="timezone"
            required
            maxLength={64}
            defaultValue={initial?.timezone || user?.timezone || 'Asia/Ho_Chi_Minh'}
          />
        </div>
        <p id="schedule-time-help" className="muted">
          First run must be within 366 days. DST gaps are rejected when creating, skipped on
          recurrence; repeated clocks use the first occurrence. Missed runs after downtime are
          coalesced into one due attempt.
        </p>
        {recurrence !== 'ONCE' && (
          <div className="field">
            <label htmlFor="schedule-runs">Maximum total runs</label>
            <input
              id="schedule-runs"
              name="runs"
              type="number"
              required
              min={Math.max(1, (initial?.runs_completed || 0) + 1)}
              max={120}
              defaultValue={initial?.max_runs || 12}
            />
          </div>
        )}
        {validation && <ErrorAlert error={validation} />}
        <button className="button primary" disabled={!selected}>
          Review schedule
        </button>
      </form>
      {draft && (
        <section aria-label="Review schedule">
          <span className="eyebrow">
            {draft.recurrence} · UP TO {draft.max_runs} RUNS
          </span>
          <h2>{formatVND(draft.amount_vnd)}</h2>
          <p>
            First run: {draft.starts_local.replace('T', ' ')} ({draft.timezone})
          </p>
          <p className="break-id">Destination: {draft.destination_account_id}</p>
          <p>{draft.memo || 'No memo'}</p>
          <p className="muted">
            No funds move or are reserved now. Each run rechecks ownership, account status,
            available funds and current limits. Business rejections are final for that occurrence.
          </p>
          {mutation.error && <ErrorAlert error={mutation.error} />}
          <div className="action-row">
            <button
              className="button secondary"
              disabled={
                mutation.isPending ||
                (mutation.error instanceof APIError && mutation.error.uncertain)
              }
              onClick={() => {
                setDraft(null);
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
              {mutation.isPending
                ? 'Saving…'
                : mutation.error instanceof APIError && mutation.error.uncertain
                  ? 'Retry original schedule'
                  : 'Confirm schedule'}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}

export function NewSchedulePage() {
  const navigate = useNavigate();
  const cache = useQueryClient();
  return (
    <>
      <PageHeading
        eyebrow="LET YOUR PLANS KEEP THEIR TIME"
        title="Create a schedule."
        description="Plan fictional internal transfers. No balance guarantee or reservation."
      />
      <ScheduleForm
        onSaved={(row) => {
          void cache.invalidateQueries({ queryKey: ['schedules'] });
          navigate(`/scheduled-transfers/${row.id}`);
        }}
      />
    </>
  );
}

export function ScheduleDetailPage() {
  const { id = '' } = useParams();
  const [editing, setEditing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ['schedule', id],
    queryFn: () => scheduleApi.detail(id),
    refetchInterval: 5000,
  });
  async function refresh() {
    setConfirmed(false);
    await Promise.all(
      ['schedule', 'schedules', 'accounts', 'summary', 'history'].map((key) =>
        cache.invalidateQueries({ queryKey: [key] }),
      ),
    );
  }
  const action = useMutation({
    mutationFn: (kind: 'pause' | 'resume' | 'cancel') =>
      scheduleApi.action(id, kind, query.data!.schedule.version),
    onSuccess: refresh,
  });
  if (query.isPending) return <LoadingSkeleton />;
  if (query.error) return <ErrorAlert error={query.error} retry={() => void query.refetch()} />;
  const row = query.data.schedule;
  const terminal = ['CANCELLED', 'COMPLETED'].includes(row.status);
  return (
    <>
      <PageHeading
        eyebrow={`${row.status} · ${row.recurrence}`}
        title="Schedule details."
        description="Latest 50 occurrences. Times below display in your browser timezone; plan follows its named IANA timezone."
        action={
          <Link className="button secondary" to="/scheduled-transfers">
            All schedules
          </Link>
        }
      />
      <section className="panel settings-panel">
        <h2>{formatVND(row.amount_vnd)}</h2>
        <p>{row.memo || 'Internal transfer plan'}</p>
        <p>
          {row.next_run_at ? `Next: ${formatDate(row.next_run_at)}` : 'No future run'} ·{' '}
          {row.timezone}
        </p>
        <p>
          {row.runs_completed} / {row.max_runs} completed runs
        </p>
        <code className="break-id">{row.id}</code>
        {action.error && <ErrorAlert error={action.error} />}
        {!terminal && (
          <>
            <div className="action-row">
              <button
                className="button secondary"
                disabled={action.isPending}
                onClick={() => action.mutate(row.status === 'ACTIVE' ? 'pause' : 'resume')}
              >
                {row.status === 'ACTIVE' ? 'Pause schedule' : 'Resume schedule'}
              </button>
              <button className="button secondary" onClick={() => setEditing((value) => !value)}>
                {editing ? 'Close editor' : 'Edit future runs'}
              </button>
            </div>
            <label className="check-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />{' '}
              I confirm cancellation of future runs.
            </label>
            <button
              className="button secondary"
              disabled={!confirmed || action.isPending}
              onClick={() => action.mutate('cancel')}
            >
              Cancel schedule
            </button>
          </>
        )}
      </section>
      {editing && !terminal && (
        <ScheduleForm
          key={row.version}
          initial={row}
          onSaved={() => {
            setEditing(false);
            void refresh();
          }}
        />
      )}
      <section className="panel settings-panel">
        <h2>Execution history</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Due time</th>
                <th>Outcome</th>
                <th>Attempts</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {query.data.occurrences.map((item) => (
                <tr key={item.id}>
                  <td>{formatDate(item.due_at)}</td>
                  <td>{item.state}</td>
                  <td>{item.attempt_count}</td>
                  <td>
                    {item.transfer_id ? (
                      <Link className="text-link" to={`/transfers/${item.transfer_id}`}>
                        View receipt
                      </Link>
                    ) : (
                      item.last_error_code || 'Awaiting execution'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
