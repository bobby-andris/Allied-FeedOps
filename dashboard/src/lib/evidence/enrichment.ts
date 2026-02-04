/**
 * On-the-fly product enrichment for design-intent detection
 * Ported from Python: src/feedops/pipeline/enrichment.py
 */

import type { ProductCatalogRow, DesignStyleContext, FunctionalFeature } from './types'

// Design style patterns for classification
const DESIGN_STYLE_PATTERNS: Record<
  string,
  { signals: string[]; tone: string; keywords: string[] }
> = {
  traditional: {
    signals: [
      'traditional',
      'classic',
      'ornate',
      'regal',
      'victorian',
      'heritage',
      'engraved',
      'floral',
      'carolina',
      'essex',
      'monte carlo',
      'retro',
    ],
    tone: 'elegant, timeless, refined, luxurious',
    keywords: ['traditional bathroom hardware', 'classic bath accessories', 'heritage bathroom fixtures'],
  },
  modern: {
    signals: [
      'modern',
      'contemporary',
      'minimalist',
      'sleek',
      'cube',
      'geometric',
      'argo',
      'dayton',
      'fresno',
      'montero',
      'venus',
      'southbeach',
      'tribecca',
      'remi',
    ],
    tone: 'crisp, clean, sophisticated, architectural',
    keywords: ['modern bathroom hardware', 'contemporary bath accessories', 'minimalist bathroom fixtures'],
  },
  transitional: {
    signals: [
      'transitional',
      'blend',
      'versatile',
      'dottingham',
      'waverly',
      'mercury',
      'que new',
      'continental',
      'soho',
      'washington square',
      'astor place',
    ],
    tone: 'balanced, versatile, sophisticated, adaptable',
    keywords: ['transitional bathroom hardware', 'versatile bath accessories'],
  },
  industrial: {
    signals: ['industrial', 'pipeline', 'pipe', 'exposed', 'loft', 'shadwell', 'urban'],
    tone: 'bold, authentic, urban, raw',
    keywords: ['industrial bathroom hardware', 'pipe-style accessories', 'loft bathroom fixtures'],
  },
  coastal: {
    signals: ['beach', 'coastal', 'nautical', 'marine', 'pacific', 'sag harbor', 'malibu'],
    tone: 'fresh, light, relaxed, breezy',
    keywords: ['coastal bathroom accessories', 'beach house hardware', 'maritime bath fixtures'],
  },
  designer: {
    signals: [
      'designer',
      'statement',
      'sculptural',
      'gallery',
      'bolero',
      'foxtrot',
      'mambo',
      'satellite',
      'tango',
      'prestige skyline',
    ],
    tone: 'bold, artistic, distinctive, gallery-worthy',
    keywords: ['designer bathroom hardware', 'statement bath accessories', 'sculptural fixtures'],
  },
}

// Functional feature patterns by category
const FUNCTIONAL_FEATURES: Record<
  string,
  {
    signals: string[]
    title_keyword: string | null
    benefit: string
    keywords: string[]
    categories: string[] | null
  }
