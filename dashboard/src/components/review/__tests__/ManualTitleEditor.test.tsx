import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import { ManualTitleEditor } from '../ManualTitleEditor'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('ManualTitleEditor', () => {
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

  it('opens with locked finish token in preview', async () => {
    const user = userEvent.setup()
    render(
      <ManualTitleEditor
        sku="CS-1"
        platform="google"
        currentTitle="Wall Mount Rod Brackets - Fire Engine Red - Carolina Collection"
        onSaved={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit base title/i }))

    expect(screen.getByText('{FINISH_NAME}')).toBeInTheDocument()
    expect(screen.getByText(/preview/i)).toBeInTheDocument()
  })

  it('submits manual template and applies to all variants', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    const fetchMock = vi.mocked(fetch)

    render(
      <ManualTitleEditor
        sku="CS-1"
        platform="google"
        currentTitle="Wall Mount Rod Brackets - {FINISH_NAME} - Carolina Collection"
        onSaved={onSaved}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit base title/i }))
    await user.clear(screen.getByLabelText(/title prefix/i))
    await user.type(screen.getByLabelText(/title prefix/i), 'Designer Rod Brackets')
    await user.clear(screen.getByLabelText(/title suffix/i))
    await user.type(screen.getByLabelText(/title suffix/i), '- Carolina Collection')

    await user.click(screen.getByRole('button', { name: /save and apply to all variants/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/review/manual-title',
        expect.objectContaining({
          method: 'POST',
        }),
      )
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/review/manual-title')
    expect(init?.body).toContain('Designer Rod Brackets {FINISH_NAME} - Carolina Collection')
    expect(onSaved).toHaveBeenCalled()
  })
})
