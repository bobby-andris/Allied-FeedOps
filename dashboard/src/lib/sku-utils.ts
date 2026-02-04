/**
 * SKU format utilities for handling URL-safe vs database formats.
 *
 * Database format: DMF-2/2X (with forward slash for dimension separator)
 * URL format: DMF-2-2X (with hyphen, since slashes are path separators)
 */

/**
 * Convert database SKU format to URL-safe format.
 * Replaces forward slashes with hyphens.
 * Example: DMF-2/2X → DMF-2-2X
 */
export function skuToUrlPath(sku: string): string {
  return sku.replace(/\//g, '-')
}

/**
 * Convert URL SKU format back to database format.
 * Replaces the last hyphen-before-dimension with a forward slash.
 * Example: DMF-2-2X → DMF-2/2X
 *
 * Note: This is a best-effort conversion. The page should try both formats.
 */
export function urlPathToSku(urlPath: string): string {
  // Match: hyphen + digits + optional letters + optional suffix (like -GAL) at end
  return urlPath.replace(/-(\d+[A-Z]*(?:-[A-Z]+)?)$/i, '/$1')
}
