"""Preserve V1 seed funding as an immutable reporting baseline."""

from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    op.execute("""
    ALTER TABLE accounts ADD COLUMN opening_balance_vnd BIGINT;
    UPDATE accounts a SET opening_balance_vnd = a.balance_vnd - COALESCE((
      SELECT sum(CASE WHEN e.direction='CREDIT' THEN e.amount_vnd ELSE -e.amount_vnd END)
      FROM ledger_entries e WHERE e.account_id=a.id
    ),0);
    ALTER TABLE accounts ALTER COLUMN opening_balance_vnd SET NOT NULL;
    ALTER TABLE accounts ALTER COLUMN opening_balance_vnd SET DEFAULT 0;
    ALTER TABLE accounts ADD CONSTRAINT opening_balance_safe
      CHECK (opening_balance_vnd BETWEEN 0 AND 9007199254740991);
    CREATE FUNCTION protect_account_baseline() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.opening_balance_vnd IS DISTINCT FROM OLD.opening_balance_vnd
      THEN RAISE EXCEPTION 'Opening baseline is immutable'; END IF;
      IF OLD.status='CLOSED' AND NEW.status <> 'CLOSED'
      THEN RAISE EXCEPTION 'Closed account is terminal'; END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER immutable_account_baseline BEFORE UPDATE ON accounts
      FOR EACH ROW EXECUTE FUNCTION protect_account_baseline();
    CREATE INDEX ix_ledger_account_date ON ledger_entries(account_id, created_at, id);
    """)


def downgrade():
    raise RuntimeError("Reporting baselines are durable; use a reviewed forward fix.")
