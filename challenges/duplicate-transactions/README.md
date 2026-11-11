# Challenge A: duplicate processing and overspending

Historical unsafe sketch, documentation only (never imported by the app):

```python
# Request A reads 5,000,000. Request B reads 5,000,000.
if account.balance_vnd >= amount:
    account.balance_vnd -= amount
    # A and B can each believe their independent 4,000,000 spend is valid.
```

An in-process mutex does not coordinate separate workers. A unique key without a shared transaction can also leave a permanently PROCESSING claim after a crash.

Shipping fix: `backend/app/transfers.py`. Unique `(user, operation, key)` insert serializes duplicate claims; a new READ COMMITTED statement reads the committed result. Consistently sorted account row locks serialize different-key spending. Claim, balances, transfer, ledger and saved response commit together. Business errors complete the claim without writing a transfer.

Run `make test-backend`. Inspect `test_twenty_four_parallel_same_key`, `test_parallel_distinct_keys_cannot_overdraw`, `test_opposite_direction_no_deadlock`, `test_injected_failure_rolls_back_everything`. Success means one same-key effect, no negative balances, invariant total supply, exactly two matching entries and safe rollback/retry.
