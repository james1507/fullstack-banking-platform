import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
const alice = '00000000-0000-4000-8000-000000000001';
const bob = '00000000-0000-4000-8000-000000000002';
const origin = process.env.BASE_URL || 'http://localhost:5173';

test('protected route requires sign-in', async ({ page }) => {
  await page.goto('/accounts');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
});

test('Alice sends money, sees receipt, balances, history and restores session', async ({
  page,
}) => {
  await page.goto('/login');
  if (process.env.CAPTURE_DEMO === '1')
    await page.screenshot({ path: '../docs/screenshots/login.png', fullPage: true });
  const signedIn = page
    .waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST',
    )
    .then((response) => response.json());
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Looking good, Alice.' })).toBeVisible();
  const token = (await signedIn).access_token;
  const accounts = await page.request.get('/api/v1/accounts', {
    headers: { Authorization: `Bearer ${token}` },
  });
  const balance = (await accounts.json())[0].balance_vnd;
  await page.getByRole('link', { name: 'Send money' }).first().click();
  await page.getByRole('button', { name: /Use Bob/ }).click();
  await page.getByLabel('Amount', { exact: true }).fill('0');
  await page.getByRole('button', { name: 'Review transfer' }).click();
  await expect(
    page.getByText('Enter a positive whole amount within the safe limit.'),
  ).toBeVisible();
  await page.getByLabel('Amount', { exact: true }).fill('150000');
  await page.getByLabel('Memo').fill('Portfolio walkthrough');
  await page.getByRole('button', { name: 'Review transfer' }).click();
  if (process.env.CAPTURE_DEMO === '1')
    await page.screenshot({ path: '../docs/screenshots/transfer.png', fullPage: true });
  await page.getByRole('button', { name: 'Confirm & send' }).click();
  await expect(page.getByRole('heading', { name: 'Transfer complete.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '150,000 ₫', exact: true })).toBeVisible();
  if (process.env.CAPTURE_DEMO === '1')
    await page.screenshot({ path: '../docs/screenshots/receipt.png', fullPage: true });
  await page.getByRole('link', { name: 'Back to overview' }).click();
  await expect(
    page
      .getByRole('heading', {
        name: `${new Intl.NumberFormat('en-US').format(balance - 150000)} ₫`,
        exact: true,
      })
      .first(),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Looking good, Alice.' })).toBeVisible();
  if (process.env.CAPTURE_DEMO === '1')
    await page.screenshot({ path: '../docs/screenshots/dashboard.png', fullPage: true });
  await page.getByRole('link', { name: 'Transactions', exact: true }).click();
  await expect(page.getByRole('link', { name: /Portfolio walkthrough/ }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test('API replays original key without duplicating transfer', async ({ request }) => {
  const login = await request.post('/api/v1/auth/login', {
    headers: { Origin: origin },
    data: { email: 'alice@example.test', password: 'DemoPass123!' },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).access_token;
  const headers = { Authorization: `Bearer ${token}`, 'Idempotency-Key': crypto.randomUUID() };
  const options = {
    headers,
    data: {
      source_account_id: alice,
      destination_account_id: bob,
      amount_vnd: 1,
      memo: 'E2E idempotency',
    },
  };
  const first = await request.post('/api/v1/transfers', options);
  const second = await request.post('/api/v1/transfers', options);
  expect(first.status()).toBe(201);
  expect(second.status()).toBe(201);
  expect(await second.json()).toEqual(await first.json());
  expect(second.headers()['x-idempotency-replayed']).toBe('true');
  const conflict = await request.post('/api/v1/transfers', {
    ...options,
    data: { ...options.data, amount_vnd: 2 },
  });
  expect(conflict.status()).toBe(409);
});

test('mobile workspace remains usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Looking good, Alice.' })).toBeVisible();
  if (process.env.CAPTURE_DEMO === '1')
    await page.screenshot({ path: '../docs/screenshots/mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByRole('link', { name: 'My accounts' }).click();
  await expect(page.getByRole('heading', { name: 'Your accounts.' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).last().click();
  await expect(page).toHaveURL(/\/login$/);
});

test('dropdowns support keyboard, dismissal, source details and mobile bounds', async ({
  page,
}) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await page.getByRole('link', { name: 'Transactions', exact: true }).click();
  const direction = page.getByRole('combobox', { name: 'Filter direction' });
  await direction.click();
  await expect(page.getByRole('option', { name: /All directions/ })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await direction.press('End');
  await direction.press('Enter');
  await expect(direction).toHaveText('Money in');
  await expect(direction).toBeFocused();
  await direction.click();
  await direction.press('Home');
  await direction.press('Escape');
  await expect(direction).toHaveText('Money in');
  await expect(page.getByRole('listbox')).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Filter account' }).click();
  await expect(page.getByRole('option', { name: /DEMO-100001/ })).toBeVisible();
  await page.getByRole('heading', { name: 'Your transactions.' }).click();
  await expect(page.getByRole('listbox')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 540 });
  await direction.click();
  const menu = (await page.getByRole('listbox').boundingBox())!;
  expect(menu.x).toBeGreaterThanOrEqual(0);
  expect(menu.y).toBeGreaterThanOrEqual(0);
  expect(menu.x + menu.width).toBeLessThanOrEqual(390);
  expect(menu.y + menu.height).toBeLessThanOrEqual(540);
  await direction.press('Escape');
  await page.getByRole('link', { name: 'Send money' }).first().click();
  const source = page.getByRole('combobox', { name: 'From account' });
  await source.click();
  await expect(page.getByRole('option', { name: /Everyday account · DEMO-100001/ })).toContainText(
    'available · VND account',
  );
  await source.press('Escape');
  await expect(page.getByRole('listbox')).toHaveCount(0);
});

test('customer opens, renames and closes a zero-balance savings account', async ({ page }) => {
  await page.goto('/login');
  const signedIn = page
    .waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST',
    )
    .then((response) => response.json());
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await page.getByRole('link', { name: 'My accounts', exact: true }).click();
  await page.getByRole('link', { name: 'Open demo account' }).click();
  await page.getByLabel('Account nickname').fill('Travel fund');
  await page.getByRole('button', { name: 'Open zero-balance account' }).click();
  await expect(page.getByRole('heading', { name: 'Travel fund', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '0 ₫', exact: true })).toBeVisible();
  await page.getByLabel('Account nickname').fill('Future plans');
  await page.getByLabel('Daily outgoing limit (VND)').fill('250000');
  await page.getByRole('button', { name: 'Save account settings' }).click();
  await expect(page.getByText('Account settings saved.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Future plans', exact: true })).toBeVisible();
  await page.getByLabel('I confirm this account should be closed.').check();
  await page.getByRole('button', { name: 'Close account', exact: true }).click();
  await expect(page.getByText('Account closed. History remains available.')).toBeVisible();
  await page.goto('/ops');
  await expect(page.getByRole('heading', { name: 'Access restricted.' })).toBeVisible();
  const token = (await signedIn).access_token;
  const denied = await page.request.post(`/api/v1/ops/accounts/${alice}/freeze`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { reason: 'RISK_REVIEW' },
  });
  expect(denied.status()).toBe(403);
});

test('operator freezes and unfreezes account with durable audit events', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.test');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Account controls.' })).toBeVisible();
  await page.getByLabel('Fictional account ID').fill(alice);
  await page.getByRole('button', { name: 'Confirm account action' }).click();
  await expect(page.getByRole('status')).toContainText('FROZEN');
  await page.getByRole('combobox', { name: 'Action' }).click();
  await page.getByRole('option', { name: 'Unfreeze account', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm account action' }).click();
  await expect(page.getByRole('status')).toContainText('ACTIVE');
  await page.getByRole('link', { name: 'Audit trail' }).click();
  await expect(
    page.getByRole('cell', { name: 'ACCOUNT_UNFROZEN', exact: false }).first(),
  ).toBeVisible();
});

test('saved recipient is verified, used in server review and safely archived', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await page.getByRole('link', { name: 'Recipients', exact: true }).click();
  await page.getByRole('link', { name: 'Add recipient' }).click();
  await page.getByLabel('Nickname', { exact: true }).fill('Bob · recurring plan');
  await page.getByRole('button', { name: 'Review recipient' }).click();
  await page.getByRole('button', { name: 'Confirm & save recipient' }).click();
  await expect(
    page.getByRole('heading', { name: 'Bob · recurring plan', exact: true }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Send to recipient' }).click();
  await expect(page.getByRole('combobox', { name: 'Saved recipient' })).toHaveText(
    'Bob · recurring plan',
  );
  await page.getByLabel('Amount', { exact: true }).fill('100');
  await page.getByLabel('Memo').fill('V2 beneficiary walkthrough');
  await page.getByRole('button', { name: 'Review transfer' }).click();
  await expect(page.getByRole('region', { name: 'Review transfer' })).toContainText('••••0001');
  await expect(page.getByText(/Estimated source balance/)).toBeVisible();
  await page.getByRole('button', { name: 'Confirm & send' }).click();
  await expect(page.getByRole('heading', { name: 'Transfer complete.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Print receipt' })).toBeVisible();
  if (process.env.CAPTURE_V2 === '1')
    await page.screenshot({ path: '../docs/screenshots/v2-receipt.png', fullPage: true });
  await page.getByRole('link', { name: 'Recipients', exact: true }).click();
  await expect(page.getByText(/^Last used /)).toBeVisible();
  if (process.env.CAPTURE_V2 === '1')
    await page.screenshot({ path: '../docs/screenshots/v2-beneficiaries.png', fullPage: true });
  await page.getByRole('button', { name: 'Archive recipient' }).click();
  await expect(page.getByRole('heading', { name: 'No saved recipients' })).toBeVisible();
  await page.getByLabel('Show archived recipients').check();
  await page.getByRole('button', { name: 'Restore recipient' }).click();
  await expect(page.getByRole('link', { name: 'Send to recipient' })).toBeVisible();
});

test('customer searches posted history and downloads a reconciled CSV statement', async ({
  page,
}) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await page.getByRole('link', { name: 'Transactions', exact: true }).click();
  await page.getByRole('link', { name: 'Advanced search', exact: true }).click();
  await page.getByLabel('Minimum VND').fill('150000');
  await page.getByLabel('Maximum VND').fill('150000');
  await page.getByRole('button', { name: 'Apply search filters' }).click();
  await expect(page.getByRole('link', { name: /Portfolio walkthrough/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next results' })).toBeDisabled();
  await page.getByRole('link', { name: 'Statements', exact: true }).click();
  await page.getByRole('combobox', { name: 'Statement account' }).click();
  await page.getByRole('option', { name: /Everyday account/ }).click();
  await page.getByRole('button', { name: 'Build statement' }).click();
  await expect(page.getByRole('heading', { name: 'Statement summary' })).toBeVisible();
  const downloading = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download CSV statement' }).click();
  const download = await downloading;
  const csv = await readFile((await download.path())!, 'utf8');
  expect(csv).toContain('record_type,reference,timestamp_utc');
  expect(csv).toContain('OPENING');
  expect(csv).toContain('CLOSING');
  expect(csv).toContain('Portfolio walkthrough');
  if (process.env.CAPTURE_V2 === '1') {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: '../docs/screenshots/v2-statements.png', fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test('scheduled transfer is executed by real worker and delivered to inbox', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await page.getByRole('link', { name: 'Schedules', exact: true }).click();
  await page.getByRole('link', { name: 'Create schedule', exact: true }).click();
  await page.getByLabel('Scheduled amount (VND)').fill('100');
  await page.getByLabel('Schedule memo').fill('V2 real worker walkthrough');
  const due = new Date(Date.now() + 10000).toISOString().slice(0, 19);
  await page.getByLabel('First run (local time)').fill(due);
  await page.getByLabel('IANA timezone').fill('UTC');
  await page.getByRole('button', { name: 'Review schedule', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Review schedule' })).toContainText(
    'No funds move or are reserved now.',
  );
  await page.getByRole('button', { name: 'Confirm schedule', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Schedule details.' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'SUCCEEDED', exact: true })).toBeVisible({
    timeout: 25000,
  });
  if (process.env.CAPTURE_V2 === '1')
    await page.screenshot({ path: '../docs/screenshots/v2-schedule.png', fullPage: true });
  await page.getByRole('link', { name: 'View receipt', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Transfer complete.' })).toBeVisible();
  await expect(page.getByText('V2 real worker walkthrough', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Inbox', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Scheduled transfer succeeded', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Mark all read' }).click();
  await expect(page.getByRole('status')).toContainText('0 unread');
  if (process.env.CAPTURE_V2 === '1')
    await page.screenshot({ path: '../docs/screenshots/v2-inbox.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
