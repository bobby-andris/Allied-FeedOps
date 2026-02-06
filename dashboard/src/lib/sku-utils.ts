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
 * @param urlSku The SKU as it appears in the URL (hyphens only)
 * @returns Array of possible database formats to try
 */
export function getSkuCandidates(urlSku: string): string[] {
  const candidates: string[] = []

  // 1. URL-decode in case of %2F encoding
  const decoded = decodeURIComponent(urlSku)

  // 2. Add the decoded URL SKU as-is (might match directly, e.g., 920D-6)
  candidates.push(decoded)

  // 3. Try replacing last hyphen-before-dimension with slash
  // Pattern: -16, -2X, -16-GAL → /16, /2X, /16-GAL
  const normalizedLast = decoded.replace(/-(\d+[A-Z]*(?:-[A-Z]+)?)$/i, '/$1')
  if (normalizedLast !== decoded) {
    candidates.push(normalizedLast)
  }

  // 4. Try replacing the second-to-last hyphen-digit segment
  // This handles cases like WP-2-16-GAL where we need WP-2/16-GAL
  const twoPartMatch = decoded.match(/^(.+?)-(\d+)-(\d+[A-Z]*(?:-[A-Z]+)?)$/i)
  if (twoPartMatch) {
    candidates.push(`${twoPartMatch[1]}-${twoPartMatch[2]}/${twoPartMatch[3]}`)
  }

  // 5. If the SKU has a slash already (from decoding), also try the hyphen version
  if (decoded.includes('/')) {
    candidates.push(decoded.replace(/\//g, '-'))
  }

  // Remove duplicates while preserving order
  return [...new Set(candidates)]
}
