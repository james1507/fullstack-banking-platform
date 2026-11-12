import csv
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError

from app import reporting
from app.db import SessionLocal, engine
from app.models import Account, LedgerEntry, Transfer, User
from app.seed import ALICE, BOB
from tests.conftest import auth
from tests.test_platform import BODY, PATH, send


def historical_post(at, amount, source=ALICE, destination=BOB, memo="Historical fixture"):
    """Synthetic history fixture, subject to the actual paired-ledger DB constraints."""
    with SessionLocal.begin() as session:
        accounts = {
            row.id: row
            for row in session.scalars(
                select(Account)
                .where(Account.id.in_([source, destination]))
                .order_by(Account.id)
                .with_for_update()
            )
        }
        row = Transfer(
            id=uuid.uuid4(),
            reference="FIXTURE-" + uuid.uuid4().hex,
            initiated_by_user_id=accounts[source].user_id,
            source_account_id=source,
            destination_account_id=destination,
            amount_vnd=amount,
            memo=memo,
            created_at=at,
        )
        accounts[source].balance_vnd -= amount
        accounts[destination].balance_vnd += amount
        session.add(row)
        session.flush()
        session.add_all(
            [
                LedgerEntry(
                    transfer_id=row.id,
                    account_id=source,
                    direction="DEBIT",
                    amount_vnd=amount,
                    created_at=at,
                ),
                LedgerEntry(
                    transfer_id=row.id,
                    account_id=destination,
                    direction="CREDIT",
                    amount_vnd=amount,
                    created_at=at,
                ),
            ]
        )
        return row.id


def report_url(account=ALICE, ending=None):
    today = ending or datetime.now(UTC).date()
    return f"{PATH}/accounts/{account}/statement?date_from={today}&date_to={today}&timezone=UTC"


def test_statement_reconciles_and_csv_neutralizes_formula(client, headers):
    assert send(client, headers, body={**BODY, "memo": ' =HYPERLINK("bad")'}).status_code == 201
    response = client.get(report_url(), headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="moneta-' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    opening = int(next(row["balance_vnd"] for row in rows if row["record_type"] == "OPENING"))
    movement = next(row for row in rows if row["record_type"] == "TRANSFER")
    closing = int(next(row["balance_vnd"] for row in rows if row["record_type"] == "CLOSING"))
    assert opening == 5000000 and closing == 4850000
    assert opening + int(movement["credit_vnd"]) - int(movement["debit_vnd"]) == closing
    assert movement["description"].startswith("'=")
    assert "T" in movement["timestamp_utc"]
    assert client.get(report_url(BOB), headers=headers).status_code == 404
    bob = auth(client, "bob@example.test")
    assert client.get(report_url(), headers=bob).status_code == 404


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", "\t=1", "\r=1", "\n+1", "  =1"]
)
def test_csv_formula_cells(value):
    assert reporting.csv_cell(value).startswith("'")
    assert reporting.csv_cell("Tiền nhà, tháng 11") == "Tiền nhà, tháng 11"


def test_statement_before_account_exists_is_zero_and_period_limits(client, headers):
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    result = client.get(
        report_url(ending=yesterday).replace("/statement?", "/statement/summary?"), headers=headers
    )
    assert result.status_code == 200
    assert result.json()["opening_balance_vnd"] == result.json()["closing_balance_vnd"] == "0"
    assert result.json()["effective_from"] is None
    for query in (
        "date_from=2026-01-02&date_to=2026-01-01",
        "date_from=2024-01-01&date_to=2026-01-01",
        "date_from=2026-01-01&date_to=2026-01-01&timezone=Invalid/Zone",
        "date_from=9999-12-31&date_to=9999-12-31",
    ):
        assert (
            client.get(f"{PATH}/accounts/{ALICE}/statement?{query}", headers=headers).status_code
            == 422
        )


