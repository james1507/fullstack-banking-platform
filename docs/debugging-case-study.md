# Debugging a duplicate transfer across layers

## Symptom

A user sees a timeout and clicks Send again. Their balance drops twice. The UI had disabled the submit button, but a second HTTP request still reached another worker.

## Root cause

A frontend flag protects one mounted component, not multiple requests, retries, tabs or server processes. A backend read-then-write balance check without locks also permits concurrent requests to spend the same initial balance.

## Reproduction

The unsafe interleaving is documented in `challenges/duplicate-transactions/README.md`. Run the real PostgreSQL regression cases:

```bash
make test-backend
# Tests: test_twenty_four_parallel_same_key,
# test_parallel_distinct_keys_cannot_overdraw, test_opposite_direction_no_deadlock
```

The tests synchronize independent request threads with a barrier. They use separate DB transactions; no lock mocking or sleep-based coordination.

## Fix

The browser creates one idempotency key at review and freezes the payload while the outcome is unknown. An explicit retry sends both unchanged. The backend atomically claims a uniquely scoped key, locks accounts in global order, writes both balances and ledger entries, and persists the exact response before committing.

The 24-way same-key case requires one transfer and identical responses. The distinct-key case spends at most the available funds. Opposite-direction transfers share the same lock order. An injected ledger-write failure proves all balances, transfer, ledger and claim roll back.

## A real integration issue found during implementation

`EmailStr` rejected the required `example.test` demo addresses because the validator normally rejects special-use domains. The fix uses `email-validator` with `test_environment=True` and delivery checks disabled at the synthetic login boundary. The integration login test now asserts successful normalized `.test` sign-in. No real-domain demo credentials were substituted to hide the mismatch.

## Contract debugging

A UI expecting `balance` instead of `balance_vnd` may show an empty balance or `NaN`. Runtime Zod contracts reject the response, API errors retain stable codes, and component tests assert the displayed behavior. See the isolated contract challenge for the symptom-to-fix walkthrough.
