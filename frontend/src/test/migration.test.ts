import { expect, it } from 'vitest';
import { validate } from '../../../migration/typescript/validation';
import cases from '../../../migration/shared-test-cases/validation_cases.json';
for (const c of cases)
  it(`shared validation: ${c.name}`, () => expect(validate(c.input)).toEqual(c.expected));
