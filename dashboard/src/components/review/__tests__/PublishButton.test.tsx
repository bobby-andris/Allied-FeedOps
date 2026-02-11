import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, afterEach } from 'vitest'

import { PublishButton } from '../PublishButton'

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

describe('PublishButton', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders readiness errors without duplicate React keys when multiple blockers exist for one platform', async () => {
    const user = userEvent.setup()
    const duplicateKeyErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        error: 'One or more requested platforms are not ready for publishing.',
        code: 'publish_platform_not_ready',
        readiness_errors: [
          {
            platform: 'google',
            code: 'google_title_not_approved',
            reason: 'google title is not approved',
            actionableMessage: 'Approve google title content before publishing.',
          },
          {
            platform: 'google',
            code: 'google_description_not_approved',
            reason: 'google description is not approved',
            actionableMessage: 'Approve google description content before publishing.',
          },
        ],
      }),
    })

    vi.stubGlobal('fetch', fetchMock)

    render(
      <PublishButton
        sku="1016"
        platformReadiness={{
          google: {
            ready: false,
            blockers: [
              {
                code: 'google_title_not_approved',
                reason: 'google title is not approved',
                actionableMessage: 'Approve google title content before publishing.',
              },
            ],
          },
          bing: {
            ready: false,
            blockers: [
              {
                code: 'bing_title_not_approved',
                reason: 'bing title is not approved',
                actionableMessage: 'Approve bing title content before publishing.',
              },
            ],
          },
          shopify: {
            ready: false,
            blockers: [
              {
                code: 'shopify_title_not_approved',
                reason: 'shopify title is not approved',
                actionableMessage: 'Approve shopify title content before publishing.',
              },
            ],
          },
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Publish' }))
    await user.click(screen.getByRole('checkbox', { name: 'google' }))
    await user.click(screen.getByRole('button', { name: /Publish to production/i }))

    await waitFor(() => {
      expect(screen.getByText('Results')).toBeInTheDocument()
    })

    expect(screen.getByText('google title is not approved')).toBeInTheDocument()
    expect(screen.getByText('google description is not approved')).toBeInTheDocument()

    const duplicateKeyWarnings = duplicateKeyErrorSpy.mock.calls.filter((call) => {
      const firstArg = String(call[0] ?? '')
      return firstArg.includes('Encountered two children with the same key')
    })

    expect(duplicateKeyWarnings).toHaveLength(0)
  })
})
