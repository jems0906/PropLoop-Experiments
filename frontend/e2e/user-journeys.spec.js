import { expect, test } from '@playwright/test'

const adminEmail = 'admin@proploop.test'
const adminPassword = 'e2e-admin-password-2026'

async function signIn(page) {
  await page.goto('/')
  await page.getByLabel('Email').fill(adminEmail)
  await page.getByLabel('Password').fill(adminPassword)
  await page.locator('form.gap-form').getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /Make the next move/ })).toBeVisible()
}

test('rejects invalid credentials and then signs in an administrator', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Email').fill(adminEmail)
  await page.getByLabel('Password').fill('incorrect-e2e-password')
  await page.locator('form.gap-form').getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid email or password')

  await page.getByLabel('Password').fill(adminPassword)
  await page.locator('form.gap-form').getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /Make the next move/ })).toBeVisible()
})

test('runs an experiment from hypothesis through a recorded ship decision', async ({ page }) => {
  await signIn(page)
  await page.getByRole('button', { name: 'New experiment' }).click()
  await page.getByLabel('Experiment name').fill('E2E rent reminder experiment')
  await page.getByLabel('Problem statement').fill('Overdue rent outreach is inconsistent across properties.')
  await page.getByLabel('Hypothesis').fill('Personal reminders will improve on-time recovery because tenants receive clear next steps.')
  await page.getByLabel('Primary target metric').fill('On-time recovery rate')
  await page.locator('.create-modal').getByRole('button', { name: 'Create experiment' }).click()
  await expect(page.getByRole('heading', { name: 'GitHub coding agent' })).toBeVisible()
  await expect(page.getByText(/OPENAI_API_KEY/)).toBeVisible()

  await page.getByRole('button', { name: 'Approve Hypothesis' }).click()
  await page.getByRole('button', { name: 'Generate spec' }).click()
  await expect(page.getByRole('heading', { name: 'AI-assisted spec' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve spec' }).click()
  await page.getByRole('button', { name: 'Approve task plan' }).click()

  const taskButtons = page.locator('.task-check:not(.checked)')
  await expect(taskButtons.first()).toBeVisible()
  const taskCount = await taskButtons.count()
  expect(taskCount).toBeGreaterThan(0)
  for (let completed = 0; completed < taskCount; completed += 1) {
    const nextTask = page.locator('.task-check:not(.checked)').first()
    await expect(nextTask).toBeVisible()
    await nextTask.click()
    await expect(page.getByRole('heading', { name: `Build checklist ${completed + 1}/${taskCount}` })).toBeVisible()
  }
  await page.getByRole('button', { name: 'Approve Build' }).click()
  await page.getByRole('button', { name: 'Add metric result' }).click()
  await page.locator('.metric-form').getByLabel('Baseline').fill('62')
  await page.locator('.metric-form').getByLabel('Observed').fill('74')
  await page.locator('.metric-form').getByLabel('Sample size').fill('120')
  await page.getByRole('button', { name: 'Record descriptive result' }).click()
  await page.getByRole('button', { name: 'Approve Measure' }).click()
  await page.getByRole('button', { name: 'Ship' }).click()
  await page.getByLabel('Why this decision?').fill('Recovery improved and the agreed error guardrail remained acceptable.')
  await page.getByRole('button', { name: 'Ship' }).click()

  await expect(page.locator('.decision-history')).toContainText('ship')
  await expect(page.locator('.title-meta')).toContainText('Shipped')
})

test('creates and accepts a team invitation', async ({ page }) => {
  await signIn(page)
  await page.getByRole('button', { name: 'Team accounts' }).click()
  await page.getByLabel('Email', { exact: true }).fill('new-member@proploop.test')
  await page.locator('.gap-form-grid').getByLabel('Role').selectOption('reviewer')
  await page.getByRole('button', { name: 'Create invitation' }).click()
  await expect(page.getByText('New invitation token')).toBeVisible()
  const invitationToken = await page.getByLabel('Token').inputValue()
  expect(invitationToken.length).toBeGreaterThanOrEqual(20)

  await page.getByRole('button', { name: 'Sign out' }).click()
  await page.getByRole('button', { name: 'Accept invite' }).click()
  await page.getByLabel('Email').fill('new-member@proploop.test')
  await page.getByLabel('Name').fill('E2E Reviewer')
  await page.getByLabel('Password').fill('e2e-reviewer-password-2026')
  await page.getByLabel('Invitation token').fill(invitationToken)
  await page.getByRole('button', { name: 'Join team' }).click()
  await expect(page.getByRole('heading', { name: 'Team settings' })).toBeVisible()
  await expect(page.locator('.gap-facts')).toContainText('new-member@proploop.test')
  await expect(page.locator('.gap-facts')).toContainText('reviewer')
  await expect(page.getByRole('button', { name: 'Create invitation' })).toHaveCount(0)
})
