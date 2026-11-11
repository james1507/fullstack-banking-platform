"""Initial schema, constraints and immutable balanced ledger.

Revision ID: 001
"""

from alembic import op

revision = "001"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE users (
        id UUID PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL, display_name VARCHAR(100) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (email = lower(email))
    );
    CREATE TABLE accounts (
        id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
        account_number VARCHAR(30) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL,
        currency VARCHAR(3) NOT NULL DEFAULT 'VND' CHECK (currency = 'VND'),
        balance_vnd BIGINT NOT NULL CHECK (balance_vnd BETWEEN 0 AND 9007199254740991),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_accounts_user ON accounts(user_id);
    CREATE TABLE transfers (
        id UUID PRIMARY KEY, reference VARCHAR(50) NOT NULL UNIQUE,
        initiated_by_user_id UUID NOT NULL REFERENCES users(id),
        source_account_id UUID NOT NULL REFERENCES accounts(id),
        destination_account_id UUID NOT NULL REFERENCES accounts(id),
        amount_vnd BIGINT NOT NULL CHECK (amount_vnd BETWEEN 1 AND 9007199254740991),
        memo VARCHAR(200), status VARCHAR(20) NOT NULL CHECK (status = 'SUCCEEDED'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (source_account_id <> destination_account_id)
    );
    CREATE INDEX ix_transfers_source_date ON transfers(source_account_id, created_at DESC, id DESC);
    CREATE INDEX ix_transfers_destination_date ON transfers(destination_account_id, created_at DESC, id DESC);
    CREATE TABLE ledger_entries (
        id UUID PRIMARY KEY, transfer_id UUID NOT NULL REFERENCES transfers(id),
        account_id UUID NOT NULL REFERENCES accounts(id),
        direction VARCHAR(6) NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
        amount_vnd BIGINT NOT NULL CHECK (amount_vnd > 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (transfer_id, account_id, direction), UNIQUE (transfer_id, direction)
    );
    CREATE INDEX ix_ledger_transfer ON ledger_entries(transfer_id);
    CREATE TABLE idempotency_records (
        id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
        operation VARCHAR(100) NOT NULL, key VARCHAR(100) NOT NULL, request_hash VARCHAR(64) NOT NULL,
        state VARCHAR(20) NOT NULL CHECK (state IN ('PROCESSING', 'COMPLETED')),
        response_status INTEGER, response_body JSONB, transfer_id UUID REFERENCES transfers(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, operation, key),
        CHECK (state <> 'COMPLETED' OR (response_status IS NOT NULL AND response_body IS NOT NULL))
    );
    CREATE TABLE refresh_sessions (
        id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id), token_hash VARCHAR(64) NOT NULL UNIQUE,
        family_id UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), rotated_at TIMESTAMPTZ
    );
    CREATE INDEX ix_refresh_user ON refresh_sessions(user_id);
    CREATE INDEX ix_refresh_family ON refresh_sessions(family_id);
    CREATE FUNCTION reject_ledger_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Committed ledger and transfers are immutable'; END; $$;
    CREATE TRIGGER immutable_ledger BEFORE UPDATE OR DELETE ON ledger_entries
      FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
    CREATE TRIGGER immutable_transfers BEFORE UPDATE OR DELETE ON transfers
      FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
    CREATE FUNCTION check_balanced_transfer() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (SELECT count(*) FROM ledger_entries WHERE transfer_id = NEW.id) <> 2
      OR NOT EXISTS (SELECT 1 FROM ledger_entries WHERE transfer_id = NEW.id
        AND direction = 'DEBIT' AND account_id = NEW.source_account_id AND amount_vnd = NEW.amount_vnd)
      OR NOT EXISTS (SELECT 1 FROM ledger_entries WHERE transfer_id = NEW.id
        AND direction = 'CREDIT' AND account_id = NEW.destination_account_id AND amount_vnd = NEW.amount_vnd)
      THEN RAISE EXCEPTION 'Transfer requires two matching ledger entries'; END IF;
      RETURN NEW;
    END; $$;
    CREATE CONSTRAINT TRIGGER balanced_transfer AFTER INSERT ON transfers
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_balanced_transfer();
    CREATE FUNCTION validate_ledger_insert() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM transfers t WHERE t.id = NEW.transfer_id
        AND t.amount_vnd = NEW.amount_vnd
        AND ((NEW.direction = 'DEBIT' AND t.source_account_id = NEW.account_id)
          OR (NEW.direction = 'CREDIT' AND t.destination_account_id = NEW.account_id)))
      THEN RAISE EXCEPTION 'Ledger entry does not match transfer'; END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER ledger_matches_transfer BEFORE INSERT ON ledger_entries
      FOR EACH ROW EXECUTE FUNCTION validate_ledger_insert();
    """)


def downgrade():
    op.execute("""
    DROP TABLE refresh_sessions, idempotency_records, ledger_entries, transfers, accounts, users CASCADE;
    DROP FUNCTION reject_ledger_mutation(), check_balanced_transfer(), validate_ledger_insert();
    """)
