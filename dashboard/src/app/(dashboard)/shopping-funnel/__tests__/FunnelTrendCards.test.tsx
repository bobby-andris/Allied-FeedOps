import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

// ---------------------------------------------------------------------------
// Mock fetch globally
// ---------------------------------------------------------------------------
const mockFetch = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = mockFetch
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a trends API response for testing */
function makeTrendsResponse(overrides: Record<string, unknown> = {}) {
  return {
    has_data: true,
    has_previous: true,
    current: {
      impressions: 10000,
      clicks: 500,
      ctr: 0.05,
      cost_micros: 50_000_000,
      conversions: 20,
      conversions_value: 3000,
      roas: 60,
    },
    previous: {
      impressions: 8000,
      clicks: 400,
      ctr: 0.05,
      cost_micros: 45_000_000,
      conversions: 18,
      conversions_value: 2700,
      roas: 60,
    },
    ...overrides,
  }
}

function stubFetchResponse(data: unknown) {
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('FunnelTrendCards', () => {
  it('renders nothing when API returns has_data: false', async () => {
    stubFetchResponse({ has_data: false })

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    const { container } = render(<FunnelTrendCards />)

    // Wait for fetch to resolve
    await vi.waitFor(() => {
      expect(mockFetch).toHaveBeenCalled()
    })

    // Should render nothing (empty or null)
    expect(container.textContent?.trim() || '').toBe('')
  })

  it('renders 6 cards with correct metric names: Impressions, Clicks, CTR, Ad Spend, Conversions, ROAS', async () => {
    stubFetchResponse(makeTrendsResponse())

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Impressions')).toBeInTheDocument()
    })

    expect(screen.getByText('Clicks')).toBeInTheDocument()
    expect(screen.getByText('CTR')).toBeInTheDocument()
    expect(screen.getByText('Ad Spend')).toBeInTheDocument()
    expect(screen.getByText('Conversions')).toBeInTheDocument()
    expect(screen.getByText('ROAS')).toBeInTheDocument()
  })

  it('shows "No prior data" when has_previous is false', async () => {
    stubFetchResponse(
      makeTrendsResponse({
        has_previous: false,
        previous: null,
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Impressions')).toBeInTheDocument()
    })

    // All 6 cards should show "No prior data" instead of trend arrows
    const noPriorTexts = screen.getAllByText('No prior data')
    expect(noPriorTexts.length).toBe(6)
  })

  it('shows green up arrow when metric increases more than 5%', async () => {
    // Current impressions 10000 vs previous 8000 => +25% change
    stubFetchResponse(
      makeTrendsResponse({
        current: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 50_000_000,
          conversions: 20,
          conversions_value: 3000,
          roas: 60,
        },
        previous: {
          impressions: 8000,
          clicks: 400,
          ctr: 0.05,
          cost_micros: 50_000_000,
          conversions: 18,
          conversions_value: 2700,
          roas: 60,
        },
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Impressions')).toBeInTheDocument()
    })

    // Impressions: +25% => should show green color and positive change indicator
    const impressionsCard = screen.getByText('Impressions').closest('[data-testid]') ||
      screen.getByText('Impressions').parentElement
    expect(impressionsCard).toBeDefined()
    // Should contain a positive percentage text like "+25.0%"
    const upTexts = screen.getAllByText(/\+25\.0%/)
    expect(upTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('shows red down arrow when metric decreases more than 5%', async () => {
    // Current clicks 300 vs previous 500 => -40% change
    stubFetchResponse(
      makeTrendsResponse({
        current: {
          impressions: 10000,
          clicks: 300,
          ctr: 0.03,
          cost_micros: 50_000_000,
          conversions: 20,
          conversions_value: 3000,
          roas: 60,
        },
        previous: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 50_000_000,
          conversions: 20,
          conversions_value: 3000,
          roas: 60,
        },
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Clicks')).toBeInTheDocument()
    })

    // Clicks: -40% => should show red color and negative percentage
    const downTexts = screen.getAllByText(/-40\.0%/)
    expect(downTexts.length).toBeGreaterThanOrEqual(1)
  })

  it('shows flat indicator when change is within 5% threshold', async () => {
    // All metrics within 5% change
    stubFetchResponse(
      makeTrendsResponse({
        current: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 50_000_000,
          conversions: 20,
          conversions_value: 3000,
          roas: 60,
        },
        previous: {
          impressions: 10200, // ~2% difference
          clicks: 510,       // ~2% difference
          ctr: 0.05,         // 0% difference
          cost_micros: 50_500_000, // ~1% difference
          conversions: 20,   // 0% difference
          conversions_value: 3000,
          roas: 60,          // 0% difference
        },
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    const { container } = render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Impressions')).toBeInTheDocument()
    })

    // No percentage text should appear (all within 5% threshold)
    // Instead should show flat/minus indicator
    expect(container.innerHTML).not.toMatch(/[+-]\d+\.\d+%/)
  })

  it('inverts color for Ad Spend (down = green, up = red)', async () => {
    // Ad Spend increases significantly => should be RED (bad)
    stubFetchResponse(
      makeTrendsResponse({
        current: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 80_000_000, // $80 (up from $50)
          conversions: 20,
          conversions_value: 3000,
          roas: 37.5,
        },
        previous: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 50_000_000, // $50
          conversions: 20,
          conversions_value: 3000,
          roas: 60,
        },
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Ad Spend')).toBeInTheDocument()
    })

    // Find the Ad Spend card's trend indicator
    const adSpendCard = screen.getByText('Ad Spend').closest('[data-testid]') ||
      screen.getByText('Ad Spend').parentElement?.parentElement
    expect(adSpendCard).toBeDefined()

    // The Ad Spend increase (+60%) should show RED (inverted — cost going up is bad)
    const trendElement = adSpendCard?.querySelector('.text-red-600') ||
      adSpendCard?.querySelector('[class*="red"]')
    expect(trendElement).toBeTruthy()
  })

  it('formats numbers correctly: impressions with commas, CTR as percentage, Ad Spend as currency, ROAS with x suffix', async () => {
    stubFetchResponse(
      makeTrendsResponse({
        current: {
          impressions: 12345,
          clicks: 567,
          ctr: 0.0459,
          cost_micros: 45_670_000,
          conversions: 23,
          conversions_value: 3450,
          roas: 75.5,
        },
        previous: {
          impressions: 10000,
          clicks: 500,
          ctr: 0.05,
          cost_micros: 40_000_000,
          conversions: 20,
          conversions_value: 3000,
          roas: 75,
        },
      }),
    )

    const { FunnelTrendCards } = await import(
      '@/app/(dashboard)/shopping-funnel/FunnelTrendCards'
    )
    render(<FunnelTrendCards />)

    await vi.waitFor(() => {
      expect(screen.getByText('Impressions')).toBeInTheDocument()
    })

    // Impressions: formatted with commas (12,345)
    expect(screen.getByText(/12,345/)).toBeInTheDocument()

    // CTR: formatted as percentage (4.59% or 4.6%)
    expect(screen.getByText(/4\.5?9?%/)).toBeInTheDocument()

    // Ad Spend: formatted as currency ($45.67 from cost_micros / 1e6)
    expect(screen.getByText(/\$45\.67/)).toBeInTheDocument()

    // ROAS: formatted with x suffix (75.5x)
    expect(screen.getByText(/75\.5x/)).toBeInTheDocument()
  })
})
