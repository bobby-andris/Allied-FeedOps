import { describe, expect, it } from 'vitest'
import {
  EXISTING_FUNNEL_UI_LIMIT,
  NEEDS_DECISION_UI_LIMIT,
} from '@/lib/shopping-funnel/ui-performance'

describe('shopping funnel UI performance limits', () => {
  it('caps needs-decision page size to keep interactions responsive', () => {
    expect(NEEDS_DECISION_UI_LIMIT).toBeLessThanOrEqual(500)
  })

  it('caps existing-funnel page size to keep interactions responsive', () => {
    expect(EXISTING_FUNNEL_UI_LIMIT).toBeLessThanOrEqual(1000)
  })
})
