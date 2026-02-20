import { describe, expect, it } from 'vitest'
import {
  classifyCampaignPattern,
  classifyLandingPage,
  classifySourceMedium,
} from '@/lib/ga4/forensics'

describe('GA4 forensics classifiers', () => {
  it('classifies source/medium quality buckets', () => {
    expect(classifySourceMedium('(not set)')).toBe('not_set')
    expect(classifySourceMedium('(data not available)')).toBe('data_not_available')
    expect(classifySourceMedium('google / cpc')).toBe('valid')
  })

  it('classifies landing page quality buckets', () => {
    expect(classifyLandingPage('')).toBe('blank')
    expect(classifyLandingPage('   ')).toBe('blank')
    expect(classifyLandingPage('(not set)')).toBe('not_set')
    expect(classifyLandingPage('/collections/towel-bars')).toBe('valid')
  })

  it('classifies campaign naming patterns', () => {
    expect(classifyCampaignPattern('(not set)')).toBe('not_set')
    expect(classifyCampaignPattern('')).toBe('missing_name')
    expect(classifyCampaignPattern('AVD - Shopping - US - soap dishes & holders - HIGH')).toBe(
      'valid_named'
    )
    expect(classifyCampaignPattern('AVD - Shopping - BRANDED - US')).toBe('valid_named')
    expect(classifyCampaignPattern('Random campaign name')).toBe('nonstandard')
  })
})
