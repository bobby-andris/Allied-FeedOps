import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import { ManualDescriptionEditor } from '../ManualDescriptionEditor'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('ManualDescriptionEditor', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      }),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('opens with locked finish sentence token in preview', async () => {
    const user = userEvent.setup()
    render(
      <ManualDescriptionEditor
        sku="CS-1"
        platform="google"
        currentDescription="Solid brass shower bracket with precision mounting. {FINISH_SENTENCE} Built for long-term durability."
        onSaved={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit base description/i }))

    expect(screen.getByText('{FINISH_SENTENCE}')).toBeInTheDocument()
    expect(screen.getByText(/preview/i)).toBeInTheDocument()
  })

  it('submits manual description template and applies to all variants', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    const fetchMock = vi.mocked(fetch)

    render(
      <ManualDescriptionEditor
        sku="CS-1"
        platform="google"
        currentDescription="Solid brass shower bracket with precision mounting. {FINISH_SENTENCE} Built for long-term durability."
        onSaved={onSaved}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit base description/i }))
    await user.clear(screen.getByLabelText(/description prefix/i))
    await user.type(
      screen.getByLabelText(/description prefix/i),
      'Solid brass shower bracket with precision mounting.',
    )
    await user.clear(screen.getByLabelText(/description suffix/i))
    await user.type(
      screen.getByLabelText(/description suffix/i),
      'Built for long-term durability with concealed mounting.',
    )

    await user.click(screen.getByRole('button', { name: /save and apply to all variants/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/review/manual-description',
        expect.objectContaining({
          method: 'POST',
        }),
      )
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/review/manual-description')
    expect(init?.body).toContain('{FINISH_SENTENCE}')
    expect(onSaved).toHaveBeenCalled()
  })
})
