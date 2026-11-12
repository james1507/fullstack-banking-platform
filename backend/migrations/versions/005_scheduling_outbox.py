"""Durable scheduled occurrences and transactional in-app delivery."""

from alembic import op

revision = "005"
down_revision = "004"


def upgrade():
    op.execute("""
    CREATE TABLE transfer_schedules (
      id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
      source_account_id UUID NOT NULL REFERENCES accounts(id),
      destination_account_id UUID NOT NULL REFERENCES accounts(id),
      amount_vnd BIGINT NOT NULL CHECK (amount_vnd BETWEEN 1 AND 9007199254740991),
      memo VARCHAR(200), timezone VARCHAR(64) NOT NULL, starts_local TIMESTAMP NOT NULL,
      recurrence VARCHAR(10) NOT NULL CHECK (recurrence IN ('ONCE','WEEKLY','MONTHLY')),
      max_runs INTEGER NOT NULL CHECK (max_runs BETWEEN 1 AND 120),
      runs_completed INTEGER NOT NULL DEFAULT 0 CHECK (runs_completed BETWEEN 0 AND 120),
      version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
      status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','PAUSED','CANCELLED','COMPLETED')),
      next_run_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CHECK (source_account_id <> destination_account_id)
    );
    CREATE INDEX ix_transfer_schedules_user ON transfer_schedules(user_id, created_at DESC, id);
    CREATE TABLE schedule_occurrences (
      id UUID PRIMARY KEY, schedule_id UUID NOT NULL REFERENCES transfer_schedules(id),
      due_at TIMESTAMPTZ NOT NULL, available_at TIMESTAMPTZ NOT NULL,
      state VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED' CHECK (state IN
        ('SCHEDULED','CLAIMED','SUCCEEDED','FAILED_RETRYABLE','FAILED_PERMANENT','CANCELLED')),
      attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 5),
      lease_until TIMESTAMPTZ, lease_token UUID,
      transfer_id UUID REFERENCES transfers(id), last_error_code VARCHAR(50),
      request_id VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CHECK ((state = 'CLAIMED') = (lease_until IS NOT NULL AND lease_token IS NOT NULL)),
      CHECK ((state = 'SUCCEEDED') = (transfer_id IS NOT NULL))
    );
    CREATE INDEX ix_occurrences_due ON schedule_occurrences(state, available_at, lease_until);
    CREATE UNIQUE INDEX uq_occurrence_slot ON schedule_occurrences(schedule_id, due_at)
      WHERE state <> 'CANCELLED';
    CREATE TABLE outbox_events (
      id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
      kind VARCHAR(30) NOT NULL, entity_id UUID NOT NULL, request_id VARCHAR(100) NOT NULL,
      state VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (state IN ('PENDING','CLAIMED','DELIVERED','RETRYABLE','DEAD_LETTER')),
      attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 5),
      available_at TIMESTAMPTZ NOT NULL DEFAULT now(), lease_until TIMESTAMPTZ, lease_token UUID,
      last_error_code VARCHAR(50), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (user_id, kind, entity_id),
      CHECK ((state = 'CLAIMED') = (lease_until IS NOT NULL AND lease_token IS NOT NULL))
    );
    CREATE INDEX ix_outbox_due ON outbox_events(state, available_at, lease_until);
    CREATE TABLE notifications (
      id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
      event_id UUID NOT NULL UNIQUE REFERENCES outbox_events(id),
      kind VARCHAR(30) NOT NULL, entity_id UUID NOT NULL,
      title VARCHAR(100) NOT NULL, body VARCHAR(300) NOT NULL, read_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_notifications_owner ON notifications(user_id, created_at DESC, id DESC);
    """)


def downgrade():
    raise RuntimeError("Schedule and delivery history must be preserved; use a forward fix.")
