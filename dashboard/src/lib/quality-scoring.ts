/**
 * Content Quality Scoring Library
 *
 * TypeScript port of src/feedops/quality/scoring.py
 * Provides heuristic scoring for CTR/CVR/brand voice proxies.
 *
 * Title Zone Strategy:
 * - Mobile Zone (1-30 chars): Most critical - must contain keyword anchor
 * - Desktop Zone (31-70 chars): Critical - determines clicks, should have key specs
 * - Extended Zone (71-150 chars): High - expands query eligibility
 */

import { FINISH_LIST } from '@/lib/regeneration/prompts'

// ============================================================================
// Constants (ported from Python)
// ============================================================================

// Title zone boundaries (based on Google Shopping research)
const MOBILE_ZONE_END = 30
const DESKTOP_ZONE_END = 70
const MAX_TITLE_LENGTH = 150

// Regex patterns
const URL_RE = /https?:\/\//i
const CITATION_RE = /catalog_csv\.|\(\s*catalog_csv\.[^)]+\)/i
const ALL_CAPS_WORD_RE = /\b[A-Z]{4,}\b/
// Examples: "18-inch", "18 in", "1-1/2 in", '18"', "0.5 in"
const INCH_RE = /(\d+\s*-\s*\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?)\s*(?:-\s*)?(?:in\b|inch(?:es)?\b|")/gi
const WEIGHT_RE = /\b\d+(?:\.\d+)?\s*(?:lb|lbs|pound|pounds)\b/gi

// Product type phrases (40+ items)
const PRODUCT_TYPE_PHRASES = [
  'towel bar', 'towel rail', 'cabinet knob', 'grab bar',
  'toilet paper holder', 'toilet paper stand', 'toilet tissue', 'tissue stand',
  'towel ring', 'robe hook', 'guest towel', 'towel holder', 'towel shelf',
  'soap dish', 'soap dispenser', 'glass shelf', 'wood shelf',
  'wall mirror', 'vanity mirror', 'make-up mirror', 'makeup mirror',
  'shower door', 'shower curtain', 'paper towel', 'wall hook',
  'coat rack', 'coat stand', 'retractable', 'garment rod', 'squeegee',
  'vanity tray', 'tissue holder', 'toothbrush holder', 'tumbler holder',
  'tumbler toothbrush', 'basket', 'towel stand', 'towel valet',
  'cabinet pull', 'cabinet handle', 'drawer pull',
]

const MATERIAL_WORDS = [
  'brass', 'solid brass', 'stainless', 'steel', 'glass', 'wood', 'zinc',
]

const FUNCTIONAL_MODIFIERS = [
  'wall mount', 'wall-mounted', 'freestanding', 'free standing',
  'countertop', 'vanity top', 'concealed', 'ada', 'pivot', 'tilt',
  'tilting', 'retractable', 'quick', 'double-sided',
]

const PREMIUM_CUES = [
  'crafted', 'engineered', 'precision', 'enduring',
  'solid brass', 'lifetime warranty', 'limited lifetime warranty',
]

const OPENING_ENGAGEMENT_CUES = [
  // Outcome / action verbs
  'upgrade', 'add', 'refresh', 'protect', 'keep', 'organize',
  'maximize', 'transform', 'eliminate', 'create', 'ensure',
  'simplify', 'streamline', 'enjoy', 'free up', 'bring',
  'make', 'turn', 'feel',
  // Problem-first / question cues
  'need', 'tired of', 'looking for', 'want', 'struggling',
  'no more', 'stop', 'never', 'imagine', 'every morning',
  'when guests', 'running out of',
]

const BANNED_MARKETING = [
  'best', 'amazing', 'incredible', 'perfect', 'cheap', 'bargain',
  'free shipping', 'sale', 'finest', 'luxurious', 'exclusive',
  'exceptional', 'unparalleled', 'superior', 'exquisite', 'ultimate',
]

const TRUST_SIGNAL_PHRASES = [
  'lifetime warranty', 'limited lifetime warranty', 'virginia',
  'assembled in', '28 designer finishes', '28 finishes',
  'designer finishes', '42+ collection', '42 collection',
  'matching accessories', 'matching pieces',
]

const ATTRIBUTE_DENSITY_CUES = [
  // Product type cues
  'towel bar', 'towel rail', 'grab bar', 'toilet paper', 'tissue stand',
  'robe hook', 'glass shelf', 'soap dish', 'soap dispenser', 'towel ring',
  'cabinet knob', 'paper towel', 'wall mirror', 'makeup mirror', 'make-up mirror',
  'vanity mirror', 'coat rack', 'toothbrush holder', 'tumbler', 'towel holder',
  'towel shelf', 'wall hook', 'towel stand', 'towel valet', 'cabinet pull',
  'cabinet handle', 'drawer pull',
  // Material/mount cues
  'solid brass', 'brass construction', 'wall mount', 'wall-mounted',
  'freestanding', 'free standing', 'countertop', 'vanity top',
]

const ROOM_CONTEXT_PHRASES = [
  'bathroom', 'kitchen', 'bath ', 'powder room', 'laundry', 'mudroom',
]

const PRODUCT_TYPE_SYNONYM_GROUPS: Record<string, string[]> = {
  'towel bar': ['towel rack', 'towel holder', 'towel rail'],
  'grab bar': ['safety bar', 'support bar', 'bathroom grab bar'],
  'toilet paper holder': ['tissue holder', 'toilet roll holder', 'tp holder'],
  'robe hook': ['towel hook', 'bathroom hook', 'wall hook'],
  'glass shelf': ['bathroom shelf', 'wall shelf', 'floating shelf'],
  'paper towel holder': ['paper towel stand', 'kitchen towel holder'],
  'cabinet knob': ['drawer knob', 'cabinet pull'],
  'towel ring': ['towel loop', 'hand towel holder'],
  'soap dish': ['soap holder', 'soap tray'],
  'wall mirror': ['bath mirror', 'vanity mirror'],
}

// ============================================================================
// Types
// ============================================================================

export type Platform = 'google' | 'bing' | 'shopify'

export interface TitleZoneAnalysis {
  mobileZone: string
  desktopZone: string
  extendedZone: string
  hasProductTypeInMobile: boolean
  hasProductTypeInDesktop: boolean
  hasDimensionInMobile: boolean
  hasDimensionInDesktop: boolean
  hasMaterialInDesktop: boolean
  hasBrandAtEnd: boolean
  zoneScore: number
  zoneNotes: string[]
}

export interface TrustSignals {
  lifetimeWarranty: boolean
  virginia: boolean
  finishVariety: boolean
  matchingAccessories: boolean
  solidBrass: boolean
}

export interface QualityAnalysis {
  ctrProxy: number          // 0-10 (title score)
  cvrProxy: number          // 0-10 (description score)
  brandVoice: number        // 0-10
  readability: number       // 0-10
  compositeScore: number    // 0-100
  titleZoneAnalysis: TitleZoneAnalysis | null
  issues: string[]
  suggestions: string[]
  trustSignals: TrustSignals
}

// ============================================================================
// Utility Functions
// ============================================================================

function clamp0to10(value: number): number {
  return Math.max(0, Math.min(10, value))
}

function containsAny(text: string, phrases: string[]): boolean {
  const t = text.toLowerCase()
  return phrases.some(p => t.includes(p))
}

function countMatches(text: string, regex: RegExp): number {
  const matches = text.match(regex)
  return matches ? matches.length : 0
}

function countSynonymCoverage(textLower: string): number {
  for (const [canonical, synonyms] of Object.entries(PRODUCT_TYPE_SYNONYM_GROUPS)) {
    const allTerms = [canonical, ...synonyms]
    const hits = allTerms.filter(term => textLower.includes(term)).length
    if (hits >= 2) return hits
  }
  return 0
}

// ============================================================================
// Title Zone Analysis
// ============================================================================

export function analyzeTitleZones(title: string): TitleZoneAnalysis {
  const mobileZone = title.slice(0, MOBILE_ZONE_END)
  const desktopZone = title.slice(MOBILE_ZONE_END, DESKTOP_ZONE_END)
  const extendedZone = title.slice(DESKTOP_ZONE_END)
  const first70 = title.slice(0, DESKTOP_ZONE_END)

  const hasProductTypeInMobile = containsAny(mobileZone, PRODUCT_TYPE_PHRASES)
  const hasProductTypeInDesktop = containsAny(first70, PRODUCT_TYPE_PHRASES)
  const hasDimensionInMobile = INCH_RE.test(mobileZone)
  // Reset lastIndex for global regex
  INCH_RE.lastIndex = 0
  const hasDimensionInDesktop = INCH_RE.test(first70)
  INCH_RE.lastIndex = 0
  const hasMaterialInDesktop = containsAny(first70, MATERIAL_WORDS)

  // Brand placement check
  const lowerTitle = title.toLowerCase()
  const hasBrand = lowerTitle.includes('allied brass')
  let hasBrandAtEnd = false
  if (hasBrand) {
    const brandPos = lowerTitle.lastIndexOf('allied brass')
    hasBrandAtEnd = brandPos >= title.length - 20 || title.slice(Math.max(0, brandPos - 5), brandPos).includes(' | ')
  }

  // Calculate zone score
  let score = 0
  const notes: string[] = []

  // Product type in mobile zone (+3 points, critical)
  if (hasProductTypeInMobile) {
    score += 3
  } else if (hasProductTypeInDesktop) {
    score += 1
    notes.push('Product type not in mobile zone (first 30 chars)')
  } else {
    notes.push('Product type missing from first 70 chars')
  }

  // Dimension in desktop zone (+2 points)
  if (hasDimensionInMobile) {
    score += 2
  } else if (hasDimensionInDesktop) {
    score += 1
    notes.push('Dimension not in mobile zone (first 30 chars)')
  } else {
    notes.push('No dimension in first 70 chars')
  }

  // Material in desktop zone (+1 point)
  if (hasMaterialInDesktop) {
    score += 1
  } else {
    notes.push('Material keyword not in first 70 chars')
  }

  // Functional modifier bonus (+1 point)
  if (containsAny(first70, FUNCTIONAL_MODIFIERS)) {
    score += 1
  }

  // Brand placement (+2 points for correct end placement)
  if (hasBrandAtEnd) {
    score += 2
  } else if (hasBrand) {
    score += 1
    notes.push('Brand not at end of title (should be last segment)')
  } else {
    notes.push('Brand missing from title')
  }

  // Title length penalty
  if (title.length > MAX_TITLE_LENGTH) {
    score -= 1
    notes.push(`Title exceeds ${MAX_TITLE_LENGTH} characters`)
  } else if (title.length < 50) {
    notes.push('Title under 50 characters - may miss search coverage')
  }

  return {
    mobileZone,
    desktopZone,
    extendedZone,
    hasProductTypeInMobile,
    hasProductTypeInDesktop,
    hasDimensionInMobile,
    hasDimensionInDesktop,
    hasMaterialInDesktop,
    hasBrandAtEnd,
    zoneScore: clamp0to10(score),
    zoneNotes: notes,
  }
}

// ============================================================================
// Title Scoring (CTR Proxy)
// ============================================================================

export function scoreTitleCtr(
  title: string,
  platform: Platform = 'google'
): { score: number; notes: string[]; zoneAnalysis: TitleZoneAnalysis | null } {
  const notes: string[] = []
  let score = 0

  // Hard failures - return immediately
  if (CITATION_RE.test(title)) {
    notes.push('Citation leakage detected in title')
    return { score: 0, notes, zoneAnalysis: null }
  }
  if (URL_RE.test(title)) {
    notes.push('URL detected in title')
    return { score: 0, notes, zoneAnalysis: null }
  }

  // Perform zone analysis
  const zoneAnalysis = analyzeTitleZones(title)
  notes.push(...zoneAnalysis.zoneNotes)

  const length = title.length
  if (length > MAX_TITLE_LENGTH) {
    notes.push(`Title exceeds ${MAX_TITLE_LENGTH} characters`)
  }
  if (length >= 50 && length <= MAX_TITLE_LENGTH) {
    score += 1
  }
  if (length >= 70 && length <= MAX_TITLE_LENGTH) {
    score += 1
  }

  // Google/Bing minimum title length penalty
  if ((platform === 'google' || platform === 'bing') && length < 60) {
    notes.push(`Title under 60 chars (${length}) -- missing search coverage`)
    score -= 1
  }

  // Product type scoring - zone-aware
  if (zoneAnalysis.hasProductTypeInMobile) {
    score += 2
  } else if (zoneAnalysis.hasProductTypeInDesktop) {
    score += 1
  }

  // Dimension scoring - zone-aware
  if (zoneAnalysis.hasDimensionInMobile) {
    score += 2
  } else if (zoneAnalysis.hasDimensionInDesktop) {
    score += 1
  }

  // Material scoring
  if (zoneAnalysis.hasMaterialInDesktop) {
    score += 1
  }

  // Functional modifier bonus
  const first70 = title.slice(0, DESKTOP_ZONE_END)
  if (containsAny(first70, FUNCTIONAL_MODIFIERS)) {
    score += 1
  }

  // Brand scoring
  if (zoneAnalysis.hasBrandAtEnd) {
    score += 1
  } else if (title.toLowerCase().includes('allied brass')) {
    score += 1
  }

  // Penalties
  if (ALL_CAPS_WORD_RE.test(title)) {
    notes.push('ALL CAPS word detected')
    score -= 1
  }

  if (containsAny(title, BANNED_MARKETING)) {
    notes.push('Promotional/budget language detected')
    score -= 2
  }

  return { score: clamp0to10(score), notes, zoneAnalysis }
}

// ============================================================================
// Description Scoring (CVR Proxy)
// ============================================================================

export function scoreDescriptionCvr(
  description: string,
  platform: Platform = 'google'
): { score: number; notes: string[] } {
  const notes: string[] = []
  let score = 0

  // Hard failures
  if (CITATION_RE.test(description)) {
    notes.push('Citation leakage detected in description')
    return { score: 0, notes }
  }
  if (URL_RE.test(description)) {
    notes.push('URL detected in description')
    return { score: 0, notes }
  }

  const textLen = description.length

  // Platform-specific length scoring
  if (platform === 'google') {
    if (textLen >= 600 && textLen <= 800) {
      score += 2
    } else if (textLen >= 500 && textLen <= 900) {
      score += 1
      notes.push('Description outside ideal 600-800 character target for Google')
    } else if (textLen >= 300) {
      notes.push('Description under 500 characters')
    } else {
      notes.push('Description under 300 characters')
    }
  } else if (platform === 'bing') {
    if (textLen >= 700 && textLen <= 1000) {
      score += 2
    } else if (textLen >= 600 && textLen <= 1100) {
      score += 1
      notes.push('Description outside ideal 700-1000 character target for Bing')
    } else if (textLen >= 300) {
      notes.push('Description under 600 characters for Bing')
    } else {
      notes.push('Description under 300 characters')
    }
  } else {
    // Shopify
    if (textLen >= 600 && textLen <= 1000) {
      score += 2
    } else if (textLen >= 500) {
      score += 1
      notes.push('Description outside ideal 600-1000 character target range')
    } else if (textLen >= 300) {
      notes.push('Description under 500 characters')
    } else {
      notes.push('Description under 300 characters')
    }
  }

  const opening = description.slice(0, 160).toLowerCase()

  if (platform === 'google' || platform === 'bing') {
    // Feed fuel: reward attribute density in first 150 chars
    const first150 = description.slice(0, 150).toLowerCase()
    const attrHits = ATTRIBUTE_DENSITY_CUES.filter(cue => first150.includes(cue)).length
    INCH_RE.lastIndex = 0
    const hasDimInOpening = INCH_RE.test(description.slice(0, 150))

    if (attrHits >= 2 || (attrHits >= 1 && hasDimInOpening)) {
      score += 2
    } else if (attrHits >= 1) {
      score += 1
      notes.push('Opening has few searchable attributes (feed fuel)')
    } else {
      notes.push('Opening lacks searchable attributes -- should lead with product type + specs')
    }
  } else {
    // Shopify: reward engagement hooks
    if (containsAny(opening, OPENING_ENGAGEMENT_CUES)) {
      score += 2
    } else {
      notes.push('Opening may lack engagement hook (no problem/outcome cue detected)')
    }
  }

  // Specs presence: at least 3 numeric/measurement tokens
  INCH_RE.lastIndex = 0
  const inchMatches = countMatches(description, INCH_RE)
  const weightMatches = countMatches(description, WEIGHT_RE)
  const measurements = inchMatches + weightMatches

  if (measurements >= 3) {
    score += 2
  } else {
    notes.push('Few measurable specs detected')
  }

  // Plain-text structure cues for Shopify
  if (platform === 'shopify') {
    const bulletLines = description.split('\n').filter(line => {
      const trimmed = line.trim()
      return trimmed.startsWith('-') || trimmed.startsWith('•')
    })
    if (bulletLines.length >= 3) {
      score += 1
    } else {
      notes.push('Missing structured highlights bullets')
    }

    if (/\b(specs?|specifications)\b/i.test(description) && measurements >= 3) {
      score += 1
    } else {
      notes.push('Missing specs section')
    }
  }

  // Trust signal scoring - platform-aware
  const textLower = description.toLowerCase()
  const trustHits = TRUST_SIGNAL_PHRASES.filter(phrase => textLower.includes(phrase)).length

  if (platform === 'shopify') {
    const first200 = description.slice(0, 200).toLowerCase()
    const earlyTrustHits = TRUST_SIGNAL_PHRASES.filter(phrase => first200.includes(phrase)).length
    score += Math.min(3, earlyTrustHits * 2)
    if (earlyTrustHits === 0 && trustHits === 0) {
      notes.push('No trust signals found (warranty, Virginia, finishes)')
    }
  } else {
    if (textLower.includes('lifetime warranty') || textLower.includes('solid brass')) {
      score += 1
    }
  }

  // Synonym coverage for Google/Bing
  if (platform === 'google' || platform === 'bing') {
    const synonymHits = countSynonymCoverage(textLower)
    if (synonymHits >= 2) {
      score += 1
    }

    if (containsAny(textLower, ROOM_CONTEXT_PHRASES)) {
      score += 1
    }
  }

  // Installation mention
  if (textLower.includes('installation') || textLower.includes('mounting')) {
    score += 1
  }

  // Penalties
  if (description.includes('!')) {
    notes.push('Exclamation point detected')
    score -= 1
  }
  if (containsAny(description, BANNED_MARKETING)) {
    notes.push('Promotional/budget language detected')
    score -= 2
  }

  return { score: clamp0to10(score), notes }
}

// ============================================================================
// Brand Voice Scoring
// ============================================================================

export function scoreBrandVoice(text: string): { score: number; notes: string[] } {
  const notes: string[] = []
  let score = 5 // Neutral baseline

  const t = text.toLowerCase()
  const cueHits = PREMIUM_CUES.filter(cue => t.includes(cue)).length

  // Diminishing returns
  if (cueHits >= 1) {
    score += Math.min(2, cueHits)
  }
  if (cueHits >= 3) {
    score += Math.min(2, cueHits - 2)
  }

  // Reward natural voice
  const genericFillers = ['this product', 'this item', 'this piece', 'our product']
  if (!containsAny(t, genericFillers)) {
    score += 1
  }

  // Penalties
  if (ALL_CAPS_WORD_RE.test(text)) {
    notes.push('ALL CAPS word detected')
    score -= 2
  }
  if (text.includes('!')) {
    notes.push('Exclamation point detected')
    score -= 1
  }
  if (containsAny(text, BANNED_MARKETING)) {
    notes.push('Promotional/budget language detected')
    score -= 3
  }

  return { score: clamp0to10(score), notes }
}

// ============================================================================
// Readability Scoring
// ============================================================================

export function scoreReadability(
  text: string,
  platform: Platform = 'google'
): { score: number; notes: string[] } {
  const notes: string[] = []

  // Only score Google/Bing - Shopify is already human-focused
  if (platform !== 'google' && platform !== 'bing') {
    return { score: 10, notes }
  }

  let score = 10 // Start at max

  if (!text || text.length < 50) {
    return { score, notes }
  }

  // Split into sentences
  const sentences = text.split(/(?<!\d)\.(?!\d)\s*/).filter(s => s.trim())

  // Penalty: Dimension dump in opening
  const dimensionDumpPattern = /^(?:Finished in \w+[\w\s]*,\s*)?[^,]+,\s*\d+(?:\.\d+)?\s*(?:in|inch)/i
  if (dimensionDumpPattern.test(text)) {
    score -= 3
    notes.push('Opens with dimension dump -- needs natural prose')
  }

  // Penalty: Keyword list at end
  const keywordListPattern = /(?:fits|matches|complements|coordinates with|works with)\s+(?:\w+\s+)?(?:bathroom|bath|kitchen)\s+(?:hardware|accessories|fixtures)(?:\s*,\s*(?:\w+\s+)?(?:bathroom|bath|kitchen)\s+(?:hardware|accessories|fixtures)){1,}\.?\s*$/i
  if (keywordListPattern.test(text)) {
    score -= 2
    notes.push('Ends with keyword list -- integrate naturally')
  }

  // Penalty: Very long sentences (>150 chars)
  const veryLong = sentences.filter(s => s.length > 150)
  if (veryLong.length > 0) {
    const penalty = Math.min(2, veryLong.length)
    score -= penalty
    notes.push(`${veryLong.length} sentence(s) over 150 chars`)
  }

  // Penalty: Ends with brand-only fragment
  if (/\.\s*Allied Brass\.?\s*$/.test(text)) {
    score -= 1
    notes.push('Ends with brand-only fragment')
  }

  return { score: clamp0to10(score), notes }
}

// ============================================================================
// Trust Signals Detection
// ============================================================================

export function detectTrustSignals(description: string): TrustSignals {
  const lower = description.toLowerCase()

  return {
    lifetimeWarranty: lower.includes('lifetime warranty') || lower.includes('limited lifetime warranty'),
    virginia: lower.includes('virginia') || lower.includes('assembled in'),
    finishVariety: lower.includes('28 finishes') || lower.includes('28 designer finishes') || lower.includes('designer finishes'),
    matchingAccessories: lower.includes('matching accessories') || lower.includes('matching pieces') || lower.includes('coordinate'),
    solidBrass: lower.includes('solid brass') || lower.includes('brass construction'),
  }
}

// ============================================================================
// Main Analysis Function
// ============================================================================

export function analyzeContent(
  title: string,
  description: string,
  platform: Platform
): QualityAnalysis {
  // Score individual dimensions
  const titleResult = scoreTitleCtr(title, platform)
  const descResult = scoreDescriptionCvr(description, platform)
  const combinedText = `${title}\n${description}`
  const voiceResult = scoreBrandVoice(combinedText)
  const readabilityResult = scoreReadability(description, platform)

  // Collect all issues and deduplicate
  const allNotes = [
    ...titleResult.notes,
    ...descResult.notes,
    ...voiceResult.notes,
    ...readabilityResult.notes,
  ]
  const uniqueNotes = Array.from(new Set(allNotes))

  // Separate issues from suggestions
  const issues = uniqueNotes.filter(n =>
    n.includes('detected') ||
    n.includes('leakage') ||
    n.includes('exceeds') ||
    n.includes('missing') ||
    n.includes('under')
  )

  const suggestions = uniqueNotes.filter(n =>
    n.includes('should') ||
    n.includes('may') ||
    n.includes('needs') ||
    n.includes('lacks')
  )

  // Calculate composite: (ctr + cvr + voice + readability) / 40 * 100
  let compositeScore = Math.round(
    (titleResult.score + descResult.score + voiceResult.score + readabilityResult.score) / 40 * 100
  )

  // ==================== HARD VIOLATION PENALTIES ====================
  // These catch platform-specific rule violations that individual scorers miss.

  // Shopify title must not contain "Allied Brass"
  if (platform === 'shopify' && title.toLowerCase().includes('allied brass')) {
    compositeScore = Math.max(0, compositeScore - 30)
    issues.push('Shopify title contains "Allied Brass" (must be removed)')
  }

  // Shopify title must not contain specific finish names
  if (platform === 'shopify') {
    for (const finish of FINISH_LIST) {
      if (title.includes(finish)) {
        compositeScore = Math.max(0, compositeScore - 30)
        issues.push(`Shopify title contains finish name "${finish}" (must be removed)`)
        break
      }
    }
  }

  // Title too short to be useful
  if (title.length < 30) {
    compositeScore = 0
    issues.push(`Title too short (${title.length} chars, minimum 30)`)
  }

  // Title is just brand name or SKU
  if (title.trim().toLowerCase() === 'allied brass' || /^[A-Z0-9\-/]+$/.test(title.trim())) {
    compositeScore = 0
    issues.push('Title is just a brand name or SKU, not a descriptive product title')
  }

  // Google/Bing base description with hardcoded finish name (should use placeholder)
  if (platform !== 'shopify' && description) {
    for (const finish of FINISH_LIST) {
      if (description.includes(finish) && !description.includes('{FINISH_')) {
        compositeScore = Math.max(0, compositeScore - 20)
        issues.push(`Description contains hardcoded finish name "${finish}" (should use {FINISH_SENTENCE} placeholder)`)
        break
      }
    }
  }

  return {
    ctrProxy: titleResult.score,
    cvrProxy: descResult.score,
    brandVoice: voiceResult.score,
    readability: readabilityResult.score,
    compositeScore,
    titleZoneAnalysis: titleResult.zoneAnalysis,
    issues,
    suggestions,
    trustSignals: detectTrustSignals(description),
  }
}

// ============================================================================
// 6-Dimension Analysis (for ContentQualityCard)
// ============================================================================

export interface SixDimensionScore {
  specificity: number          // 0-10: Concrete claims
  benefitCoverage: number      // 0-10: Benefits in hook
  keywordInclusion: number     // 0-10: Search term coverage
  formatAdherence: number      // 0-10: Within limits
  brandVoice: number           // 0-10: Premium tone
  factualAccuracy: number      // 0-10: All claims verified
  overallScore: number         // 0-100: Average of 6 dimensions
  status: 'ready' | 'minor' | 'major'  // ≥80% ready, 70-79% minor, <70% major
  lowestDimension: {
    name: string
    score: number
    label: string
  }
}

/**
 * Maps existing quality scores to 6 AGENTS.md dimensions for ContentQualityCard
 *
 * Mapping strategy:
 * 1. Specificity ← (cvrProxy × 0.6) + (brandVoice × 0.4)
 * 2. Benefit Coverage ← cvrProxy × 1.0
 * 3. Keyword Inclusion ← ctrProxy × 1.0
 * 4. Format Adherence ← length compliance checks
 * 5. Brand Voice ← brandVoice (direct)
 * 6. Factual Accuracy ← 10 - (issues.length × 2)
 */
export function analyzeSixDimensions(
  title: string,
  description: string,
  platform: Platform
): SixDimensionScore {
  const analysis = analyzeContent(title, description, platform)

  // 1. Specificity: Concrete claims (favor description quality + brand voice)
  const specificity = clamp0to10(
    (analysis.cvrProxy * 0.6) + (analysis.brandVoice * 0.4)
  )

  // 2. Benefit Coverage: Benefits in hook (use description score as proxy)
  const benefitCoverage = analysis.cvrProxy

  // 3. Keyword Inclusion: Search term coverage (use title score as proxy)
  const keywordInclusion = analysis.ctrProxy

  // 4. Format Adherence: Within limits (check length compliance)
  let formatAdherence = 10

  // Title length check
  if (title.length > MAX_TITLE_LENGTH) {
    formatAdherence -= 3
  } else if (title.length < 50) {
    formatAdherence -= 2
  }

  // Description length check (platform-specific)
  if (platform === 'google') {
    if (description.length < 500 || description.length > 900) {
      formatAdherence -= 2
    }
  } else if (platform === 'bing') {
    if (description.length < 600 || description.length > 1100) {
      formatAdherence -= 2
    }
  } else {
    // Shopify
    if (description.length < 500 || description.length > 1000) {
      formatAdherence -= 2
    }
  }

  formatAdherence = clamp0to10(formatAdherence)

  // 5. Brand Voice: Premium tone (direct from existing score)
  const brandVoice = analysis.brandVoice

  // 6. Factual Accuracy: All claims verified (penalize based on issues)
  const factualIssues = analysis.issues.filter(issue =>
    issue.includes('detected') ||
    issue.includes('leakage') ||
    issue.includes('exceeds') ||
    issue.includes('ALL CAPS') ||
    issue.includes('Promotional') ||
    issue.includes('URL')
  ).length

  const factualAccuracy = clamp0to10(10 - (factualIssues * 2))

  // Calculate overall score (average of 6 dimensions, scaled to 0-100)
  const dimensionAvg = (
    specificity +
    benefitCoverage +
    keywordInclusion +
    formatAdherence +
    brandVoice +
    factualAccuracy
  ) / 6

  const overallScore = Math.round(dimensionAvg * 10)

  // Determine status
  let status: 'ready' | 'minor' | 'major'
  if (overallScore >= 80) {
    status = 'ready'
  } else if (overallScore >= 70) {
    status = 'minor'
  } else {
    status = 'major'
  }

  // Find lowest dimension for collapsed state
  const dimensions = [
    { name: 'specificity', score: specificity, label: 'Specificity' },
    { name: 'benefitCoverage', score: benefitCoverage, label: 'Benefit Coverage' },
    { name: 'keywordInclusion', score: keywordInclusion, label: 'Keyword Inclusion' },
    { name: 'formatAdherence', score: formatAdherence, label: 'Format Adherence' },
    { name: 'brandVoice', score: brandVoice, label: 'Brand Voice' },
    { name: 'factualAccuracy', score: factualAccuracy, label: 'Factual Accuracy' },
  ]

  const lowestDimension = dimensions.reduce((min, dim) =>
    dim.score < min.score ? dim : min
  )

  return {
    specificity,
    benefitCoverage,
    keywordInclusion,
    formatAdherence,
    brandVoice,
    factualAccuracy,
    overallScore,
    status,
    lowestDimension,
  }
}
