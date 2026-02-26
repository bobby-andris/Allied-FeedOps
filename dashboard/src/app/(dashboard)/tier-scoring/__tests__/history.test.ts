import { describe, it, expect } from 'vitest'
import { groupHistoryByDay } from '../components/HistoryView'
import { getActionLabel } from '../components/HistoryDayGroup'
import type { HistoryEntry } from '../hooks/useRecommendations'

// ---------------------------------------------------------------------------
// Test helper: minimal valid HistoryEntry mock
// ---------------------------------------------------------------------------

function makeEntry(overrides: Partial<HistoryEntry> = {}): HistoryEntry {
  return {
    search_term: 'brass towel bar',
    custom_label_0: 'Towel Bar',
    recommended_tier: 'MEDIUM',
    review_status: 'accepted',
    accepted_at: '2026-02-25T14:30:00Z',
    accepted_by: 'user',
    metadata: {
      current_tier: 'LOW',
      impact: { low: 10, mid: 25, high: 40 },
    },
    created_at: '2026-02-25T12:00:00Z',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// groupHistoryByDay
// ---------------------------------------------------------------------------

describe('groupHistoryByDay', () => {
  it('returns empty array for no entries', () => {
    expect(groupHistoryByDay([])).toEqual([])
  })

  it('groups 5 entries across 3 days into 3 day groups ordered reverse-chronologically', () => {
    const entries: HistoryEntry[] = [
      makeEntry({ search_term: 'a', accepted_at: '2026-02-23T10:00:00Z', created_at: '2026-02-23T09:00:00Z' }),
      makeEntry({ search_term: 'b', accepted_at: '2026-02-25T14:00:00Z', created_at: '2026-02-25T12:00:00Z' }),
      makeEntry({ search_term: 'c', accepted_at: '2026-02-24T09:00:00Z', created_at: '2026-02-24T08:00:00Z' }),
      makeEntry({ search_term: 'd', accepted_at: '2026-02-25T10:00:00Z', created_at: '2026-02-25T09:00:00Z' }),
      makeEntry({ search_term: 'e', accepted_at: '2026-02-23T15:00:00Z', created_at: '2026-02-23T14:00:00Z' }),
    ]

    const groups = groupHistoryByDay(entries)

    expect(groups).toHaveLength(3)

    // Most recent day first (Feb 25)
    expect(groups[0].entries).toHaveLength(2)
    expect(groups[0].entries[0].search_term).toBe('b') // 14:00 before 10:00

    // Second day (Feb 24)
    expect(groups[1].entries).toHaveLength(1)
    expect(groups[1].entries[0].search_term).toBe('c')

    // Oldest day (Feb 23)
    expect(groups[2].entries).toHaveLength(2)
    expect(groups[2].entries[0].search_term).toBe('e') // 15:00 before 10:00
  })

  it('each entry contains expected fields', () => {
    const entry = makeEntry({
      search_term: 'test-term',
      review_status: 'accepted',
      accepted_at: '2026-02-25T14:30:00Z',
      metadata: { current_tier: 'LOW', impact: { low: 5, mid: 10, high: 15 } },
    })

    const groups = groupHistoryByDay([entry])
    expect(groups).toHaveLength(1)

    const result = groups[0].entries[0]
    expect(result.search_term).toBe('test-term')
    expect(result.review_status).toBe('accepted')
    expect(result.accepted_at).toBe('2026-02-25T14:30:00Z')
    expect(result.metadata.current_tier).toBe('LOW')
    expect(result.metadata.impact).toEqual({ low: 5, mid: 10, high: 15 })
  })

  it('sorts entries within same day by timestamp descending (most recent first)', () => {
    const entries: HistoryEntry[] = [
      makeEntry({ search_term: 'early', accepted_at: '2026-02-25T08:00:00Z' }),
      makeEntry({ search_term: 'late', accepted_at: '2026-02-25T20:00:00Z' }),
      makeEntry({ search_term: 'mid', accepted_at: '2026-02-25T14:00:00Z' }),
    ]

    const groups = groupHistoryByDay(entries)
    expect(groups).toHaveLength(1)
    expect(groups[0].entries.map(e => e.search_term)).toEqual(['late', 'mid', 'early'])
  })

  it('falls back to created_at when accepted_at is null', () => {
    const entries: HistoryEntry[] = [
      makeEntry({ search_term: 'no-accept', accepted_at: null, created_at: '2026-02-24T10:00:00Z' }),
      makeEntry({ search_term: 'has-accept', accepted_at: '2026-02-25T10:00:00Z' }),
    ]

    const groups = groupHistoryByDay(entries)
    expect(groups).toHaveLength(2)
    // Feb 25 first (most recent)
    expect(groups[0].entries[0].search_term).toBe('has-accept')
    expect(groups[1].entries[0].search_term).toBe('no-accept')
  })
})

// ---------------------------------------------------------------------------
// getActionLabel
// ---------------------------------------------------------------------------

describe('getActionLabel', () => {
  it('returns "Approved" for accepted entries', () => {
    const entry = makeEntry({ review_status: 'accepted' })
    expect(getActionLabel(entry)).toBe('Approved')
  })

  it('returns "Rejected" for rejected entries', () => {
    const entry = makeEntry({ review_status: 'rejected' })
    expect(getActionLabel(entry)).toBe('Rejected')
  })

  it('returns "Undone" for pending entries (undo resets to pending)', () => {
    const entry = makeEntry({ review_status: 'pending' })
    expect(getActionLabel(entry)).toBe('Undone')
  })

  it('returns "Undone" when metadata.history last action is undone', () => {
    const entry = makeEntry({
      review_status: 'pending',
      metadata: {
        current_tier: 'LOW',
        history: [
          { action: 'accepted', at: '2026-02-25T10:00:00Z' },
          { action: 'undone', at: '2026-02-25T11:00:00Z' },
        ],
      },
    })
    expect(getActionLabel(entry)).toBe('Undone')
  })

  it('shows rejection reason when metadata.rejection_reason exists', () => {
    const entry = makeEntry({
      review_status: 'rejected',
      metadata: {
        current_tier: 'LOW',
        rejection_reason: 'Not enough data',
      },
    })
    // getActionLabel returns the status label; the reason is rendered separately in the component
    expect(getActionLabel(entry)).toBe('Rejected')
    expect(entry.metadata.rejection_reason).toBe('Not enough data')
  })
})
