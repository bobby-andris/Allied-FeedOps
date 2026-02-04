/**
 * Pattern extraction for competitor intelligence
 * Extracts title_structure, keyword, benefit, trust_signal, and competitor_brand patterns
 */

import type { CompetitorPatternType } from '@/lib/supabase/types'

export interface ExtractedPattern {
  category: string
  pattern_type: CompetitorPatternType
  pattern_value: string
  frequency: number
  avg_position: number | null
  sources: string[]
  example_titles: string[]
}

interface ListingData {
  title: string
  description?: string | null
  source: string
  position?: number | null
  domain?: string | null
  brand?: string | null
}

// Known competitor brands to track
const KNOWN_BRANDS = [
  'signature hardware',
  'kingston brass',
  'moen',
  'delta',
  'kohler',
  'pfister',
  'american standard',
  'brizo',
  'hansgrohe',
  'grohe',
  'rohl',
  'newport brass',
  'california faucets',
  'gatco',
  'elements of design',
]

// Title structure patterns
const TITLE_STRUCTURE_PATTERNS = [
  { pattern: /^\d+/, name: 'dimension_first', label: 'Leads with dimension' },
  { pattern: /\b(modern|traditional|contemporary|classic|transitional|vintage|rustic)\b/i, name: 'style_included', label: 'Includes style' },
  { pattern: /\b(brass|stainless|chrome|nickel|bronze|gold|matte|polished|satin)\b/i, name: 'finish_prominent', label: 'Finish prominent' },
  { pattern: /\b(wall[\s-]*mount|freestanding|countertop|ceiling[\s-]*mount|recessed)\b/i, name: 'mount_type', label: 'Mount type specified' },
  { pattern: /\b(\d+["']?\s*(?:inch|in\b|"))/i, name: 'size_specified', label: 'Size specified' },
  { pattern: /\bset\s+of\s+\d+|\d+[\s-]*(?:pack|piece|pc)\b/i, name: 'quantity_mentioned', label: 'Quantity/set mentioned' },
]

// Benefit patterns
const BENEFIT_PATTERNS = [
  { pattern: /easy\s*(?:to\s*)?install/i, name: 'easy_installation', label: 'Easy installation' },
  { pattern: /rust[\s-]*(?:proof|resistant|free)/i, name: 'rust_resistant', label: 'Rust resistant' },
  { pattern: /ada[\s-]*compliant/i, name: 'ada_compliant', label: 'ADA compliant' },
  { pattern: /heavy[\s-]*duty/i, name: 'heavy_duty', label: 'Heavy duty' },
  { pattern: /quick[\s-]*release/i, name: 'quick_release', label: 'Quick release' },
  { pattern: /no[\s-]*drill/i, name: 'no_drill', label: 'No drill' },
  { pattern: /waterproof/i, name: 'waterproof', label: 'Waterproof' },
  { pattern: /anti[\s-]*slip|non[\s-]*slip/i, name: 'anti_slip', label: 'Anti-slip' },
  { pattern: /space[\s-]*saving/i, name: 'space_saving', label: 'Space saving' },
  { pattern: /adjustable/i, name: 'adjustable', label: 'Adjustable' },
]

// Trust signal patterns
const TRUST_SIGNAL_PATTERNS = [
  { pattern: /warranty/i, name: 'warranty_mentioned', label: 'Warranty mentioned' },
  { pattern: /made\s+in\s+(?:usa|america|the\s+us)/i, name: 'made_in_usa', label: 'Made in USA' },
  { pattern: /solid\s*(?:brass|metal|steel|stainless)/i, name: 'solid_material', label: 'Solid material callout' },
  { pattern: /\d+\s*year/i, name: 'year_guarantee', label: 'Year guarantee' },
  { pattern: /lifetime/i, name: 'lifetime_guarantee', label: 'Lifetime guarantee' },
  { pattern: /commercial[\s-]*grade/i, name: 'commercial_grade', label: 'Commercial grade' },
  { pattern: /premium|high[\s-]*quality/i, name: 'premium_quality', label: 'Premium quality claim' },
]

// Stop words for keyword extraction
const STOP_WORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
  'with', 'by', 'from', 'this', 'that', 'these', 'those', 'is', 'are', 'was',
  'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
  'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
  'your', 'our', 'its', 'all', 'any', 'each', 'every', 'both', 'few', 'more',
  'most', 'other', 'some', 'such', 'than', 'too', 'very', 'just', 'also',
  'now', 'only', 'not', 'new', 'get', 'set', 'best', 'top', 'great', 'good',
])

