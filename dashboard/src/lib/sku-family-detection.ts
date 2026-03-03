/**
 * SKU Family Detection via Prefix Pattern Matching
 *
 * Groups master SKUs into product families by extracting a common prefix.
 * Examples: DY-41-18 + DY-41-24 → family "DY-41" (Dayton Towel Bar in 18" and 24")
 */

export interface SkuPrefixResult {
  prefix: string
  spec: string
}

export interface SkuFamily {
  prefix: string
  members: string[]
  specs: string[]
}

/**
 * Extract a family prefix and spec suffix from a master SKU.
 *
 * Returns null if no meaningful split can be made.
 *
 * Examples:
 *   "DY-41-24"    → { prefix: "DY-41", spec: "24" }
 *   "FR-1/16GTB"  → { prefix: "FR-1", spec: "16GTB" }
 *   "P-230-24-TS" → { prefix: "P-230", spec: "24-TS" }
 *   "DMF-2/2X"    → { prefix: "DMF-2", spec: "2X" }
 *   "920D-6"      → null
 *   "AP-26"       → null
 */
export function extractSkuPrefix(masterSku: string): SkuPrefixResult | null {
  // Try slash-separated first: prefix/spec
  if (masterSku.includes('/')) {
    const slashIdx = masterSku.lastIndexOf('/')
    const prefix = masterSku.slice(0, slashIdx)
    const spec = masterSku.slice(slashIdx + 1)
    if (prefix && spec) {
      return { prefix, spec }
    }
  }

  // Try hyphen-separated: find the last hyphen before a numeric segment
  // Need at least 3 hyphen-separated parts to form prefix + spec
  const parts = masterSku.split('-')
  if (parts.length < 3) {
    return null
  }

  // Find split point: rightmost hyphen where the next part starts with a digit
  // and there are at least 2 parts before it
  for (let i = parts.length - 1; i >= 2; i--) {
    if (parts[i] && /^\d/.test(parts[i])) {
      const prefix = parts.slice(0, i).join('-')
      const spec = parts.slice(i).join('-')
      return { prefix, spec }
    }
  }

  return null
}

/**
 * Group SKUs by their prefix into families.
 * Only returns groups with 2+ members (actual families).
 */
export function groupByPrefix(skus: string[]): SkuFamily[] {
  const groups = new Map<string, { members: string[]; specs: string[] }>()

  for (const sku of skus) {
    const result = extractSkuPrefix(sku)
    if (!result) continue

    const existing = groups.get(result.prefix)
    if (existing) {
      existing.members.push(sku)
      existing.specs.push(result.spec)
    } else {
      groups.set(result.prefix, {
        members: [sku],
        specs: [result.spec],
      })
    }
  }

  const families: SkuFamily[] = []
  for (const [prefix, group] of groups) {
    if (group.members.length < 2) continue

    // Sort by SKU name; keep specs aligned with their members
    const indices = group.members
      .map((_, i) => i)
      .sort((a, b) => group.members[a].localeCompare(group.members[b]))

    families.push({
      prefix,
      members: indices.map((i) => group.members[i]),
      specs: indices.map((i) => group.specs[i]),
    })
  }

  return families
}
