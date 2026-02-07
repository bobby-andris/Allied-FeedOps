/**
 * SKU format utilities for handling URL-safe vs database formats.
 *
 * Database format: May use slashes (WP-2/16-GAL) or hyphens (920D-6)
 * URL format: Always uses hyphens (slashes are path separators)
 *
 * The database has inconsistent formats - some SKUs use slashes for
 * dimension separators, others use hyphens throughout. When converting
 * from URL to database format, we generate multiple candidates and
 * try each one until we find a match.
 */

/**
 * Convert database SKU format to URL-safe format.
 * Replaces forward slashes with hyphens.
 * Example: WP-2/16-GAL → WP-2-16-GAL
 */
export function skuToUrlPath(sku: string): string {
  return sku.replace(/\//g, '-')
}

/**
 * Convert URL SKU format back to database format.
 * Replaces the last hyphen-before-dimension with a forward slash.
 * Example: WP-2-16-GAL → WP-2/16-GAL
 *
 * @deprecated Use getSkuCandidates for more robust matching.
 * This is a best-effort conversion that only works for some SKU patterns.
 */
export function urlPathToSku(urlPath: string): string {
  // Match: hyphen + digits + optional letters + optional suffix (like -GAL) at end
  return urlPath.replace(/-(\d+[A-Z]*(?:-[A-Z]+)?)$/i, '/$1')
}

/**
 * Generate all possible database SKU formats for a URL SKU.
 * Use this when looking up a SKU in the database - try each candidate
 * until you find a match.
 *
 * IMPORTANT: Slash-format candidates are prioritized first, as that's the
 * canonical format in product_catalog. This prevents matching incorrect
 * hyphen-format duplicates that may exist in the database.
 *
 * @param urlSku The SKU as it appears in the URL (hyphens only)
 * @returns Array of possible database formats to try, prioritized by likelihood
 */
export function getSkuCandidates(urlSku: string): string[] {
  const slashCandidates: string[] = []
  const hyphenCandidates: string[] = []

  // 1. URL-decode in case of %2F encoding
  const decoded = decodeURIComponent(urlSku)

  // If already has slash (from URL decoding), prioritize it
  if (decoded.includes('/')) {
    slashCandidates.push(decoded)
    hyphenCandidates.push(decoded.replace(/\//g, '-'))
  } else {
    // Try converting hyphens to slashes (these are more likely to be correct)

    // 2. Try replacing last hyphen-before-dimension with slash
    // Pattern: -16, -2X, -16-GAL → /16, /2X, /16-GAL
    const normalizedLast = decoded.replace(/-(\d+[A-Z]*(?:-[A-Z]+)?)$/i, '/$1')
    if (normalizedLast !== decoded) {
      slashCandidates.push(normalizedLast)
    }

    // 3. Try replacing the second-to-last hyphen-digit segment
    // This handles cases like WP-2-16-GAL where we need WP-2/16-GAL
    // Also handles DMF-2-2X → DMF-2/2X
    const twoPartMatch = decoded.match(/^(.+?)-(\d+)-(\d+[A-Z]*(?:-[A-Z]+)?)$/i)
    if (twoPartMatch) {
      slashCandidates.push(`${twoPartMatch[1]}-${twoPartMatch[2]}/${twoPartMatch[3]}`)
    }

    // 4. Add the decoded URL SKU as-is last (might match hyphens-only SKUs like 920D-6)
    hyphenCandidates.push(decoded)
  }

  // Return slash candidates first (canonical format), then hyphen fallbacks
  const allCandidates = [...slashCandidates, ...hyphenCandidates]

  // Remove duplicates while preserving order
  return [...new Set(allCandidates)]
}
