"""Owner-scoped saved recipients; no changes to committed transfer facts."""

from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    op.execute("""
    CREATE TABLE beneficiaries (
      id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
      destination_account_id UUID NOT NULL REFERENCES accounts(id),
      nickname VARCHAR(100) NOT NULL CHECK (length(trim(nickname)) > 0),
      archived_at TIMESTAMPTZ, last_used_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_active_beneficiary ON beneficiaries(user_id, destination_account_id)
      WHERE archived_at IS NULL;
    CREATE INDEX ix_beneficiaries_owner_name ON beneficiaries(user_id, lower(nickname), id);
    """)


def downgrade():
    raise RuntimeError("Beneficiary history must be preserved; use a forward fix.")
