import { expect, test } from '@playwright/test'
import { authenticate } from './helpers.js'

test.describe('activities critical flow', () => {
  test('activities list renders mocked sessions', async ({ page }) => {
    await authenticate(page, {
      handlers: {
        'GET /api/activities': {
          items: [
            {
              id: 101,
              name: 'Morning Easy Run',
              sport_type: 'Run',
              activity_date: '2026-09-10',
              distance_m: 8000,
              moving_time_s: 2400,
              average_heartrate: 142,
              provider: 'strava',
            },
          ],
          total: 1,
          page: 1,
          page_size: 10,
        },
      },
    })

    await page.goto('/activities')
    await expect(page.getByRole('heading', { name: 'All activities' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'This month' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Morning Easy Run' })).toBeVisible()
    await expect(page.getByText('Total: 1')).toBeVisible()
  })
})
