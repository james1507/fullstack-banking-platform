import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { validate } from './validation.ts';
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a],[b]) => a.localeCompare(b)).map(([key, v]) => [key, canonical(v)]));
  return value;
}
const cases = JSON.parse(readFileSync(new URL('../shared-test-cases/validation_cases.json', import.meta.url), 'utf8'));
for (const c of cases) { const result = validate(c.input); assert.deepEqual(result, c.expected, c.name); console.log(JSON.stringify(canonical({ name: c.name, result }))); }
