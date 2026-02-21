import type { IntentClassification, IntentClass, IntentSubclass } from '@/lib/intent/types'

const BRAND_TOKENS = ['allied brass', 'alliedbrass', 'avd']

const COMPETITOR_TOKENS = [
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

const PRODUCT_OBJECT_HINTS = [
  'towel bar',
  'towel ring',
  'soap dish',
  'soap dispenser',
  'toothbrush holder',
  'toilet paper holder',
  'tp holder',
  'grab bar',
  'glass shelf',
  'robe hook',
  'mirror',
  'paper towel holder',
  'shower door pull',
  'shower squeegee',
  'basket',
  'shelf',
]

const MATERIAL_TOKENS = ['solid brass', 'brass', 'stainless', 'nickel', 'bronze', 'chrome']
const FINISH_TOKENS = ['matte', 'polished', 'satin', 'oil rubbed', 'antique', 'unlacquered']
const SIZE_TOKENS = ['inch', '"', 'in ', '24', '18', '16', '36', '48']

const MODIFIER_HINTS = [
  'wall mount',
  'double',
  'single',
  'triple',
  'recessed',
  'reserve',
  'rollerless',
  'ada',
  'commercial',
  'heavy duty',
]

const CATEGORY_HINTS = ['bathroom', 'bath', 'kitchen', 'vanity', 'shower', 'hotel', 'powder room']

const INFO_HINTS = ['how to', 'install', 'installation', 'care', 'clean', 'repair', 'replacement']

const RISK_POLICY_HINTS = ['free', 'cheap', 'used', 'diy', 'template', 'cad', 'drawing']

const MISMATCH_HINTS = ['plumbing service', 'contractor near me', 'job', 'employment']

function normalizeQuery(value: string): string {
  return value.toLowerCase().trim().replace(/\s+/g, ' ')
}

function collectMatches(term: string, candidates: string[]): string[] {
  return candidates.filter((candidate) => term.includes(candidate))
}

export function classifyIntent(searchTerm: string): IntentClassification {
  const normalizedQuery = normalizeQuery(searchTerm)
  const brandMatches = collectMatches(normalizedQuery, BRAND_TOKENS)
  const competitorMatches = collectMatches(normalizedQuery, COMPETITOR_TOKENS)
  const productMatches = collectMatches(normalizedQuery, PRODUCT_OBJECT_HINTS)
  const materialMatches = collectMatches(normalizedQuery, MATERIAL_TOKENS)
  const finishMatches = collectMatches(normalizedQuery, FINISH_TOKENS)
  const sizeMatches = collectMatches(normalizedQuery, SIZE_TOKENS)
  const modifierMatches = collectMatches(normalizedQuery, MODIFIER_HINTS)
  const categoryMatches = collectMatches(normalizedQuery, CATEGORY_HINTS)
  const infoMatches = collectMatches(normalizedQuery, INFO_HINTS)
  const policyRiskMatches = collectMatches(normalizedQuery, RISK_POLICY_HINTS)
  const mismatchMatches = collectMatches(normalizedQuery, MISMATCH_HINTS)

  const subclasses = new Set<IntentSubclass>()
  const reasonCodes = new Set<string>()
  const matchedTokens = new Set<string>()

  for (const token of [
    ...brandMatches,
    ...competitorMatches,
    ...productMatches,
    ...materialMatches,
    ...finishMatches,
    ...sizeMatches,
    ...modifierMatches,
    ...categoryMatches,
    ...infoMatches,
    ...policyRiskMatches,
    ...mismatchMatches,
  ]) {
    matchedTokens.add(token)
  }

  const isBranded = brandMatches.length > 0
  const isCompetitor = competitorMatches.length > 0
  const hasMismatchRisk = mismatchMatches.length > 0

  let intentClass: IntentClass = 'DISCOVERY_LOW'

  if (isBranded) {
    intentClass = 'BRAND_CORE'
    reasonCodes.add('brand_token_detected')
    subclasses.add('brand_only')
    if (productMatches.length > 0) subclasses.add('brand_with_category')
    if (/\b[a-z]{1,4}-?\d{1,4}\b/.test(normalizedQuery)) subclasses.add('brand_with_sku')
  } else if (isCompetitor) {
    intentClass = 'COMPETITOR'
    reasonCodes.add('competitor_token_detected')
    subclasses.add('competitor_product')
    if (normalizedQuery.includes('alternative') || normalizedQuery.includes('vs')) {
      subclasses.add('competitor_alternative')
    }
  } else if (hasMismatchRisk) {
    intentClass = 'MISMATCH'
    reasonCodes.add('mismatch_token_detected')
    subclasses.add('irrelevant_product')
  } else if (policyRiskMatches.length > 0) {
    intentClass = 'RISK_POLICY'
    reasonCodes.add('policy_sensitive_token_detected')
    subclasses.add('policy_sensitive')
  } else if (infoMatches.length > 0 && productMatches.length === 0) {
    intentClass = 'INFO_ASSIST'
    reasonCodes.add('informational_intent_detected')
    subclasses.add('how_to')
    subclasses.add('install_care')
  } else if (productMatches.length > 0 && (materialMatches.length > 0 || finishMatches.length > 0 || sizeMatches.length > 0)) {
    intentClass = 'PRODUCT_HIGH'
    reasonCodes.add('high_intent_product_signals')
    if (sizeMatches.length > 0) subclasses.add('product_with_size')
    if (materialMatches.length > 0) subclasses.add('product_with_material')
    if (finishMatches.length > 0) subclasses.add('product_with_finish')
  } else if (productMatches.length > 0 || modifierMatches.length > 0 || categoryMatches.length > 0) {
    intentClass = 'CATEGORY_MID'
    reasonCodes.add('category_intent_detected')
    subclasses.add('category_with_modifier')
    if (categoryMatches.length > 0) subclasses.add('room_fixture')
  } else {
    intentClass = 'DISCOVERY_LOW'
    reasonCodes.add('broad_discovery_default')
    subclasses.add('broad_problem')
  }

  return {
    normalizedQuery,
    intentClass,
    subclasses: Array.from(subclasses),
    reasonCodes: Array.from(reasonCodes),
    matchedTokens: Array.from(matchedTokens),
    isBranded,
    isCompetitor,
    hasMismatchRisk,
  }
}
