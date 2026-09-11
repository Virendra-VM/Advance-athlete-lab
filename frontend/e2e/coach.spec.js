import { expect, test } from '@playwright/test'
import { authenticate, mockUser } from './helpers.js'

test.describe('coach critical flows', () => {
  test('consent gate when AI coaching is off', async ({ page }) => {
    await authenticate(page, {
      handlers: {
        'GET /api/coach/status': {
          providers_configured: [],
          mode: 'rules',
          ai_consent: false,
          science_chunks: 0,
          has_active_plan: false,
        },
      },
    })

    await page.goto('/coach')
    await expect(page.getByText('Turn on AI coaching')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open settings' })).toBeVisible()
    await expect(page.getByPlaceholder('Message Coach')).toHaveCount(0)
  })

  test('coach shell loads with empty chat and composer', async ({ page }) => {
    await authenticate(page, {
      user: mockUser(),
      handlers: {
        'GET /api/coach/status': {
          providers_configured: [],
          active_provider: null,
          active_model: null,
          mode: 'rules',
          ai_consent: true,
          science_chunks: 0,
          has_active_plan: false,
        },
        'GET /api/coach/chat': { messages: [] },
        'GET /api/coach/warm': {
          context: null,
          proactive_prompts: [],
          todays_call: null,
        },
        'GET /api/coach/plan': null,
        'GET /api/coach/advice': null,
      },
    })

    await page.goto('/coach')
    await expect(page.getByText('AI Coach')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'What should we look at?' })).toBeVisible()
    await expect(page.getByPlaceholder('Message Coach')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
    await expect(page.getByText('Coaching only — not medical advice.')).toBeVisible()
  })
})
