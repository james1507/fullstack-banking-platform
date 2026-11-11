# Python → TypeScript validation parity

The same 36 JSON fixtures drive both pure implementations and both test suites. `make parity` executes each standalone runner and compares canonical UTF-8 JSONL output byte for byte with `diff`.

| Concern | Chosen contract |
|---|---|
| Payload | object only, no unknown fields |
| Required fields | source, destination, amount; fixed validation order |
| IDs | canonical hyphenated UUID syntax; lowercase output |
| Amount | finite numeric mathematical integer in `[1, 2^53-1]`; no strings or booleans |
| Memo | optional/null; at most 200 Unicode code points before trimming |
| Whitespace | trim ASCII space, tab, LF, CR, form feed, vertical tab only |
| Empty memo | normalize to null |
| Error | `{ok:false,code,field}`; first deterministic validation failure |
| Success | `{ok:true,value:{source_account_id,destination_account_id,amount_vnd,memo}}` |
| Serialization | recursively sorted keys, compact JSON, Unicode emitted directly |

Python excludes `bool` explicitly because it subclasses `int`. TypeScript checks finite/integer before safe upper bound, preventing rounded unsafe values from being accepted. Python integers remain exact; JavaScript numbers do not, hence the common safe bound. Memo length uses Python code points and TypeScript `Array.from`, rather than UTF-16 `.length`. ASCII trimming avoids the different Unicode whitespace definitions in Python `strip()` and JavaScript `trim()`.

The migration module accepts normalized numeric inputs (including a mathematical integer written as `1e6` in JSON). The HTTP boundary is intentionally stricter: Pydantic rejects floating-point Python values and strings for the integer amount. This pure migration exercise is independent of DB authorization/balance checks. It is not a second HTTP validation authority.

Fixtures cover missing fields, positive and invalid amounts, integer limits, self-transfer, malformed IDs, memo bounds, emoji, whitespace, optional fields and wrong payload types. Runners assert the committed expected result before emitting output; parity alone cannot hide a shared wrong result. Fixture expectations are reviewable in `validation_cases.json`.
