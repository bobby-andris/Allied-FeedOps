import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import ExperimentLabPage from '@/app/(dashboard)/experiment-lab/page'

describe('ExperimentLabPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders weekly governance checkpoint summary for active experiments', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          experiments: [
            {
              experiment_key: 'exp-1',
              name: 'Search Buildout Holdout',
              initiative: 'Query mining + buildout',
              hypothesis: 'Graduated terms improve margin efficiency',
              status: 'active',
              start_date: '2026-02-01',
              end_date: null,
              success_threshold: 0.08,
              failure_threshold: -0.05,
              created_at: '2026-02-01T00:00:00.000Z',
            },
          ],
          outcomes: [
            {
              experiment_key: 'exp-1',
              metric_name: 'margin_roas',
              observed_lift: 0.11,
              sample_size: 640,
              status: 'observing',
              measured_at: '2026-02-20T12:00:00.000Z',
            },
          ],
          assignments: [
            { experiment_key: 'exp-1', entity_key: 'term-a', cohort: 'control', assigned_at: '2026-02-15T00:00:00.000Z' },
            { experiment_key: 'exp-1', entity_key: 'term-b', cohort: 'treatment', assigned_at: '2026-02-15T00:00:00.000Z' },
          ],
          governance: [
            {
              experiment_key: 'exp-1',
              latest_metric_name: 'margin_roas',
              latest_observed_lift: 0.11,
              latest_sample_size: 640,
              holdout_share: 0.5,
              weekly_status: 'promote_to_scale',
              checkpoint_due: false,
            },
          ],
          warnings: [],
        }),
        { status: 200 }
      )
    )

    render(<ExperimentLabPage />)

    await waitFor(() => {
      expect(screen.getByText(/weekly governance checkpoints/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/promote_to_scale/i)).toBeInTheDocument()
    expect(screen.getByText(/holdout share/i)).toBeInTheDocument()
    expect(screen.getAllByText(/assign holdouts/i).length).toBeGreaterThanOrEqual(1)
  })
})
