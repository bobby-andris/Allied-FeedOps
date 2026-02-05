/**
 * Finish Data for Allied Brass Products
 *
 * Contains marketing descriptions and metadata for all 30 finishes.
 * Used by variant content generation to create finish-specific titles and descriptions.
 */

export interface FinishData {
  name: string
  code: string
  description: string
  style: 'traditional' | 'contemporary' | 'transitional' | 'statement'
  tone: 'warm' | 'cool' | 'neutral' | 'bold'
}

/**
 * All available finishes with marketing-appropriate descriptions.
 * These descriptions are used to replace {FINISH_DESCRIPTION} placeholders.
 */
export const FINISH_DATA: Record<string, FinishData> = {
  'Antique Brass': {
    name: 'Antique Brass',
    code: 'ABR',
    description: 'features a softened, aged golden patina that brings vintage charm to traditional spaces',
    style: 'traditional',
    tone: 'warm',
  },
  'Antique Bronze': {
    name: 'Antique Bronze',
    code: 'ABZ',
    description: 'offers a rich, deep brown tone with subtle highlights that complements rustic and traditional decor',
    style: 'traditional',
    tone: 'warm',
  },
  'Antique Copper': {
    name: 'Antique Copper',
    code: 'CA',
    description: 'brings warmth with its burnished copper tone and aged character for a timeless look',
    style: 'traditional',
    tone: 'warm',
  },
  'Antique Pewter': {
    name: 'Antique Pewter',
    code: 'PEW',
    description: 'delivers a soft, silvery gray with aged undertones that pairs well with classic fixtures',
    style: 'traditional',
    tone: 'cool',
  },
  'Autumn Sparkle': {
    name: 'Autumn Sparkle',
    code: 'ASP',
    description: 'adds a unique shimmer with warm autumn tones for a distinctive decorative accent',
    style: 'statement',
    tone: 'warm',
  },
  'Brushed Bronze': {
    name: 'Brushed Bronze',
    code: 'BBR',
    description: 'combines a warm bronze base with a brushed texture for understated elegance',
    style: 'transitional',
    tone: 'warm',
  },
  'Fire Engine Red': {
    name: 'Fire Engine Red',
    code: 'FER',
    description: 'makes a bold statement with a vibrant, glossy red that adds personality to any space',
    style: 'statement',
    tone: 'bold',
  },
  'Flat Troll Blue': {
    name: 'Flat Troll Blue',
    code: 'FTB',
    description: 'offers a distinctive matte blue finish for a playful yet sophisticated accent',
    style: 'statement',
    tone: 'cool',
  },
  'Glokzin Teal': {
    name: 'Glokzin Teal',
    code: 'GLT',
    description: 'brings coastal-inspired color with a rich teal tone that stands out beautifully',
    style: 'statement',
    tone: 'cool',
  },
  'Golden Yellow': {
    name: 'Golden Yellow',
    code: 'GLY',
    description: 'delivers sunny warmth with a cheerful golden tone that brightens any bathroom',
    style: 'statement',
    tone: 'warm',
  },
  'Lavender': {
    name: 'Lavender',
    code: 'LVN',
    description: 'adds a soft, calming presence with its gentle purple hue for a spa-like atmosphere',
    style: 'statement',
    tone: 'cool',
  },
  'Matte Black': {
    name: 'Matte Black',
    code: 'BKM',
    description: 'delivers modern sophistication with a smooth, non-reflective surface that coordinates with contemporary fixtures',
    style: 'contemporary',
    tone: 'neutral',
  },
  'Matte Gray': {
    name: 'Matte Gray',
    code: 'GYM',
    description: 'offers versatile neutrality with a soft, matte surface that complements any color scheme',
    style: 'contemporary',
    tone: 'neutral',
  },
  'Matte White': {
    name: 'Matte White',
    code: 'WHM',
    description: 'brings clean, crisp simplicity with a smooth matte surface for a fresh modern look',
    style: 'contemporary',
    tone: 'neutral',
  },
  'Mediterranean Blue': {
    name: 'Mediterranean Blue',
    code: 'MBL',
    description: 'evokes coastal elegance with a deep, rich blue inspired by the sea',
    style: 'statement',
    tone: 'cool',
  },
  'Military Camo': {
    name: 'Military Camo',
    code: 'PT1',
    description: 'offers a unique camouflage pattern for a distinctive, personalized touch',
    style: 'statement',
    tone: 'neutral',
  },
  'Oil Rubbed Bronze': {
    name: 'Oil Rubbed Bronze',
    code: 'ORB',
    description: 'features a deep, rich brown with copper highlights that develops character over time',
    style: 'traditional',
    tone: 'warm',
  },
  'Pink': {
    name: 'Pink',
    code: 'PNK',
    description: 'adds a soft, feminine touch with a gentle pink tone for a unique personal statement',
    style: 'statement',
    tone: 'warm',
  },
  'Polished Brass': {
    name: 'Polished Brass',
    code: 'PB',
    description: 'brings classic elegance with a bright, mirror-like golden shine that catches the light',
    style: 'traditional',
    tone: 'warm',
  },
  'Polished Chrome': {
    name: 'Polished Chrome',
    code: 'PC',
    description: 'offers timeless versatility with a bright, reflective surface that matches most fixtures',
    style: 'transitional',
    tone: 'cool',
  },
  'Polished Nickel': {
    name: 'Polished Nickel',
    code: 'PNI',
    description: 'combines warmth and brightness with a soft silver tone that works in any style',
    style: 'transitional',
    tone: 'neutral',
  },
  'Red White and Blue': {
    name: 'Red White and Blue',
    code: 'RWB',
    description: 'celebrates patriotic spirit with a distinctive tri-color pattern',
    style: 'statement',
    tone: 'bold',
  },
  'Satin Brass': {
    name: 'Satin Brass',
    code: 'SBR',
    description: 'offers a warm, brushed golden tone with a soft luster that resists fingerprints',
    style: 'transitional',
    tone: 'warm',
  },
  'Satin Chrome': {
    name: 'Satin Chrome',
    code: 'SCH',
    description: 'delivers a brushed silver look with reduced glare for a softer, modern aesthetic',
    style: 'contemporary',
    tone: 'cool',
  },
  'Satin Nickel': {
    name: 'Satin Nickel',
    code: 'SN',
    description: 'provides a warm silver tone with a brushed texture that hides water spots and fingerprints',
    style: 'transitional',
    tone: 'neutral',
  },
  'Sea Foam Green': {
    name: 'Sea Foam Green',
    code: 'SFG',
    description: 'brings a fresh, coastal vibe with a soft green tone inspired by ocean waves',
    style: 'statement',
    tone: 'cool',
  },
  'Shaded Beige': {
    name: 'Shaded Beige',
    code: 'SHB',
    description: 'offers subtle warmth with a neutral beige tone that blends seamlessly with earth tones',
    style: 'transitional',
    tone: 'warm',
  },
  'Spanish Gold': {
    name: 'Spanish Gold',
    code: 'SGL',
    description: 'adds Old World elegance with a rich, deep gold tone for a luxurious accent',
    style: 'traditional',
    tone: 'warm',
  },
  'Unlacquered Brass': {
    name: 'Unlacquered Brass',
    code: 'UNL',
    description: 'develops a unique living patina over time, creating one-of-a-kind character',
    style: 'traditional',
    tone: 'warm',
  },
  'Venetian Bronze': {
    name: 'Venetian Bronze',
    code: 'VB',
    description: 'combines deep bronze with golden highlights for a warm, Old World European feel',
    style: 'traditional',
    tone: 'warm',
  },
}

