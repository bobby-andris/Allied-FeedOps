import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'

interface ValueSignalWarnings {
  push(message: string): void
}

type LimitedQuery<Row> = {
  select(columns: string): {
    order(column: string, options: { ascending: boolean }): {
      limit(value: number): PromiseLike<{ data: Row[] | null; error: unknown }>
    }
  }
}

interface SupabaseValueSignalClient {
  from(table: 'sku_margin_daily'): LimitedQuery<{ gross_margin_rate?: number | null }>
  from(table: 'order_line_returns_daily'): LimitedQuery<{ return_amount?: number | null }>
  from(table: string): LimitedQuery<Record<string, unknown>>
}

function clampZeroToOne(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.max(0, Math.min(1, value))
}

function average(values: number[]): number | undefined {
  if (values.length === 0) {
    return undefined
  }

  const sum = values.reduce((total, value) => total + value, 0)
  return sum / values.length
}

function toMarginScore(rows: Array<{ gross_margin_rate?: number | null }> | null | undefined): number | undefined {
  const values = (rows ?? [])
    .map((row) => Number(row.gross_margin_rate))
    .filter((value) => Number.isFinite(value))
    .map((value) => clampZeroToOne(value))

  const avg = average(values)
  return avg == null ? undefined : clampZeroToOne(avg)
}

function toReturnsScore(
  rows: Array<{ return_amount?: number | null }> | null | undefined
): number | undefined {
  const values = (rows ?? [])
    .map((row) => Number(row.return_amount))
    .filter((value) => Number.isFinite(value) && value >= 0)

  const avgReturnAmount = average(values)
  if (avgReturnAmount == null) {
    return undefined
  }

  const penalty = Math.min(avgReturnAmount / 100, 1)
  return clampZeroToOne(1 - penalty)
}

export async function loadLatestValueSignalScore(
  supabase: SupabaseValueSignalClient | null | undefined,
  warnings: ValueSignalWarnings
): Promise<number | undefined> {
  if (!supabase || typeof supabase.from !== 'function') {
    return undefined
  }

  let marginScore: number | undefined
  let returnsScore: number | undefined

  try {
    const { data, error } = await supabase
      .from('sku_margin_daily')
      .select('gross_margin_rate')
      .order('snapshot_date', { ascending: false })
      .limit(500)

    if (error) throw error
    marginScore = toMarginScore(data)
  } catch (error) {
    if (isMissingRelationError(error, 'sku_margin_daily')) {
      warnings.push('Table "sku_margin_daily" is missing. Margin confidence signal was skipped.')
    } else {
      warnings.push(`Unable to load margin confidence signal: ${extractErrorMessage(error)}`)
    }
  }

  try {
    const { data, error } = await supabase
      .from('order_line_returns_daily')
      .select('return_amount')
      .order('snapshot_date', { ascending: false })
      .limit(500)

    if (error) throw error
    returnsScore = toReturnsScore(data)
  } catch (error) {
    if (isMissingRelationError(error, 'order_line_returns_daily')) {
      warnings.push('Table "order_line_returns_daily" is missing. Returns confidence signal was skipped.')
    } else {
      warnings.push(`Unable to load returns confidence signal: ${extractErrorMessage(error)}`)
    }
  }

  if (marginScore == null && returnsScore == null) {
    return undefined
  }

  if (marginScore != null && returnsScore != null) {
    return clampZeroToOne(marginScore * 0.7 + returnsScore * 0.3)
  }

  return marginScore ?? returnsScore
}
