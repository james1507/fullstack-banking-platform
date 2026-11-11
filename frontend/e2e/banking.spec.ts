import { test, expect } from '@playwright/test';
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
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Looking good, Alice.' })).toBeVisible();
  const before = await page.request.post('/api/v1/auth/login', {
    headers: { Origin: origin },
    data: { email: 'alice@example.test', password: 'DemoPass123!' },
  });
  const token = (await before.json()).access_token;
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
