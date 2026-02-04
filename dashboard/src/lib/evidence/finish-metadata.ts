/**
 * Finish metadata for variant-level description personalization
 * Ported from Python: src/feedops/pipeline/finish_injection.py
 */

export interface FinishMeta {
  category:
    | 'classic_metallic'
    | 'warm_metallic'
    | 'contemporary_neutral'
    | 'living_finish'
    | 'premium_metallic'
    | 'statement_color'
  description_type: 'coordination' | 'statement'
  style_affinities: string[]
  functional_description: string
  coordination_note: string | null
  opening_phrase?: string
  style_context?: string
}

/**
 * Complete finish metadata for all 30 Allied Brass finishes
 */
export const FINISH_METADATA: Record<string, FinishMeta> = {
  'Polished Chrome': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['modern', 'contemporary', 'transitional'],
    functional_description:
      'Polished Chrome delivers a bright, mirror-like sheen that coordinates effortlessly with chrome faucets and modern fixtures.',
    coordination_note:
      'pairs beautifully with matching {collection} accessories in the same finish for a cohesive bathroom design',
    opening_phrase: 'in Polished Chrome coordinates with modern chrome faucets',
    style_context: 'chrome faucets, modern fixtures, contemporary hardware',
  },
  'Polished Brass': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'classic', 'transitional'],
    functional_description:
      'Polished Brass brings warm, golden elegance that complements traditional faucets and classic bathroom fixtures.',
    coordination_note:
      'coordinates with other {collection} pieces for a timeless, unified look',
  },
  'Polished Nickel': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['transitional', 'modern', 'contemporary'],
    functional_description:
      'Polished Nickel offers a softer, warmer alternative to chrome with a subtle golden undertone that suits transitional spaces.',
    coordination_note:
      'pairs seamlessly with matching {collection} hardware for refined continuity',
    opening_phrase: 'in Polished Nickel brings warm elegance to transitional spaces',
    style_context: 'polished nickel faucets, transitional fixtures, warm metallic accents',
  },
  'Satin Chrome': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['modern', 'contemporary', 'transitional'],
    functional_description:
      'Satin Chrome provides a brushed, matte-like surface that resists fingerprints while maintaining a modern, understated elegance.',
    coordination_note:
      'coordinates with other {collection} accessories for a cohesive contemporary look',
  },
  'Satin Nickel': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['transitional', 'modern', 'contemporary'],
    functional_description:
      'Satin Nickel offers a warm, brushed finish that hides water spots and fingerprints, perfect for high-use bathrooms.',
    coordination_note:
      'pairs with matching {collection} pieces for a unified, low-maintenance design',
    opening_phrase: 'in Satin Nickel hides fingerprints while adding warm elegance',
    style_context: 'brushed nickel faucets, transitional fixtures, low-maintenance hardware',
  },
  'Satin Brass': {
    category: 'classic_metallic',
    description_type: 'coordination',
    style_affinities: ['transitional', 'modern', 'contemporary'],
    functional_description:
      'Satin Brass combines warm golden tones with a brushed texture, bringing modern warmth without the high shine of polished brass.',
    coordination_note:
      'coordinates beautifully with other {collection} hardware in the same finish',
    opening_phrase: 'in Satin Brass adds modern warmth with a brushed golden finish',
    style_context: 'brushed brass faucets, modern gold fixtures, transitional hardware',
  },
  'Brushed Bronze': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['transitional', 'traditional', 'rustic'],
    functional_description:
      'Brushed Bronze features warm, earthy tones with a softly textured surface that adds depth to traditional and transitional bathrooms.',
    coordination_note:
      'pairs with matching {collection} accessories for a warm, cohesive aesthetic',
  },
  'Oil Rubbed Bronze': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'transitional', 'rustic', 'industrial'],
    functional_description:
      'Oil Rubbed Bronze offers rich, dark brown tones with subtle copper highlights, bringing Old World character to any bathroom.',
    coordination_note:
      'coordinates with other {collection} pieces for a distinguished, heritage-inspired look',
  },
  'Venetian Bronze': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'transitional', 'mediterranean'],
    functional_description:
      'Venetian Bronze presents deep, warm undertones with subtle golden accents, evoking European craftsmanship and timeless style.',
    coordination_note:
      'pairs elegantly with matching {collection} hardware for refined warmth',
  },
  'Antique Brass': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'classic', 'vintage'],
    functional_description:
      'Antique Brass features a softened, aged golden patina that brings vintage charm and character to traditional spaces.',
    coordination_note:
      'coordinates with other {collection} accessories for a curated, collected look',
    opening_phrase: 'in Antique Brass brings vintage charm to traditional spaces',
    style_context: 'antique brass fixtures, vintage hardware, traditional decor, bronze and copper accents',
  },
  'Antique Bronze': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'transitional', 'rustic'],
    functional_description:
      'Antique Bronze combines deep brown tones with subtle warm highlights, offering heritage appeal with modern durability.',
    coordination_note: 'pairs with matching {collection} pieces for timeless continuity',
  },
  'Antique Copper': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'rustic', 'craftsman'],
    functional_description:
      'Antique Copper brings warm, reddish-brown tones with natural variation, perfect for rustic or craftsman-style bathrooms.',
    coordination_note:
      'coordinates with other {collection} hardware for artisan-inspired warmth',
  },
  'Antique Pewter': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['traditional', 'vintage', 'transitional'],
    functional_description:
      'Antique Pewter offers a soft, silvery-gray tone with subtle warmth, bridging traditional and contemporary aesthetics.',
    coordination_note:
      'pairs with matching {collection} accessories for understated elegance',
  },
  'Matte Black': {
    category: 'contemporary_neutral',
    description_type: 'coordination',
    style_affinities: ['modern', 'contemporary', 'industrial', 'minimalist'],
    functional_description:
      'Matte Black makes a bold, modern statement with its sleek, non-reflective surface that anchors contemporary bathroom designs.',
    coordination_note:
      'coordinates with other {collection} pieces in Matte Black for a striking, cohesive modern look',
    opening_phrase: 'in Matte Black makes a bold statement in modern spaces',
    style_context: 'black faucets, modern fixtures, industrial hardware, minimalist design',
  },
  'Matte Gray': {
    category: 'contemporary_neutral',
    description_type: 'coordination',
    style_affinities: ['modern', 'contemporary', 'minimalist', 'industrial'],
    functional_description:
      'Matte Gray provides a sophisticated neutral that complements concrete, stone, and other modern materials.',
    coordination_note:
      'pairs with matching {collection} hardware for refined industrial appeal',
  },
  'Matte White': {
    category: 'contemporary_neutral',
    description_type: 'coordination',
    style_affinities: ['modern', 'contemporary', 'coastal', 'minimalist'],
    functional_description:
      'Matte White brings clean, fresh simplicity that brightens spaces and creates a light, airy bathroom atmosphere.',
    coordination_note:
      'coordinates with other {collection} accessories for a crisp, unified aesthetic',
  },
  'Unlacquered Brass': {
    category: 'living_finish',
    description_type: 'statement',
    style_affinities: ['traditional', 'transitional', 'artisan'],
    functional_description:
      'Unlacquered Brass is a living finish that develops a unique natural patina over time, gaining character and warmth with age. Each piece becomes one-of-a-kind, perfect for those who appreciate authentic materials that tell a story.',
    coordination_note: null,
    opening_phrase: 'in Unlacquered Brass develops a unique patina over time',
    style_context: 'living finishes, artisan hardware, authentic materials, vintage aesthetic',
  },
  'Spanish Gold': {
    category: 'premium_metallic',
    description_type: 'statement',
    style_affinities: ['traditional', 'luxury', 'mediterranean'],
    functional_description:
      'Spanish Gold presents a rich, warm golden tone with European-inspired elegance, bringing luxury and sophistication to distinguished bathrooms.',
    coordination_note: null,
  },
  'French Gold': {
    category: 'premium_metallic',
    description_type: 'statement',
    style_affinities: ['traditional', 'luxury', 'classic'],
    functional_description:
      'French Gold offers refined European elegance with a rich, warm golden hue that elevates traditional and transitional bathrooms.',
    coordination_note: null,
  },
  'Tuscan Brass': {
    category: 'premium_metallic',
    description_type: 'statement',
    style_affinities: ['mediterranean', 'traditional', 'tuscan'],
    functional_description:
      'Tuscan Brass evokes the warmth of Italian countryside with its rich, aged golden tones, perfect for Mediterranean-inspired spaces.',
    coordination_note: null,
  },
  'Fire Engine Red': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['contemporary', 'eclectic', 'bold'],
    functional_description:
      'Fire Engine Red makes a fearless design statement, transforming functional bathroom hardware into a vibrant focal point. A bold choice for those who embrace color and personality in their space.',
    coordination_note: null,
    opening_phrase: 'in Fire Engine Red transforms this essential into a conversation piece',
    style_context: 'bold accents, statement hardware, colorful bathrooms, eclectic design',
  },
  'Mediterranean Blue': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['coastal', 'mediterranean', 'eclectic', 'sophisticated'],
    functional_description:
      'Mediterranean Blue presents a deep, sophisticated blue with subtle purple undertones, evoking the rich depths of coastal waters for a bold yet refined statement.',
    coordination_note: null,
  },
  Lavender: {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['contemporary', 'soft_modern', 'eclectic'],
    functional_description:
      'Lavender introduces soft, calming color that adds a touch of unexpected elegance, perfect for creating a spa-like retreat.',
    coordination_note: null,
  },
  Pink: {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['contemporary', 'playful', 'eclectic'],
    functional_description:
      'Pink brings playful, modern energy to bathroom design, offering a fresh take on hardware that celebrates individuality.',
    coordination_note: null,
  },
  'Glokzin Teal': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['contemporary', 'eclectic', 'bold'],
    functional_description:
      'Glokzin Teal delivers rich, jewel-toned sophistication, adding artistic depth and a designer touch to modern bathrooms.',
    coordination_note: null,
  },
  'Sea Foam Green': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['coastal', 'soft_modern', 'transitional'],
    functional_description:
      'Sea Foam Green captures the tranquil essence of ocean-inspired design, bringing soft, natural color to coastal and contemporary spaces.',
    coordination_note: null,
  },
  'Golden Yellow': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['eclectic', 'bold', 'contemporary'],
    functional_description:
      'Golden Yellow brings sunny, optimistic energy to bathroom design, creating a warm and inviting atmosphere.',
    coordination_note: null,
  },
  'Autumn Sparkle': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['eclectic', 'transitional', 'warm'],
    functional_description:
      'Autumn Sparkle captures the rich, warm tones of fall foliage, adding seasonal warmth and subtle sparkle to any bathroom.',
    coordination_note: null,
  },
  'Shaded Bronze': {
    category: 'warm_metallic',
    description_type: 'coordination',
    style_affinities: ['transitional', 'traditional', 'rustic'],
    functional_description:
      'Shaded Bronze offers multi-tonal depth with warm bronze undertones and darker accents, adding dimension to traditional spaces.',
    coordination_note:
      'pairs with matching {collection} pieces for a layered, textured look',
  },
  'Spanish Moss': {
    category: 'statement_color',
    description_type: 'statement',
    style_affinities: ['coastal', 'transitional', 'organic'],
    functional_description:
      'Spanish Moss brings the soft, muted greens of Southern landscapes to bathroom design, creating a natural, organic atmosphere.',
    coordination_note: null,
  },
}

/**
 * Get finish metadata by name (case-insensitive)
 */
export function getFinishMetadata(finishName: string): FinishMeta | null {
  // Try exact match first
  if (finishName in FINISH_METADATA) {
    return FINISH_METADATA[finishName]
  }

  // Try case-insensitive match
  const finishLower = finishName.toLowerCase()
  for (const [name, meta] of Object.entries(FINISH_METADATA)) {
    if (name.toLowerCase() === finishLower) {
      return meta
    }
  }

  return null
}

/**
 * Get a short functional description for a finish (first sentence only)
 */
export function getFinishShortDescription(finishName: string): string | null {
  const meta = getFinishMetadata(finishName)
  if (!meta) return null

  const desc = meta.functional_description
  // Find first sentence boundary
  const match = desc.match(/[^.!?]*[.!?]/)
  return match ? match[0] : desc
}
