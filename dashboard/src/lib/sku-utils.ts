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
 * Tries replacing each hyphen position with a slash to cover ALL boundary
 * types (digit-to-digit, letter-to-digit, etc.) without fragile regex.
 *
 * @param urlSku The SKU as it appears in the URL (hyphens only)
 * @returns Array of possible database formats to try, as-is first then slash variants
 */
export function getSkuCandidates(urlSku: string): string[] {
  const decoded = decodeURIComponent(urlSku)
  const candidates = new Set<string>()

  // If already has a slash (from URL decoding), try it and its hyphen version
  if (decoded.includes('/')) {
    candidates.add(decoded)
    candidates.add(decoded.replace(/\//g, '-'))
    return [...candidates]
  }

  // Always try the URL SKU as-is (works for hyphens-only SKUs like 920D-6)
  candidates.add(decoded)

  // Try replacing each hyphen with a slash, one at a time.
  // For "DT-HTL-24-5" this produces: DT/HTL-24-5, DT-HTL/24-5, DT-HTL-24/5
  // The DB lookup loop will find the correct one.
  for (let i = 0; i < decoded.length; i++) {
    if (decoded[i] === '-') {
      candidates.add(decoded.substring(0, i) + '/' + decoded.substring(i + 1))
    }
  }

  return [...candidates]
}
