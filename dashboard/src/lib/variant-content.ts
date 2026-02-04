/**
 * Variant Content Generation Utilities
 *
 * Functions to generate variant-specific titles and descriptions
 * by combining base templates with finish names.
 */

/**
 * Generate a variant-specific title by appending finish name to base title.
 *
 * @param baseTitle - The master SKU title template
 * @param finishName - The finish name (e.g., "Antique Brass", "Matte Black")
 * @param platform - Target platform ('google' | 'bing')
 * @returns Variant-specific title with finish name
 *
 * @example
 * generateVariantTitle("18-Inch Paper Towel Holder", "Antique Brass", "google")
 * // Returns: "18-Inch Paper Towel Holder - Antique Brass"
 */
export function generateVariantTitle(
  baseTitle: string | null,
  finishName: string,
  platform: 'google' | 'bing' = 'google'
): string {
  if (!baseTitle) {
    return finishName
  }

  // Clean up the base title
  const cleanBase = baseTitle.trim()

  // Check if finish name is already in the title (avoid duplication)
  if (cleanBase.toLowerCase().includes(finishName.toLowerCase())) {
    return cleanBase
  }

  // Format based on platform preference
  // Google: Use dash separator for clean structured data
  // Bing: Use "in" for more natural language
  if (platform === 'bing') {
    return `${cleanBase} in ${finishName}`
  }

  return `${cleanBase} - ${finishName}`
}

/**
 * Generate a variant-specific description by inserting finish name naturally.
 *
 * @param baseDescription - The master SKU description template
 * @param finishName - The finish name (e.g., "Antique Brass", "Matte Black")
 * @returns Variant-specific description with finish name integrated
 *
 * @example
 * generateVariantDescription(
 *   "This elegant paper towel holder adds style to your kitchen.",
 *   "Antique Brass"
 * )
 * // Returns: "This elegant paper towel holder in Antique Brass adds style to your kitchen."
 */
export function generateVariantDescription(
  baseDescription: string | null,
  finishName: string
): string {
  if (!baseDescription) {
    return `Available in ${finishName} finish.`
  }

  const cleanDesc = baseDescription.trim()

  // Check if finish name is already in the description (avoid duplication)
  if (cleanDesc.toLowerCase().includes(finishName.toLowerCase())) {
    return cleanDesc
  }

  // Strategy 1: Insert after first product mention
  // Look for common product words and insert finish after them
  const productPatterns = [
    /\b(towel bar|towel holder|paper towel holder|soap dish|robe hook|shelf|basket|ring|grab bar|mirror)\b/i,
  ]

  for (const pattern of productPatterns) {
    const match = cleanDesc.match(pattern)
    if (match && match.index !== undefined) {
      const insertPosition = match.index + match[0].length
      const before = cleanDesc.slice(0, insertPosition)
      const after = cleanDesc.slice(insertPosition)

      // Don't insert if there's already a color/finish word immediately after
      if (!/^\s*(in|with|featuring)\s/i.test(after)) {
        return `${before} in ${finishName}${after}`
      }
    }
  }

  // Strategy 2: Prepend finish context if no good insertion point found
  // Only if description doesn't start with a finish-related phrase
  if (!/^(this|the|our|a|an)\s/i.test(cleanDesc)) {
    return `${finishName} finish. ${cleanDesc}`
  }

  // Strategy 3: Insert "in {finish}" after "This" at the start
  if (/^this\s/i.test(cleanDesc)) {
    return cleanDesc.replace(/^(this)\s/i, `$1 ${finishName} `)
  }

  // Fallback: Append finish info at end
  const endsWithPunctuation = /[.!?]$/.test(cleanDesc)
  if (endsWithPunctuation) {
    return `${cleanDesc} Available in ${finishName}.`
  }
  return `${cleanDesc}. Available in ${finishName}.`
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

  // Already formatted nicely
  if (finish.includes(' ')) return finish

  // Handle codes like "ABR" -> check if we should expand
  // For now, just return as-is since we usually have finish_name
  return finish
}