/**
 * Extract patterns from a list of competitor listings
 */
export function extractPatterns(
  listings: ListingData[],
  category: string
): ExtractedPattern[] {
  const patternMap = new Map<string, ExtractedPattern>()

  for (const listing of listings) {
    const text = `${listing.title} ${listing.description || ''}`
    const titleLower = listing.title.toLowerCase()
    const textLower = text.toLowerCase()

    // Extract title structure patterns
    for (const { pattern, name } of TITLE_STRUCTURE_PATTERNS) {
      if (pattern.test(listing.title)) {
        addOrUpdatePattern(patternMap, {
          category,
          pattern_type: 'title_structure',
          pattern_value: name,
          position: listing.position ?? null,
          source: listing.source,
          exampleTitle: listing.title,
        })
      }
    }

    // Extract benefit patterns
    for (const { pattern, name } of BENEFIT_PATTERNS) {
      if (pattern.test(text)) {
        addOrUpdatePattern(patternMap, {
          category,
          pattern_type: 'benefit',
          pattern_value: name,
          position: listing.position ?? null,
          source: listing.source,
          exampleTitle: listing.title,
        })
      }
    }

    // Extract trust signal patterns
    for (const { pattern, name } of TRUST_SIGNAL_PATTERNS) {
      if (pattern.test(text)) {
        addOrUpdatePattern(patternMap, {
          category,
          pattern_type: 'trust_signal',
          pattern_value: name,
          position: listing.position ?? null,
          source: listing.source,
          exampleTitle: listing.title,
        })
      }
    }

    // Extract competitor brands
    for (const brand of KNOWN_BRANDS) {
      if (textLower.includes(brand) || (listing.brand && listing.brand.toLowerCase().includes(brand))) {
        addOrUpdatePattern(patternMap, {
          category,
          pattern_type: 'competitor_brand',
          pattern_value: brand.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
          position: listing.position ?? null,
          source: listing.source,
          exampleTitle: listing.title,
        })
      }
    }

    // Also track domain as competitor if from SERP
    if (listing.domain && listing.domain !== 'amazon.com' && listing.domain !== 'wayfair.com' && listing.domain !== 'homedepot.com') {
      addOrUpdatePattern(patternMap, {
        category,
        pattern_type: 'competitor_brand',
        pattern_value: listing.domain,
        position: listing.position ?? null,
        source: listing.source,
        exampleTitle: listing.title,
      })
    }

    // Extract keywords
    const keywords = extractTopKeywords(titleLower)
    for (const kw of keywords) {
      addOrUpdatePattern(patternMap, {
        category,
        pattern_type: 'keyword',
        pattern_value: kw,
        position: listing.position ?? null,
        source: listing.source,
        exampleTitle: listing.title,
      })
    }
  }

  // Filter patterns that appear at least twice
  return Array.from(patternMap.values())
    .filter(p => p.frequency >= 2)
    .sort((a, b) => b.frequency - a.frequency)
}

function addOrUpdatePattern(
  map: Map<string, ExtractedPattern>,
  data: {
    category: string
    pattern_type: CompetitorPatternType
    pattern_value: string
    position: number | null
    source: string
    exampleTitle: string
  }
) {
  const key = `${data.category}:${data.pattern_type}:${data.pattern_value}`
  const existing = map.get(key)

  if (existing) {
    existing.frequency++
    // Update average position
    if (data.position !== null) {
      if (existing.avg_position !== null) {
        existing.avg_position =
          (existing.avg_position * (existing.frequency - 1) + data.position) /
          existing.frequency
      } else {
        existing.avg_position = data.position
      }
    }
    // Track unique sources
    if (!existing.sources.includes(data.source)) {
      existing.sources.push(data.source)
    }
    // Add example titles (max 3)
    if (existing.example_titles.length < 3 && !existing.example_titles.includes(data.exampleTitle)) {
      existing.example_titles.push(data.exampleTitle)
    }
  } else {
    map.set(key, {
      category: data.category,
      pattern_type: data.pattern_type,
      pattern_value: data.pattern_value,
      frequency: 1,
      avg_position: data.position,
      sources: [data.source],
      example_titles: [data.exampleTitle],
    })
  }
}

