import { describe, expect, it } from 'vitest'

import {
  CATCHALL_CUSTOM_LABEL,
  isCatchallCustomLabel,
  normalizeCustomLabelValue,
} from '@/lib/regeneration/custom-label'

describe('custom label helpers', () => {
  it('normalizes values to lowercase trimmed strings', () => {
    expect(normalizeCustomLabelValue('  Wall Mounted Towel Bars  ')).toBe('wall mounted towel bars')
  })

  it('returns null for empty values', () => {
    expect(normalizeCustomLabelValue('')).toBeNull()
    expect(normalizeCustomLabelValue('   ')).toBeNull()
    expect(normalizeCustomLabelValue(undefined)).toBeNull()
  })

  it('detects catchall value case-insensitively', () => {
    expect(isCatchallCustomLabel(CATCHALL_CUSTOM_LABEL)).toBe(true)
    expect(isCatchallCustomLabel('__CATCHALL__')).toBe(true)
    expect(isCatchallCustomLabel('paper towel holders')).toBe(false)
  })
})
