import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IntentControlCenterPage from '@/app/(dashboard)/intent-control-center/page'

describe('IntentControlCenterPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('allows acknowledging an open guardrail incident from the control center', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'

      if (url.includes('/api/intent/decisions')) {
        return new Response(
          JSON.stringify({
            policy_version: 'intent_v1',
            total_terms_evaluated: 1,
            review_required_count: 1,
            action_distribution: { funnel: 1 },
            decisions: [
              {
                search_term: 'brass robe hook',
                metrics: {
                  impressions: 100,
                  clicks: 12,
                  conversions: 2,
                  conversionsValue: 48,
                  costMicros: 14000000,
                },
                decision: {
                  routeAction: 'funnel',
                  recommendedTier: 'medium',
                  confidence: 0.72,
                  requiresReview: true,
                  reasonCodes: ['route_shopping_medium'],
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

      if (url.includes('/api/intent/guardrails') && method === 'GET') {
        return new Response(
          JSON.stringify({
            status: 'hold',
            reason_codes: ['high_incident_stack'],
            stale_data_hours: 2,
            open_critical_incidents: 1,
            open_high_incidents: 2,
            derived_incidents: [
              {
                ruleId: 'critical_incident_open',
                severity: 'critical',
                message: 'Critical guardrail incidents are still open.',
              },
            ],
            open_incidents: [
              {
                id: 'incident-1',
                rule_id: 'critical_incident_open',
                severity: 'critical',
                status: 'open',
                message: 'Critical guardrail incidents are still open.',
                suggested_action: 'Run rollback',
                created_at: '2026-02-20T12:00:00.000Z',
              },
            ],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/bid-policy')) {
        return new Response(
          JSON.stringify({
            decision_count: 0,
            decisions: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/guardrails/incidents') && method === 'POST') {
        return new Response(
          JSON.stringify({
            updated: true,
            incident: {
              id: 'incident-1',
              status: 'acknowledged',
            },
            warnings: [],
          }),
          { status: 200 }
        )
      }

      return new Response(JSON.stringify({}), { status: 200 })
    })

    const user = userEvent.setup()
    render(<IntentControlCenterPage />)

    const acknowledgeButton = await screen.findByRole('button', {
      name: /acknowledge incident-1/i,
    })
    await user.click(acknowledgeButton)

    await waitFor(() => {
      expect(screen.getByText(/incident incident-1 updated to acknowledged\./i)).toBeInTheDocument()
    })
  })

  it('allows running rollback from an open guardrail incident', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'

      if (url.includes('/api/intent/decisions')) {
        return new Response(
          JSON.stringify({
            policy_version: 'intent_v1',
            total_terms_evaluated: 1,
            review_required_count: 1,
            action_distribution: { funnel: 1 },
            decisions: [
              {
                search_term: 'brass robe hook',
                metrics: {
                  impressions: 100,
                  clicks: 12,
                  conversions: 2,
                  conversionsValue: 48,
                  costMicros: 14000000,
                },
                decision: {
                  routeAction: 'funnel',
                  recommendedTier: 'medium',
                  confidence: 0.72,
                  requiresReview: true,
                  reasonCodes: ['route_shopping_medium'],
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

      if (url.includes('/api/intent/guardrails') && method === 'GET') {
        return new Response(
          JSON.stringify({
            status: 'hold',
            reason_codes: ['critical_incident_open'],
            stale_data_hours: 2,
            open_critical_incidents: 1,
            open_high_incidents: 0,
            derived_incidents: [
              {
                ruleId: 'critical_incident_open',
                severity: 'critical',
                message: 'Critical guardrail incidents are still open.',
              },
            ],
            open_incidents: [
              {
                id: 'incident-1',
                rule_id: 'critical_incident_open',
                severity: 'critical',
                status: 'open',
                message: 'Critical guardrail incidents are still open.',
                suggested_action: 'Run rollback',
                created_at: '2026-02-20T12:00:00.000Z',
              },
            ],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/bid-policy')) {
        return new Response(
          JSON.stringify({
            decision_count: 0,
            decisions: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/rollback') && method === 'GET') {
        return new Response(
          JSON.stringify({
            snapshot_count: 1,
            snapshots: [
              {
                id: 'snapshot-1',
                snapshot_key: 'intent_v1_2026_02_20',
                policy_version: 'intent_v1',
                created_at: '2026-02-20T12:00:00.000Z',
              },
            ],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/rollback') && method === 'POST') {
        return new Response(
          JSON.stringify({
            rollback_applied: true,
            deactivated_negative_count: 2,
          }),
          { status: 200 }
        )
      }

      return new Response(JSON.stringify({}), { status: 200 })
    })

    const user = userEvent.setup()
    render(<IntentControlCenterPage />)

    const rollbackButton = await screen.findByRole('button', {
      name: /run rollback incident-1/i,
    })
    await user.click(rollbackButton)

    await waitFor(() => {
      expect(screen.getByText(/rollback executed for incident-1/i)).toBeInTheDocument()
      expect(screen.getByText(/deactivated negatives: 2/i)).toBeInTheDocument()
    })
  })

  it('renders operator calibration and decision consistency analytics', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()

      if (url.includes('/api/intent/decisions')) {
        return new Response(
          JSON.stringify({
            policy_version: 'intent_v1',
            total_terms_evaluated: 5,
            review_required_count: 2,
            action_distribution: { funnel: 4, branded: 1 },
            decisions: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/guardrails')) {
        return new Response(
          JSON.stringify({
            status: 'go',
            reason_codes: ['guardrails_clear'],
            stale_data_hours: 0.4,
            open_critical_incidents: 0,
            open_high_incidents: 0,
            derived_incidents: [],
            open_incidents: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/bid-policy')) {
        return new Response(
          JSON.stringify({
            decision_count: 0,
            decisions: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/rollback')) {
        return new Response(
          JSON.stringify({
            snapshot_count: 0,
            snapshots: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/intent/review-analytics')) {
        return new Response(
          JSON.stringify({
            summary: {
              total_actions: 24,
              unique_entities: 11,
              unique_actors: 3,
              consistency_rate: 0.82,
              alignment_rate: 0.76,
              review_velocity_24h: 7,
            },
            queue_summaries: [
              {
                queue_name: 'search_governance',
                total_actions: 14,
                unique_entities: 6,
                unique_actors: 3,
                consistency_rate: 0.79,
                alignment_rate: 0.74,
              },
            ],
            actor_summaries: [
              {
                actor: 'dashboard:search-governance',
                total_actions: 9,
                unique_entities: 5,
                queue_count: 2,
                alignment_rate: 0.88,
              },
            ],
            conflict_entities: [],
            warnings: [],
          }),
          { status: 200 }
        )
      }

      return new Response(JSON.stringify({}), { status: 200 })
    })

    render(<IntentControlCenterPage />)

    expect(await screen.findByText(/operator calibration & decision consistency/i)).toBeInTheDocument()
    expect(screen.getByText(/^review actions$/i)).toBeInTheDocument()
    expect(screen.getByText(/7 in last 24h/i)).toBeInTheDocument()
    expect(screen.getByText(/82%/)).toBeInTheDocument()
  })
})
