"""Add roles, account lifecycle, limits and immutable audit without touching V1 postings."""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.execute("""
    ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER'
      CHECK (role IN ('CUSTOMER', 'OPERATIONS', 'AUDITOR'));
    ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh';
    ALTER TABLE users ADD COLUMN locale VARCHAR(10) NOT NULL DEFAULT 'en';
    ALTER TABLE accounts ADD COLUMN account_type VARCHAR(10) NOT NULL DEFAULT 'CHECKING'
      CHECK (account_type IN ('CHECKING', 'SAVINGS'));
    ALTER TABLE accounts ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'
      CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED'));
    ALTER TABLE accounts ADD COLUMN closed_at TIMESTAMPTZ;
    ALTER TABLE accounts ADD COLUMN daily_outgoing_limit_vnd BIGINT
      CHECK (daily_outgoing_limit_vnd BETWEEN 1 AND 9007199254740991);
    ALTER TABLE accounts ADD CONSTRAINT closed_account_empty
      CHECK (status <> 'CLOSED' OR (balance_vnd = 0 AND closed_at IS NOT NULL));
    CREATE INDEX ix_accounts_owner_status ON accounts(user_id, status);
    CREATE TABLE audit_events (
      id UUID PRIMARY KEY, actor_user_id UUID REFERENCES users(id),
      action VARCHAR(50) NOT NULL, target_type VARCHAR(30) NOT NULL,
      target_id UUID NOT NULL, outcome VARCHAR(20) NOT NULL,
      request_id VARCHAR(100) NOT NULL, safe_metadata JSONB NOT NULL DEFAULT '{}',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_audit_time ON audit_events(created_at DESC, id DESC);
    CREATE INDEX ix_audit_target ON audit_events(target_type, target_id);
    CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_events
      FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
    """)


def downgrade():
    raise RuntimeError("V2 contains durable audit/lifecycle data; use a reviewed forward fix.")
