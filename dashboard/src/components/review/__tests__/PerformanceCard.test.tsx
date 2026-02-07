import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PerformanceCard } from '../PerformanceCard'

// Mock the hooks and utilities
vi.mock('@/hooks/usePerformanceData', () => ({
  usePerformanceData: vi.fn(),
}))

import { usePerformanceData } from '@/hooks/usePerformanceData'

const mockUsePerformanceData = usePerformanceData as ReturnType<typeof vi.fn>

describe('PerformanceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('renders loading skeleton while fetching data', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: true,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(screen.getByText('PERFORMANCE (30d)')).toBeInTheDocument()
      // Should show skeleton elements
      const skeletons = document.querySelectorAll('.animate-pulse')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('Error State', () => {
    it('handles fetch errors gracefully', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: false,
        error: 'Failed to fetch performance data',
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(screen.getByText(/failed to load performance/i)).toBeInTheDocument()
    })
  })

  describe('No Data State', () => {
    it('shows no data message when performance data unavailable', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(screen.getByText(/no performance data available/i)).toBeInTheDocument()
    })
  })

  describe('Collapsed State', () => {
    it('renders collapsed state with key metrics summary', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(screen.getByText(/45\.2K impressions/i)).toBeInTheDocument()
      expect(screen.getByText(/3\.2% CTR/i)).toBeInTheDocument()
      expect(screen.getByText(/\$2,847/i)).toBeInTheDocument()
    })

    it('shows status indicator in collapsed state', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(screen.getByText(/below avg/i)).toBeInTheDocument()
    })
  })

  describe('Expanded State', () => {
    it('renders expanded state with full comparison table when baseline exists', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      // Click to expand
      const trigger = screen.getByRole('button', { name: /performance/i })
      await user.click(trigger)

      // Should show comparison table headers
      await waitFor(() => {
        expect(screen.getByText(/CURRENT/i)).toBeInTheDocument()
        expect(screen.getByText(/BASELINE/i)).toBeInTheDocument()
        expect(screen.getByText(/CHANGE/i)).toBeInTheDocument()
      })

      // Should show baseline values
      expect(screen.getByText(/42,100/i)).toBeInTheDocument()
      expect(screen.getByText(/1,263/i)).toBeInTheDocument()
    })

    it('shows no baseline message when baseline data unavailable', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'no-data',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      // Click to expand
      const trigger = screen.getByRole('button', { name: /performance/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText(/baseline will be captured when content is published/i)).toBeInTheDocument()
      })
    })
  })

  describe('Status Indicator Logic', () => {
    it('shows green status when CTR >= category avg AND improving', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1862,
          ctr: 0.041,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'good',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const statusIndicator = screen.getByTestId('status-indicator')
      expect(statusIndicator).toHaveClass('bg-green-500')
    })

    it('shows yellow status when CTR below average', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const statusIndicator = screen.getByTestId('status-indicator')
      expect(statusIndicator).toHaveClass('bg-yellow-500')
    })

    it('shows red status when CTR significantly below average (>20% under)', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.025,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'critical',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const statusIndicator = screen.getByTestId('status-indicator')
      expect(statusIndicator).toHaveClass('bg-red-500')
    })

    it('shows gray status when no performance data available', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const statusIndicator = screen.getByTestId('status-indicator')
      expect(statusIndicator).toHaveClass('bg-gray-500')
    })
  })

  describe('Collapsible Behavior', () => {
    it('toggles between collapsed and expanded on click', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const trigger = screen.getByRole('button', { name: /performance/i })

      // Initially collapsed
      expect(screen.queryByText(/CURRENT/i)).not.toBeInTheDocument()

      // Click to expand
      await user.click(trigger)
      await waitFor(() => {
        expect(screen.getByText(/CURRENT/i)).toBeInTheDocument()
      })

      // Click to collapse
      await user.click(trigger)
      await waitFor(() => {
        expect(screen.queryByText(/CURRENT/i)).not.toBeInTheDocument()
      })
    })

    it('shows chevron icon rotation animation', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const chevron = screen.getByTestId('chevron-icon')

      // Initially should point down
      expect(chevron).not.toHaveClass('rotate-180')

      // Click to expand
      const trigger = screen.getByRole('button', { name: /performance/i })
      await user.click(trigger)

      // Should rotate up
      await waitFor(() => {
        expect(chevron).toHaveClass('rotate-180')
      })
    })
  })

  describe('Accessibility', () => {
    it('supports keyboard navigation', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const trigger = screen.getByRole('button', { name: /performance/i })

      // Tab to focus
      await user.tab()
      expect(trigger).toHaveFocus()

      // Enter to expand
      await user.keyboard('{Enter}')
      await waitFor(() => {
        expect(screen.getByText(/baseline will be captured/i)).toBeInTheDocument()
      })

      // Space to collapse
      await user.keyboard(' ')
      await waitFor(() => {
        expect(screen.queryByText(/baseline will be captured/i)).not.toBeInTheDocument()
      })
    })

    it('announces collapsed/expanded state to screen readers', () => {
      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const trigger = screen.getByRole('button', { name: /performance/i })
      expect(trigger).toHaveAttribute('aria-expanded', 'false')
    })
  })

  describe('Change Percentage Calculations', () => {
    it('correctly calculates positive change percentages', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: {
          avg_impressions: 42100,
          avg_clicks: 1263,
          avg_ctr: 0.030,
          avg_conversions: 71,
          avg_conversion_value: 2201,
        },
        status: 'warning',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const trigger = screen.getByRole('button', { name: /performance/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText(/\+7\.4%/i)).toBeInTheDocument() // Impressions change
        expect(screen.getByText(/\+14\.5%/i)).toBeInTheDocument() // Clicks change
      })
    })

    it('shows em-dash when baseline unavailable', async () => {
      const user = userEvent.setup()

      mockUsePerformanceData.mockReturnValue({
        current: {
          impressions: 45200,
          clicks: 1446,
          ctr: 0.032,
          conversions: 89,
          conversion_value: 2847,
        },
        baseline: null,
        status: 'no-data',
        loading: false,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      const trigger = screen.getByRole('button', { name: /performance/i })
      await user.click(trigger)

      // Should show message instead of table
      await waitFor(() => {
        expect(screen.getByText(/baseline will be captured/i)).toBeInTheDocument()
      })
    })
  })

  describe('Platform Parameter', () => {
    it('passes platform parameter to usePerformanceData hook', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: true,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" platform="bing" />)

      expect(mockUsePerformanceData).toHaveBeenCalledWith('920D-6', 'bing')
    })

    it('defaults to google platform when not specified', () => {
      mockUsePerformanceData.mockReturnValue({
        current: null,
        baseline: null,
        status: 'no-data',
        loading: true,
        error: null,
      })

      render(<PerformanceCard sku="920D-6" />)

      expect(mockUsePerformanceData).toHaveBeenCalledWith('920D-6', 'google')
    })
  })
})
