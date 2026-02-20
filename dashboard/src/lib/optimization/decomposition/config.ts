import type { AssignmentTier } from '@/lib/shopping-funnel/types'
import type { DecompositionVersions } from '@/lib/optimization/decomposition/types'

export const DECOMPOSITION_VERSIONS: DecompositionVersions = {
  parserVersion: 'decomp_v1',
  scoreVersion: 'score_v1',
  recommendationVersion: 'route_v1',
}

export const DEFAULT_STALE_THRESHOLD_HOURS = 24

export const DECOMPOSITION_BATCH_SIZE = 250

export const FEATURE_FLAG_DECOMPOSITION_PIPELINE =
  process.env.SHOPPING_DECOMPOSITION_PIPELINE_ENABLED === 'true'

export const BRAND_TOKENS = ['allied brass', 'alliedbrass', 'avd']

export const COMPETITOR_TOKENS = [
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

// Order defines precedence when multiple object candidates match.
export const PRODUCT_OBJECT_HINTS = [
  'toilet paper holder',
  'tp holder',
  'paper towel holder',
  'towel bar',
  'towel ring',
  'soap dispenser',
  'soap dish',
  'toothbrush holder',
  'grab bar',
  'glass shelf',
  'shower door pull',
  'shower squeegee',
  'robe hook',
  'mirror',
  'basket',
  'shelf',
]

export const MODIFIER_HINTS = [
  'wall mount',
  'wall mounted',
  'freestanding',
  'double',
  'single',
  'triple',
  'recessed',
  'reserve',
  'rollerless',
  'ada',
  'commercial',
  'solid brass',
  'heavy duty',
  'matte',
  'polished',
  'satin',
  'chrome',
  'nickel',
  'bronze',
]

export const USE_CASE_HINTS = [
  'bathroom',
  'kitchen',
  'guest',
  'powder room',
  'shower',
  'vanity',
  'commercial',
  'hotel',
  'rv',
]

export const HIGH_INTENT_TOKENS = [
  'buy',
  'shop',
  'best',
  'for sale',
  'near me',
  'wall mounted',
]

export const NEGATIVE_RISK_TOKENS = ['replacement part', 'repair', 'used', 'diy', 'free', 'cheap']

export const RECOMMENDATION_PRECEDENCE: Array<
  'branded' | 'competitor' | 'global_block' | 'funnel'
> = ['branded', 'competitor', 'global_block', 'funnel']

export const BASE_FUNNEL_CONFIDENCE = 0.55

export const BASE_INTENT_CONFIDENCE = 0.35

export const INTENT_CONFIDENCE_BONUS = {
  productObject: 0.2,
  modifierOrUseCase: 0.1,
  explicitBrandOrCompetitor: 0.2,
  ambiguityPenalty: 0.15,
}

export const BASELINE_TARGET_ROAS_BY_TIER: Record<Exclude<AssignmentTier, 'campaign_negative'>, number> = {
  high: 3.6,
  medium: 3.1,
  low: 2.6,
}
