/**
 * Variant Content Generation Utilities
 *
 * Functions to generate variant-specific titles and descriptions
 * by combining base templates with finish-specific content.
 *
 * NEW APPROACH (preferred):
 * - Base description is finish-agnostic
 * - Product-specific finish sentences are stored in variant_finish_sentences table
 * - Sentences describe the relationship between THIS product and each finish
 * - E.g., "The warm patina of Antique Brass complements this traditional Carolina design."
 *
 * LEGACY FALLBACK (for content without finish sentences):
 * - Uses {FINISH_NAME} and {FINISH_DESCRIPTION} placeholders
 * - Or detects and replaces hardcoded finish names
 * - Falls back to generic finish descriptions from finish-data.ts
 */

import {
  getFinishData,
  getAllFinishNames,
  PLACEHOLDERS,
  type FinishData,
} from './finish-data'

/**
 * Generate a variant-specific title from a base template.
 *
 * Handles three cases:
 * 1. Template has {FINISH_NAME} placeholder → replace it
 * 2. Template has a different finish name → replace it
 * 3. Template has no finish → append finish name
 *
 * @param baseTitle - The master SKU title template
 * @param finishName - The target finish name (e.g., "Fire Engine Red")
 * @param platform - Target platform ('google' | 'bing')
 * @returns Variant-specific title with correct finish
 */
export function generateVariantTitle(
  baseTitle: string | null,
  finishName: string,
  platform: 'google' | 'bing' = 'google'
): string {
  if (!baseTitle) {
    return finishName
  }

  let result = baseTitle.trim()

  // Case 1: Replace placeholder if present
  if (result.includes(PLACEHOLDERS.FINISH_NAME)) {
    return result.replace(new RegExp(escapeRegex(PLACEHOLDERS.FINISH_NAME), 'g'), finishName)
  }

  // Case 2: Check if target finish is already in title (exact match)
  if (result.toLowerCase().includes(finishName.toLowerCase())) {
    return result
  }

  // Case 3: Check if a DIFFERENT finish name is in the title → replace it
  const allFinishes = getAllFinishNames()
  for (const existingFinish of allFinishes) {
    if (result.toLowerCase().includes(existingFinish.toLowerCase())) {
      // Replace the existing finish with the new one (case-preserving)
      const regex = new RegExp(escapeRegex(existingFinish), 'gi')
      return result.replace(regex, finishName)
    }
  }

  // Case 4: No finish in title - append based on platform style
  if (platform === 'bing') {
    return `${result} in ${finishName}`
  }
  return `${result} - ${finishName}`
}

/**
 * Generate a variant-specific description from a base template.
 *
 * Priority order:
 * 1. If finishSentences provided → use product-specific finish sentence
 * 2. If template has placeholders → replace them with finish data
 * 3. If template has a different finish name → replace it
 * 4. If template has no finish → insert finish naturally
 *
 * @param baseDescription - The master SKU description template
 * @param finishName - The target finish name (e.g., "Fire Engine Red")
 * @param finishSentences - Optional product-specific finish sentences (from variant_finish_sentences table)
 * @returns Variant-specific description with correct finish
 */
export function generateVariantDescription(
  baseDescription: string | null,
  finishName: string,
  finishSentences?: Record<string, string>
): string {
  // Handle missing base description
  if (!baseDescription) {
    // Use finish sentence if available
    if (finishSentences?.[finishName]) {
      return finishSentences[finishName]
    }
    // Fallback to generic finish data
    const finishData = getFinishData(finishName)
    if (finishData) {
      return `Available in ${finishName}, which ${finishData.description}.`
    }
    return `Available in ${finishName} finish.`
  }

  let result = baseDescription.trim()

  // Priority 1: Use product-specific finish sentence if available
  if (finishSentences?.[finishName]) {
    const finishSentence = finishSentences[finishName]

    // Insert finish sentence after first sentence
    // "This towel bar features solid brass. [FINISH SENTENCE]. Backed by..."
    const firstPeriodMatch = result.search(/(?<!\d)\.(?!\d)/)
    if (firstPeriodMatch > 0) {
      const before = result.slice(0, firstPeriodMatch + 1)
      const after = result.slice(firstPeriodMatch + 1)
      // Add space before finish sentence, and ensure proper spacing after
      return `${before} ${finishSentence}${after.startsWith(' ') ? after : ' ' + after}`.trim()
    }
    // No period found - append finish sentence
    return `${result} ${finishSentence}`.trim()
  }

  // Fallback to generic logic for legacy content
  return generateVariantDescriptionGeneric(baseDescription, finishName)
}

/**
 * Generic variant description generation (fallback when no finish sentences available).
 * Handles placeholders and hardcoded finish replacement.
 */
