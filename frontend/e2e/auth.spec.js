import { expect, test } from '@playwright/test'
import { installApiMocks, mockUser } from './helpers.js'

test.describe('auth critical flows', () => {
  test('unauthenticated /dashboard redirects to sign-in', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/signin/)
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await expect(page.getByText('Advance Athlete Lab')).toBeVisible()
  })

  test('unauthenticated /coach redirects to sign-in', async ({ page }) => {
    await page.goto('/coach')
    await expect(page).toHaveURL(/\/signin/)
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
  })

  test('sign-in shows API error when credentials are rejected', async ({ page }) => {
    await installApiMocks(page, {
      handlers: {
        'POST /api/auth/login': async (route) => {
          await route.fulfill({
            status: 401,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Incorrect email or password' }),
          })
        },
      },
    })

    await page.goto('/signin')
    await page.locator('input[type="email"]').fill('athlete@example.com')
    await page.locator('input[type="password"]').fill('wrong-password')
    await page.getByRole('button', { name: 'Sign In' }).click()

    await expect(page.getByText('Incorrect email or password')).toBeVisible()
    await expect(page).toHaveURL(/\/signin/)
  })

  test('successful sign-in with mocked auth lands on dashboard', async ({ page }) => {
    const user = mockUser()
    await installApiMocks(page, { user })

    await page.goto('/signin')
    await page.locator('input[type="email"]').fill(user.email)
    await page.locator('input[type="password"]').fill('password123')
    await page.getByRole('button', { name: 'Sign In' }).click()

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Welcome back, Test' })).toBeVisible()
  })
})