def test_calendar_and_dst_periods():
    start, end, _ = reporting.period(date(2024, 3, 10), date(2024, 3, 10), "America/New_York")
    assert end - start == timedelta(hours=23)
    start, end, _ = reporting.period(date(2024, 11, 3), date(2024, 11, 3), "America/New_York")
    assert end - start == timedelta(hours=25)
    start, end, _ = reporting.period(date(2024, 2, 29), date(2024, 2, 29), "UTC")
    assert end - start == timedelta(days=1)


def test_export_row_cap_and_immutable_opening_baseline(client, headers, monkeypatch):
    assert send(client, headers, "export-1").status_code == 201
    assert send(client, headers, "export-2").status_code == 201
    monkeypatch.setattr(reporting, "MAX_EXPORT_ROWS", 1)
    assert (
        client.get(report_url(), headers=headers).json()["error"]["code"] == "EXPORT_LIMIT_EXCEEDED"
    )
    with pytest.raises(DBAPIError), SessionLocal.begin() as session:
        session.execute(text("UPDATE accounts SET opening_balance_vnd=1"))


def test_cursor_ties_filters_and_cross_user_binding(client, headers):
    at = datetime.now(UTC).replace(microsecond=0)
    expected = {str(historical_post(at, amount)) for amount in (10, 20, 30)}
    first = client.get(PATH + "/transfers/search?page_size=1", headers=headers).json()
    seen = {first["items"][0]["id"]}
    cursor = first["next_cursor"]
    while cursor:
        response = client.get(
            PATH + "/transfers/search", headers=headers, params={"page_size": 1, "cursor": cursor}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        seen.update(row["id"] for row in data["items"])
        cursor = data["next_cursor"]
    assert seen == expected
    filtered = client.get(
        PATH + "/transfers/search?min_amount=20&max_amount=30", headers=headers
    ).json()
    assert {row["amount_vnd"] for row in filtered["items"]} == {20, 30}
    cursor = first["next_cursor"]
    for invalid in ("bad", cursor[:-1] + ("a" if cursor[-1] != "a" else "b")):
        assert (
            client.get(
                PATH + "/transfers/search", headers=headers, params={"cursor": invalid}
            ).status_code
            == 400
        )
    assert (
        client.get(
            PATH + "/transfers/search",
            headers=headers,
            params={"cursor": cursor, "reference": "different"},
        ).status_code
        == 400
    )
    bob = auth(client, "bob@example.test")
    assert (
        client.get(PATH + "/transfers/search", headers=bob, params={"cursor": cursor}).status_code
        == 400
    )
    assert (
        client.get(PATH + f"/transfers/search?account_id={BOB}", headers=headers).status_code == 404
    )
    assert (
        client.get(
            PATH + "/transfers/search?min_amount=20&max_amount=10", headers=headers
        ).status_code
        == 422
    )
    assert client.get(PATH + "/transfers?page=1", headers=headers).status_code == 200


def test_statement_uses_consistent_snapshot_during_concurrent_post(client, headers, db):
    actor = db.get(User, uuid.UUID("10000000-0000-4000-8000-000000000001"))
    today = datetime.now(UTC).date()
    observed = Event()
    posted = Event()
    connection_seen = []

    def pause_after_account(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"):
            connection_seen.append(connection)
        elif (
            connection_seen
            and connection is connection_seen[0]
            and statement.startswith("SELECT accounts.")
            and not observed.is_set()
        ):
            observed.set()
            assert posted.wait(timeout=15)

    def read_statement():
        with SessionLocal() as session:
            return reporting.statement(session, actor, ALICE, today, today, "UTC", "snapshot-test")[
                0
            ]

    event.listen(engine, "after_cursor_execute", pause_after_account)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(read_statement)
            try:
                assert observed.wait(timeout=15)
                assert send(client, headers).status_code == 201
            finally:
                posted.set()
            summary = future.result(timeout=15)
    finally:
        posted.set()
        event.remove(engine, "after_cursor_execute", pause_after_account)
    assert summary.closing_balance_vnd == "5000000"
    assert summary.row_count == 0