/**
 * Get finish data by name (case-insensitive)
 */
export function getFinishData(finishName: string): FinishData | null {
  // Direct lookup
  if (FINISH_DATA[finishName]) {
    return FINISH_DATA[finishName]
  }

  // Case-insensitive lookup
  const normalized = finishName.toLowerCase()
  for (const [key, data] of Object.entries(FINISH_DATA)) {
    if (key.toLowerCase() === normalized) {
      return data
    }
  }

  return null
}

/**
 * Get finish data by code
 */
export function getFinishDataByCode(code: string): FinishData | null {
  const upperCode = code.toUpperCase()
  for (const data of Object.values(FINISH_DATA)) {
    if (data.code === upperCode) {
      return data
    }
  }
  return null
}

/**
 * Get all finish names
 */
export function getAllFinishNames(): string[] {
  return Object.keys(FINISH_DATA)
}

/**
 * Check if a string contains any finish name
 */
export function containsFinishName(text: string): string | null {
  const lowerText = text.toLowerCase()
  for (const finishName of Object.keys(FINISH_DATA)) {
    if (lowerText.includes(finishName.toLowerCase())) {
      return finishName
    }
  }
  return null
}

/**
 * Replace any finish name in text with a new finish name
 */
export function replaceFinishName(text: string, newFinishName: string): string {
  let result = text

  // Replace any existing finish name with the new one
  for (const finishName of Object.keys(FINISH_DATA)) {
    // Case-insensitive replacement
    const regex = new RegExp(finishName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    result = result.replace(regex, newFinishName)
  }

  return result
}

/**
 * Placeholder constants for template generation
 */
export const PLACEHOLDERS = {
  FINISH_NAME: '{FINISH_NAME}',
  FINISH_DESCRIPTION: '{FINISH_DESCRIPTION}',
  FINISH_SENTENCE: '{FINISH_SENTENCE}',
} as const