> = {
  reeded_grip: {
    signals: ['reeded', 'textured grip', 'grooved grip'],
    title_keyword: 'Reeded Grip',
    benefit: 'textured grip surface provides secure hold even with wet hands',
    keywords: ['reeded grab bar', 'textured grip grab bar'],
    categories: ['Grab Bars'],
  },
  smooth_grip: {
    signals: ['smooth'],
    title_keyword: 'Smooth',
    benefit: 'smooth finish for a sleek look that is easy to maintain',
    keywords: ['smooth grab bar'],
    categories: ['Grab Bars'],
  },
  l_shaped: {
    signals: ['90 deg', '90-degree', 'l-shaped', 'left hand', 'right hand', 'angled'],
    title_keyword: 'L-Shaped',
    benefit: 'L-shaped configuration provides corner or transition support',
    keywords: ['L-shaped grab bar', 'corner grab bar', 'angled grab bar'],
    categories: ['Grab Bars'],
  },
  three_post: {
    signals: ['3 post', '3-post', 'three post'],
    title_keyword: '3-Post',
    benefit: 'three-post mounting configuration for enhanced stability',
    keywords: ['3-post grab bar'],
    categories: ['Grab Bars'],
  },
  cube_design: {
    signals: ['cube design', 'cube style', 'cubic'],
    title_keyword: 'Cube Design',
    benefit: 'modern cube-style mounts with clean geometric lines',
    keywords: ['cube design bathroom hardware', 'geometric bathroom accessories'],
    categories: null, // Applies to all
  },
  double_bar: {
    signals: ['double', 'dual bar'],
    title_keyword: 'Double',
    benefit: 'double bar design provides twice the towel hanging capacity',
    keywords: ['double towel bar', 'dual towel bar'],
    categories: ['Towel Bars'],
  },
  with_shelf: {
    signals: ['with shelf', 'shelf combo', 'integrated shelf'],
    title_keyword: 'with Shelf',
    benefit: 'integrated shelf provides additional storage space',
    keywords: ['towel bar with shelf'],
    categories: ['Towel Bars', 'Glass Shelves'],
  },
  train_rack: {
    signals: ['train rack', 'hotel rack', 'hotel style'],
    title_keyword: 'Train Rack',
    benefit: 'hotel-style train rack with integrated shelf',
    keywords: ['train rack', 'hotel towel rack'],
    categories: ['Towel Bars'],
  },
  tilting: {
    signals: ['tilt', 'tilting', 'pivot', 'pivoting', 'adjustable angle'],
    title_keyword: 'Tilting',
    benefit: 'tilt-adjustable angle for personalized viewing',
    keywords: ['tilting mirror', 'pivot mirror', 'tilt vanity mirror'],
    categories: ['Wall Mirrors', 'Make-Up Mirrors'],
  },
  magnifying: {
    signals: ['magnif', '2x', '3x', '4x', '5x', '8x', 'magnification'],
    title_keyword: null, // Use specific magnification from product data
    benefit: 'magnification for detailed grooming and makeup application',
    keywords: ['magnifying mirror', 'magnifying makeup mirror'],
    categories: ['Make-Up Mirrors'],
  },
  extendable: {
    signals: ['extendable', 'extending', 'swing arm', 'articulating'],
    title_keyword: 'Swing Arm',
    benefit: 'extendable swing arm brings mirror closer when needed',
    keywords: ['swing arm mirror', 'extendable mirror'],
    categories: ['Make-Up Mirrors'],
  },
  lighted: {
    signals: ['lighted', 'led', 'illuminated', 'backlit'],
    title_keyword: 'Lighted',
    benefit: 'built-in lighting for optimal visibility',
    keywords: ['lighted mirror', 'LED vanity mirror'],
    categories: ['Make-Up Mirrors', 'Wall Mirrors'],
  },
  recessed: {
    signals: ['recessed', 'in-wall'],
    title_keyword: 'Recessed',
    benefit: 'recessed design creates a streamlined, built-in appearance',
    keywords: ['recessed toilet paper holder'],
    categories: ['Toilet Paper Holders'],
  },
  covered: {
    signals: ['covered', 'hooded', 'lid', 'with cover'],
    title_keyword: 'Covered',
    benefit: 'covered design protects tissue from moisture and dust',
    keywords: ['covered toilet paper holder'],
    categories: ['Toilet Paper Holders'],
  },
  ada_compliant: {
    signals: ['ada', 'accessible', 'compliant'],
    title_keyword: 'ADA Compliant',
    benefit: 'ADA-compliant design meets accessibility requirements',
    keywords: ['ADA grab bar', 'ADA compliant grab bar'],
    categories: ['Grab Bars'],
  },
  wall_mount: {
    signals: ['wall mount', 'wall-mount', 'wall mounted'],
    title_keyword: 'Wall Mount',
    benefit: 'wall-mounted installation saves floor space',
    keywords: ['wall mount'],
    categories: null,
  },
  freestanding: {
    signals: ['freestanding', 'free-standing', 'floor stand'],
    title_keyword: 'Freestanding',
    benefit: 'freestanding design requires no wall mounting',
    keywords: ['freestanding'],
    categories: null,
  },
}

/**
 * Detect design style from product data
 */
export function detectDesignStyle(product: ProductCatalogRow): DesignStyleContext {
  // Build text to analyze
  const textToAnalyze = [
    product.title,
    product.collection || '',
    product.style || '',
  ]
    .join(' ')
    .toLowerCase()

  for (const [style, config] of Object.entries(DESIGN_STYLE_PATTERNS)) {
    if (config.signals.some((signal) => textToAnalyze.includes(signal))) {
      return {
        style,
        tone_guidance: config.tone,
        style_keywords: config.keywords,
      }
    }
  }

  // Default to transitional (versatile)
  return {
    style: 'transitional',
    tone_guidance: 'refined, versatile, quality-focused',
    style_keywords: ['designer bathroom hardware', 'quality bath accessories'],
  }
}

/**
 * Detect functional features from product data
 */
export function detectFunctionalFeatures(product: ProductCatalogRow): FunctionalFeature[] {
  const textToAnalyze = [
    product.title,
    product.narrative_copy || '',
    product.style || '',
    product.mounting_type || '',
    product.bullet_1 || '',
    product.bullet_2 || '',
    product.bullet_3 || '',
    product.bullet_4 || '',
    product.bullet_5 || '',
    product.bullet_6 || '',
  ]
    .join(' ')
    .toLowerCase()

  const detected: FunctionalFeature[] = []

  for (const [featureId, config] of Object.entries(FUNCTIONAL_FEATURES)) {
    // Check category applicability
    if (config.categories && !config.categories.includes(product.category)) {
      continue
    }

    // Check signals
    if (config.signals.some((signal) => textToAnalyze.includes(signal))) {
      detected.push({
        feature_id: featureId,
        title_keyword: config.title_keyword,
        benefit: config.benefit,
        keywords: config.keywords,
      })
    }
  }

  return detected
}

/**
 * Get room context from category
 */
export function getRoomContext(category: string): 'kitchen' | 'bathroom' {
  const catLower = category.toLowerCase()
  if (catLower.includes('kitchen')) {
    return 'kitchen'
  }
  return 'bathroom'
}
