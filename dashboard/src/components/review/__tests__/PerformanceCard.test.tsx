import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PerformanceCard } from '../PerformanceCard'

const nowIso = new Date().toISOString()

describe('PerformanceCard', () => {
  it('shows no-data state when neither snapshots nor baselines exist', () => {
    render(<PerformanceCard sku="920D-6" baselines={[]} snapshots={[]} />)

    expect(screen.getByText('PERFORMANCE (30d)')).toBeInTheDocument()
    expect(screen.getByText(/No data yet\. Performance tracking begins after first publish\./i)).toBeInTheDocument()
    expect(screen.getByTestId('status-indicator')).toHaveClass('bg-gray-500')
  })

  it('shows baseline-only state when baseline exists but no current snapshots', () => {
    render(
      <PerformanceCard
        sku="920D-6"
        baselines={[
          {
            master_sku: '920D-6',
            platform: 'google',
            avg_impressions: 42100,
            avg_clicks: 1263,
            avg_ctr: 0.03,
            avg_conversions: 71,
            avg_cvr: 0.0562,
            avg_conversion_value: 2201,
            baseline_start_date: '2026-01-01',
            baseline_end_date: '2026-01-31',
            created_at: nowIso,
          },
        ]}
        snapshots={[]}
      />,
    )

    expect(screen.getByText('BASELINE (30d)')).toBeInTheDocument()
    expect(screen.getByText('42.1K')).toBeInTheDocument()
    expect(screen.getByText('1.3K')).toBeInTheDocument()
    expect(screen.getByText('3.0%')).toBeInTheDocument()
  })

  it('aggregates current snapshots for collapsed summary row', () => {
    render(
      <PerformanceCard
        sku="920D-6"
        baselines={[]}
        snapshots={[
          {
            id: '1',
            master_sku: '920D-6',
            platform: 'google',
            snapshot_date: nowIso,
            impressions: 20000,
            clicks: 640,
            ctr: 0.032,
            conversions: 40,
            cvr: 0.0625,
            conversion_value: 1000,
            days_since_publish: 3,
            fetched_at: nowIso,
          },
          {
            id: '2',
            master_sku: '920D-6',
            platform: 'google',
            snapshot_date: nowIso,
            impressions: 25200,
            clicks: 806,
            ctr: 0.032,
            conversions: 49,
            cvr: 0.0608,
            conversion_value: 1847,
            days_since_publish: 4,
            fetched_at: nowIso,
          },
        ]}
      />,
    )

    expect(screen.getByText('45.2K')).toBeInTheDocument()
    expect(screen.getByText('3.2%')).toBeInTheDocument()
    expect(screen.getByText('$2,847')).toBeInTheDocument()
    expect(screen.getByTestId('status-indicator')).toHaveClass('bg-red-500')
  })

  it('renders expanded baseline comparison table when baseline exists', async () => {
    const user = userEvent.setup()

    render(
      <PerformanceCard
        sku="920D-6"
        baselines={[
          {
            master_sku: '920D-6',
            platform: 'google',
            avg_impressions: 42100,
            avg_clicks: 1263,
            avg_ctr: 0.03,
            avg_conversions: 71,
            avg_cvr: 0.0562,
            avg_conversion_value: 2201,
            baseline_start_date: '2026-01-01',
            baseline_end_date: '2026-01-31',
            created_at: nowIso,
          },
        ]}
        snapshots={[
          {
            id: '1',
            master_sku: '920D-6',
            platform: 'google',
            snapshot_date: nowIso,
            impressions: 45200,
            clicks: 1446,
            ctr: 0.032,
            conversions: 89,
            cvr: 0.0615,
            conversion_value: 2847,
            days_since_publish: 5,
            fetched_at: nowIso,
          },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: /PERFORMANCE \(30d\)/i }))

    await waitFor(() => {
      expect(screen.getByText('Current')).toBeInTheDocument()
      expect(screen.getByText('Baseline')).toBeInTheDocument()
      expect(screen.getByText('Change')).toBeInTheDocument()
    })

    expect(screen.getByText('Impressions')).toBeInTheDocument()
    expect(screen.getAllByText('45.2K')).toHaveLength(2)
    expect(screen.getByText('42.1K')).toBeInTheDocument()
  })

  it('respects selected platform when filtering baselines and snapshots', () => {
    render(
      <PerformanceCard
        sku="920D-6"
        platform="bing"
        baselines={[
          {
            master_sku: '920D-6',
            platform: 'google',
            avg_impressions: 99999,
            avg_clicks: 3000,
            avg_ctr: 0.03,
            avg_conversions: 71,
            avg_cvr: 0.0562,
            avg_conversion_value: 2201,
            baseline_start_date: '2026-01-01',
            baseline_end_date: '2026-01-31',
            created_at: nowIso,
          },
          {
            master_sku: '920D-6',
            platform: 'bing',
            avg_impressions: 8000,
            avg_clicks: 160,
            avg_ctr: 0.02,
            avg_conversions: 8,
            avg_cvr: 0.05,
            avg_conversion_value: 500,
            baseline_start_date: '2026-01-01',
            baseline_end_date: '2026-01-31',
            created_at: nowIso,
          },
        ]}
        snapshots={[
          {
            id: 'google-1',
            master_sku: '920D-6',
            platform: 'google',
            snapshot_date: nowIso,
            impressions: 45200,
            clicks: 1446,
            ctr: 0.032,
            conversions: 89,
            cvr: 0.0615,
            conversion_value: 2847,
            days_since_publish: 2,
            fetched_at: nowIso,
          },
          {
            id: 'bing-1',
            master_sku: '920D-6',
            platform: 'bing',
            snapshot_date: nowIso,
            impressions: 10000,
            clicks: 200,
            ctr: 0.02,
            conversions: 10,
            cvr: 0.05,
            conversion_value: 500,
            days_since_publish: 2,
            fetched_at: nowIso,
          },
        ]}
      />,
    )

    // Uses bing snapshot totals, not google values.
    expect(screen.getByText('10.0K')).toBeInTheDocument()
    expect(screen.getByText('2.0%')).toBeInTheDocument()
    expect(screen.getByText('$500')).toBeInTheDocument()
  })
})