function extractTopKeywords(text: string): string[] {
  const words = text
    .replace(/[^a-z0-9\s-]/g, '')
    .split(/\s+/)
    .filter(word => word.length > 3 && !STOP_WORDS.has(word))

  // Count frequency
  const counts = new Map<string, number>()
  for (const word of words) {
    counts.set(word, (counts.get(word) || 0) + 1)
  }

  // Return top 5 by frequency
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([word]) => word)
}

/**
 * Extract domain from a URL
 */
export function extractDomain(url: string): string | null {
  try {
    const parsed = new URL(url)
    return parsed.hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

/**
 * Normalize Apify data from different actors to a common format
 */
export function normalizeApifyData(
  source: string,
  rawData: Record<string, unknown>[]
): ListingData[] {
  switch (source) {
    case 'google':
      return rawData.map((item, index) => ({
        title: String(item.title || ''),
        description: item.description ? String(item.description) : null,
        source: 'google',
        position: typeof item.position === 'number' ? item.position : index + 1,
        domain: item.url ? extractDomain(String(item.url)) : null,
      }))

    case 'amazon':
      return rawData.map((item, index) => ({
        title: String(item.title || item.name || ''),
        description: item.description ? String(item.description) : (item.productDescription ? String(item.productDescription) : null),
        source: 'amazon',
        position: typeof item.position === 'number' ? item.position : index + 1,
        domain: 'amazon.com',
        brand: item.brand ? String(item.brand) : null,
      }))

    case 'wayfair':
      return rawData.map((item, index) => ({
        title: String(item.name || item.title || ''),
        description: item.description ? String(item.description) : null,
        source: 'wayfair',
        position: typeof item.position === 'number' ? item.position : index + 1,
        domain: 'wayfair.com',
        brand: item.manufacturer ? String(item.manufacturer) : (item.brand ? String(item.brand) : null),
      }))

    case 'homedepot':
      return rawData.map((item, index) => ({
        title: String(item.title || item.productName || item.name || ''),
        description: item.description ? String(item.description) : (item.shortDescription ? String(item.shortDescription) : null),
        source: 'homedepot',
        position: typeof item.position === 'number' ? item.position : index + 1,
        domain: 'homedepot.com',
        brand: item.brand ? String(item.brand) : (item.brandName ? String(item.brandName) : null),
      }))

    default:
      return rawData.map((item, index) => ({
        title: String(item.title || item.name || ''),
        description: item.description ? String(item.description) : null,
        source,
        position: index + 1,
      }))
  }
}

/**
 * Get human-readable label for a pattern value
 */
export function getPatternLabel(patternType: string, patternValue: string): string {
  // Check title structure patterns
  const titleStructure = TITLE_STRUCTURE_PATTERNS.find(p => p.name === patternValue)
  if (titleStructure) return titleStructure.label

  // Check benefit patterns
  const benefit = BENEFIT_PATTERNS.find(p => p.name === patternValue)
  if (benefit) return benefit.label

  // Check trust signal patterns
  const trustSignal = TRUST_SIGNAL_PATTERNS.find(p => p.name === patternValue)
  if (trustSignal) return trustSignal.label

  // Default: capitalize and format
  return patternValue
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/**
 * Check if our content has a specific pattern
 */
export function checkIfContentHasPattern(
  content: { title: string | null; description: string | null },
  patternType: CompetitorPatternType,
  patternValue: string
): boolean {
  const text = `${content.title || ''} ${content.description || ''}`
  const textLower = text.toLowerCase()

  switch (patternType) {
    case 'title_structure': {
      const pattern = TITLE_STRUCTURE_PATTERNS.find(p => p.name === patternValue)
      return pattern ? pattern.pattern.test(content.title || '') : false
    }
    case 'benefit': {
      const pattern = BENEFIT_PATTERNS.find(p => p.name === patternValue)
      return pattern ? pattern.pattern.test(text) : false
    }
    case 'trust_signal': {
      const pattern = TRUST_SIGNAL_PATTERNS.find(p => p.name === patternValue)
      return pattern ? pattern.pattern.test(text) : false
    }
    case 'keyword':
      return textLower.includes(patternValue.toLowerCase())
    case 'competitor_brand':
      // Allied Brass shouldn't match competitor brands
      return false
    default:
      return false
  }
}