function generateVariantDescriptionGeneric(
  baseDescription: string,
  finishName: string
): string {
  let result = baseDescription.trim()
  const finishData = getFinishData(finishName)

  // Case 1: Replace placeholders if present
  const hasPlaceholder =
    result.includes(PLACEHOLDERS.FINISH_NAME) ||
    result.includes(PLACEHOLDERS.FINISH_DESCRIPTION)

  if (hasPlaceholder) {
    result = result.replace(
      new RegExp(escapeRegex(PLACEHOLDERS.FINISH_NAME), 'g'),
      finishName
    )

    if (finishData) {
      // Replace {FINISH_DESCRIPTION} with the full sentence
      const finishDescSentence = `${finishName} ${finishData.description}`
      result = result.replace(
        new RegExp(escapeRegex(PLACEHOLDERS.FINISH_DESCRIPTION), 'g'),
        finishDescSentence
      )
    } else {
      // Remove placeholder if no finish data
      result = result.replace(
        new RegExp(escapeRegex(PLACEHOLDERS.FINISH_DESCRIPTION) + '\\.?\\s*', 'g'),
        ''
      )
    }

    return result.trim()
  }

  // Case 2: Check if target finish is already correctly in description
  if (result.toLowerCase().includes(finishName.toLowerCase())) {
    return result
  }

  // Case 3: Check for and replace any existing finish name and its description
  const allFinishes = getAllFinishNames()
  let foundExistingFinish = false

  for (const existingFinish of allFinishes) {
    if (result.toLowerCase().includes(existingFinish.toLowerCase())) {
      foundExistingFinish = true
      const existingData = getFinishData(existingFinish)

      // Replace the finish name
      const finishRegex = new RegExp(escapeRegex(existingFinish), 'gi')
      result = result.replace(finishRegex, finishName)

      // If there's a finish description pattern, replace it too
      // Pattern: "which features/offers/brings/delivers/etc..."
      if (existingData && finishData) {
        // Replace the old finish description with the new one
        const oldDesc = existingData.description
        const newDesc = finishData.description

        // Try to replace the description if it exists
        if (result.toLowerCase().includes(oldDesc.toLowerCase().substring(0, 30))) {
          const descRegex = new RegExp(escapeRegex(oldDesc), 'gi')
          result = result.replace(descRegex, newDesc)
        }
      }

      break // Only replace the first found finish
    }
  }

  if (foundExistingFinish) {
    return result
  }

  // Case 4: No finish in description - insert naturally
  return insertFinishInDescription(result, finishName, finishData)
}

/**
 * Insert finish name naturally into a description that has no finish mention.
 */
function insertFinishInDescription(
  description: string,
  finishName: string,
  finishData: FinishData | null
): string {
  // Strategy 1: Look for "available in" phrase and insert after
  const availableInMatch = description.match(/available in\s+/i)
  if (availableInMatch && availableInMatch.index !== undefined) {
    const insertPos = availableInMatch.index + availableInMatch[0].length
    const before = description.slice(0, insertPos)
    const after = description.slice(insertPos)

    if (finishData) {
      return `${before}${finishName}, which ${finishData.description}. ${after}`.trim()
    }
    return `${before}${finishName}. ${after}`.trim()
  }

  // Strategy 2: Insert after first product mention
  const productPatterns = [
    /\b(towel bar|towel holder|paper towel holder|soap dish|robe hook|shelf|basket|ring|grab bar|mirror|cabinet pull|toilet paper holder|tissue holder)\b/i,
  ]

  for (const pattern of productPatterns) {
    const match = description.match(pattern)
    if (match && match.index !== undefined) {
      const insertPosition = match.index + match[0].length
      const before = description.slice(0, insertPosition)
      const after = description.slice(insertPosition)

      // Don't insert if there's already a preposition
      if (!/^\s*(in|with|featuring)\s/i.test(after)) {
        return `${before} in ${finishName}${after}`
      }
    }
  }

  // Strategy 3: Prepend if description starts with article
  if (/^(this|the|our|a|an)\s/i.test(description)) {
    return description.replace(/^(this|the|our|a|an)\s/i, `$1 ${finishName} `)
  }

  // Fallback: Append finish info at end
  const endsWithPunctuation = /[.!?]$/.test(description)
  if (finishData) {
    if (endsWithPunctuation) {
      return `${description} Available in ${finishName}, which ${finishData.description}.`
    }
    return `${description}. Available in ${finishName}, which ${finishData.description}.`
  }

  if (endsWithPunctuation) {
    return `${description} Available in ${finishName}.`
  }
  return `${description}. Available in ${finishName}.`
}

/**
 * Escape special regex characters in a string
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Truncate text with ellipsis for preview display
 */
export function truncateForPreview(text: string | null, maxLength: number = 60): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}

/**
 * Get a display-friendly finish name from various formats
 */
export function normalizeFinishName(finish: string | null): string {
  if (!finish) return 'Unknown Finish'

  // Already formatted nicely (has space)
  if (finish.includes(' ')) return finish

  // Try to look up by code
  const finishData = getFinishData(finish)
  if (finishData) {
    return finishData.name
  }

  return finish
}

/**
 * Check if a base template uses placeholders (preferred format)
 */
export function templateUsesPlaceholders(template: string): boolean {
  return (
    template.includes(PLACEHOLDERS.FINISH_NAME) ||
    template.includes(PLACEHOLDERS.FINISH_DESCRIPTION)
  )
}

/**
 * Check if a base template has a hardcoded finish (problematic format)
 */
export function templateHasHardcodedFinish(template: string): string | null {
  const lowerTemplate = template.toLowerCase()
  for (const finishName of getAllFinishNames()) {
    if (lowerTemplate.includes(finishName.toLowerCase())) {
      return finishName
    }
  }
  return null
}
