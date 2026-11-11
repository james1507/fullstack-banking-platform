import uuid

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Account, User
from app.security import password_hasher

ALICE = uuid.UUID("00000000-0000-4000-8000-000000000001")
BOB = uuid.UUID("00000000-0000-4000-8000-000000000002")


def seed():
    with SessionLocal.begin() as db:
        for index, name, balance in [(1, "Alice", 5_000_000), (2, "Bob", 3_000_000)]:
            user_id = uuid.UUID(f"10000000-0000-4000-8000-{index:012d}")
            db.execute(
                insert(User)
                .values(
                    id=user_id,
                    email=f"{name.lower()}@example.test",
                    display_name=name,
                    password_hash=password_hasher.hash("DemoPass123!"),
                    is_active=True,
                )
                .on_conflict_do_nothing(index_elements=["email"])
            )
            db.execute(
                insert(Account)
                .values(
                    id=ALICE if index == 1 else BOB,
                    user_id=user_id,
                    account_number=f"DEMO-{index}00001",
                    name="Everyday account",
                    currency="VND",
                    balance_vnd=balance,
                )
                .on_conflict_do_nothing(index_elements=["account_number"])
            )


if __name__ == "__main__":
    seed()
    print("Demo users/accounts ready. Existing balances preserved.")
