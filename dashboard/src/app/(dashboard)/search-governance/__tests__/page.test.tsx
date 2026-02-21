import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchGovernancePage from '@/app/(dashboard)/search-governance/page'

describe('SearchGovernancePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('generates draft candidates and refreshes the queue', async () => {
    let candidateCalls = 0

    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'

      if (url.includes('/api/search/governance/candidates') && method === 'GET') {
        candidateCalls += 1
        if (candidateCalls === 1) {
          return new Response(
            JSON.stringify({
              candidate_count: 0,
              candidates: [],
            }),
            { status: 200 }
          )
        }

        return new Response(
          JSON.stringify({
            candidate_count: 1,
            candidates: [
              {
                search_term: 'unlacquered brass towel bar',
                custom_label_0s: [{ custom_label_0: 'HIGH' }],
                governance: {
                  action: 'promote_to_exact',
                  recommendedTier: 'exact',
                  confidence: 0.84,
                  reasonCodes: ['exact_graduation_threshold_met'],
                },
                buildout: {
                  cluster_key: 'towel bar',
                  suggested_campaign: 'Search | Product High | Towel Bar',
                  suggested_ad_group: 'Towel Bar | Exact',
                },
                route_decision: {
                  classification: {
                    intentClass: 'PRODUCT_HIGH',
                  },
                },
              },
            ],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/search/governance/drafts') && method === 'POST') {
        return new Response(
          JSON.stringify({
            evaluated_count: 20,
            eligible_count: 8,
            drafted_count: 5,
            skipped_existing_count: 3,
            warnings: [],
          }),
          { status: 200 }
        )
      }

      return new Response(JSON.stringify({ applied_count: 0, warnings: [] }), { status: 200 })
    })

    const user = userEvent.setup()
    render(<SearchGovernancePage />)

    const generateButton = await screen.findByRole('button', { name: /generate drafts/i })
    await user.click(generateButton)

    await waitFor(() => {
      expect(
        screen.getByText(/generated 5 draft candidate\(s\) from 8 eligible terms\./i)
      ).toBeInTheDocument()
    })

    expect(candidateCalls).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('unlacquered brass towel bar')).toBeInTheDocument()
    expect(screen.getByText(/search buildout briefs/i)).toBeInTheDocument()
    expect(screen.getByText(/Search \| Product High \| Towel Bar/i)).toBeInTheDocument()
  })

  it('runs tier movement evaluation with rollout safety status feedback', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'

      if (url.includes('/api/search/governance/candidates') && method === 'GET') {
        return new Response(
          JSON.stringify({
            candidate_count: 1,
            candidates: [
              {
                search_term: 'brass robe hook',
                custom_label_0s: [{ custom_label_0: 'MEDIUM' }],
                metrics: {
                  impressions: 140,
                  clicks: 19,
                  conversions: 4,
                  conversionsValue: 92,
                  costMicros: 24000000,
                },
                current_tier: 'phrase',
                governance: {
                  action: 'promote_to_exact',
                  recommendedTier: 'exact',
                  confidence: 0.81,
                  reasonCodes: ['exact_readiness_threshold_met'],
                },
                buildout: {
                  cluster_key: 'robe hook',
                  suggested_campaign: 'Search | Category Mid | Robe Hook',
                  suggested_ad_group: 'Robe Hook | Exact',
                },
                route_decision: {
                  classification: {
                    intentClass: 'CATEGORY_MID',
                  },
                },
              },
            ],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/search/governance/movements') && method === 'POST') {
        return new Response(
          JSON.stringify({
            generated_at: '2026-02-20T00:00:00.000Z',
            generated_count: 1,
            staged_count: 0,
            cancelled_count: 1,
            rollout_safety: {
              status: 'blocked',
            },
            warnings: [],
          }),
          { status: 200 }
        )
      }

      return new Response(JSON.stringify({ applied_count: 0, warnings: [] }), { status: 200 })
    })

    const user = userEvent.setup()
    render(<SearchGovernancePage />)

    const selectAllButton = await screen.findByRole('button', { name: /select all/i })
    await user.click(selectAllButton)

    const evaluateButton = await screen.findByRole('button', { name: /evaluate movements/i })
    await user.click(evaluateButton)

    await waitFor(() => {
      expect(
        screen.getByText(/movement run generated 1 decision\(s\); staged 0 action\(s\); safety: blocked\./i)
      ).toBeInTheDocument()
    })
  })
})
