import type { SupabaseClient } from '@supabase/supabase-js'

export function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  if (error && typeof error === 'object') {
    const message = Reflect.get(error, 'message')
    const details = Reflect.get(error, 'details')
    const hint = Reflect.get(error, 'hint')
    const parts = [message, details, hint].filter(
      (part): part is string => typeof part === 'string' && part.trim().length > 0
    )
    if (parts.length > 0) {
      return parts.join(' | ')
    }
  }
  return 'Unknown error'
}

export function isMissingRelationError(error: unknown, relationName: string): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }

  const code = Reflect.get(error, 'code')
  if (code === '42P01' || code === 'PGRST205') {
    return true
  }

  const message = extractErrorMessage(error).toLowerCase()
  const relation = relationName.toLowerCase()
  return (
    (message.includes('does not exist') || message.includes('could not find the table')) &&
    (message.includes(relation) || message.includes(`public.${relation}`))
  )
}

export async function insertRowsSafe(
  client: SupabaseClient,
  table: string,
  rows: Record<string, unknown>[]
): Promise<{ inserted: number; warning?: string }> {
  if (rows.length === 0) {
    return { inserted: 0 }
  }

  const { error } = await client.from(table).insert(rows)
  if (!error) {
    return { inserted: rows.length }
  }

  if (isMissingRelationError(error, table)) {
    return {
      inserted: 0,
      warning: `Table \"${table}\" is missing. Apply latest Supabase migrations to enable persistence.`,
    }
  }

  throw error
}
