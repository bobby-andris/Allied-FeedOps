type SupabaseLike = {
  from: (table: string) => {
    select: (columns: string) => {
      in: (column: string, values: string[]) => {
        limit: (value: number) => unknown
      }
    }
  }
}

type AliasLookupResponse = {
  data: Array<{ master_sku?: string | null }> | null
  error: { message?: string } | null
}

function dedupePreserve(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const value of values) {
    const key = value.trim()
    if (!key || seen.has(key)) {
      continue
    }
    seen.add(key)
    out.push(key)
  }
  return out
}

function separatorVariants(input: string): string[] {
  const chars = [...input]
  const separatorPositions = chars
    .map((char, index) => ({ char, index }))
    .filter(({ char }) => char === '-' || char === '/')
    .map(({ index }) => index)

  if (!separatorPositions.length) {
    return [input]
  }

  const variants = new Set<string>([input])
  const total = 1 << separatorPositions.length
  for (let mask = 0; mask < total; mask += 1) {
    const next = [...chars]
    separatorPositions.forEach((pos, idx) => {
      next[pos] = (mask & (1 << idx)) ? '/' : '-'
    })
    variants.add(next.join(''))
  }
  return Array.from(variants)
}

function aliasDistance(candidate: string, requested: string): [number, number] {
  let mismatchCount = 0
  const bound = Math.min(candidate.length, requested.length)
  for (let index = 0; index < bound; index += 1) {
    if (candidate[index] !== requested[index]) {
      mismatchCount += 1
    }
  }
  mismatchCount += Math.abs(candidate.length - requested.length)
  const slashDelta = Math.abs(
    (candidate.match(/\//g)?.length ?? 0) - (requested.match(/\//g)?.length ?? 0)
  )
  return [mismatchCount, slashDelta]
}

export function buildMasterSkuAliases(masterSku: string): string[] {
  const requested = masterSku.trim().replace(/\s+/g, '').toUpperCase()
  if (!requested) {
    return []
  }

  const pool = dedupePreserve([
    requested,
    ...separatorVariants(requested),
    requested.replace(/\//g, ''),
    requested.replace(/-/g, ''),
  ])

  const ordered = pool
    .slice(1)
    .sort((left, right) => {
      const [leftDiff, leftSlash] = aliasDistance(left, requested)
      const [rightDiff, rightSlash] = aliasDistance(right, requested)
      if (leftDiff !== rightDiff) return leftDiff - rightDiff
      if (leftSlash !== rightSlash) return leftSlash - rightSlash
      return left.localeCompare(right)
    })
  return [requested, ...ordered]
}

function pickCanonicalMatch(aliases: string[], rows: Array<{ master_sku?: string | null }> | null): string | null {
  if (!rows?.length) {
    return null
  }
  const matches = new Set(
    rows
      .map((row) => (row.master_sku || '').trim().toUpperCase())
      .filter(Boolean)
  )

  for (const alias of aliases) {
    if (matches.has(alias)) {
      return alias
    }
  }
  return null
}

async function resolveFromTable(
  supabase: SupabaseLike,
  table: string,
  aliases: string[]
): Promise<string | null> {
  if (!aliases.length) {
    return null
  }

  const response = await (supabase
    .from(table)
    .select('master_sku')
    .in('master_sku', aliases)
    .limit(500) as AliasLookupResponse)
  const { data, error } = response

  if (error) {
    console.warn(`Master SKU alias lookup failed for ${table}:`, error.message || error)
    return null
  }

  return pickCanonicalMatch(aliases, data)
}

export async function resolveCanonicalMasterSku(
  supabase: unknown,
  masterSku: string
): Promise<string> {
  const client = supabase as SupabaseLike
  const aliases = buildMasterSkuAliases(masterSku)
  if (!aliases.length) {
    return ''
  }

  const tables = [
    'product_catalog',
    'variant_index',
    'generated_content',
    'variant_finish_sentences',
    'sku_approvals',
  ]

  for (const table of tables) {
    const resolved = await resolveFromTable(client, table, aliases)
    if (resolved) {
      return resolved
    }
  }

  return aliases[0]
}

export async function resolveCanonicalMasterSkuList(
  supabase: unknown,
  masterSkus: string[]
): Promise<string[]> {
  return Promise.all(masterSkus.map((masterSku) => resolveCanonicalMasterSku(supabase, masterSku)))
}
