export interface ClassifiedGoogleAdsError {
  code: string
  retryable: boolean
  rateLimited: boolean
  message: string
}

export interface RetryAttemptContext {
  delayMs: number
  retryCount: number
  errorCode: string
  operationName?: string
}

export interface RunWithGoogleAdsRetryOptions {
  maxRetries?: number
  baseDelayMs?: number
  sleep?: (ms: number) => Promise<void>
  onRetry?: (context: RetryAttemptContext) => void
  operationName?: string
}

export interface RetrySuccess<T> {
  value: T
  retryCount: number
}

const RATE_LIMIT_CODES = ['RESOURCE_TEMPORARILY_EXHAUSTED', 'RATE_EXCEEDED'] as const
const RETRYABLE_CODES = [
  ...RATE_LIMIT_CODES,
  'TRANSIENT_ERROR',
  'INTERNAL_ERROR',
  'UNAVAILABLE',
  'DEADLINE_EXCEEDED',
  'TEMPORARILY_UNAVAILABLE',
] as const

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function extractString(value: unknown): string {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

function collectErrorMessages(error: unknown): string[] {
  if (!error) {
    return []
  }

  if (typeof error === 'string') {
    return [error]
  }

  if (error instanceof Error) {
    const parts = [error.message]
    const nested = error as Error & {
      details?: unknown
      code?: unknown
      status?: unknown
      error?: unknown
      errors?: unknown
    }
    parts.push(extractString(nested.code))
    parts.push(extractString(nested.status))
    parts.push(extractString(nested.details))
    if (nested.error) {
      parts.push(...collectErrorMessages(nested.error))
    }
    if (Array.isArray(nested.errors)) {
      for (const item of nested.errors) {
        parts.push(...collectErrorMessages(item))
      }
    }
    return parts.filter(Boolean)
  }

  if (typeof error === 'object') {
    const record = error as Record<string, unknown>
    const parts = [
      extractString(record.message),
      extractString(record.code),
      extractString(record.status),
      extractString(record.details),
      extractString(record.error_code),
    ]
    if (record.error) {
      parts.push(...collectErrorMessages(record.error))
    }
    if (Array.isArray(record.errors)) {
      for (const item of record.errors) {
        parts.push(...collectErrorMessages(item))
      }
    }
    return parts.filter(Boolean)
  }

  return []
}

function getKnownErrorCode(message: string): string {
  const upper = message.toUpperCase()
  for (const code of RETRYABLE_CODES) {
    if (upper.includes(code)) {
      return code
    }
  }
  return 'UNKNOWN'
}

export function classifyGoogleAdsError(error: unknown): ClassifiedGoogleAdsError {
  const messages = collectErrorMessages(error)
  const message = messages.length > 0 ? messages.join(' | ') : 'Unknown Google Ads API error'
  const code = getKnownErrorCode(message)
  const rateLimited = RATE_LIMIT_CODES.includes(code as (typeof RATE_LIMIT_CODES)[number])
  const retryable = RETRYABLE_CODES.includes(code as (typeof RETRYABLE_CODES)[number])

  return {
    code,
    retryable,
    rateLimited,
    message,
  }
}

export function getRetryDelayMs(
  retryCount: number,
  classifiedError: ClassifiedGoogleAdsError,
  baseDelayMs = 5000
): number {
  if (classifiedError.rateLimited) {
    return 60000
  }

  const exponentialDelay = baseDelayMs * 2 ** Math.max(retryCount - 1, 0)
  return Math.min(exponentialDelay, 60000)
}

export class GoogleAdsRetryError extends Error {
  readonly code: string
  readonly retryCount: number
  readonly operationName?: string
  readonly causeError?: unknown

  constructor(
    params: {
      code: string
      message: string
      retryCount: number
      operationName?: string
    },
    causeError?: unknown
  ) {
    super(params.message)
    this.name = 'GoogleAdsRetryError'
    this.code = params.code
    this.retryCount = params.retryCount
    this.operationName = params.operationName
    this.causeError = causeError
  }
}

export async function runWithGoogleAdsRetry<T>(
  operation: () => Promise<T>,
  options: RunWithGoogleAdsRetryOptions = {}
): Promise<RetrySuccess<T>> {
  const maxRetries = options.maxRetries ?? 3
  const baseDelayMs = options.baseDelayMs ?? 5000
  const sleep = options.sleep ?? sleepMs

  let retryCount = 0
  while (true) {
    try {
      const value = await operation()
      return { value, retryCount }
    } catch (error) {
      const classified = classifyGoogleAdsError(error)
      if (!classified.retryable || retryCount >= maxRetries) {
        throw new GoogleAdsRetryError(
          {
            code: classified.code,
            message: classified.message,
            retryCount,
            operationName: options.operationName,
          },
          error
        )
      }

      retryCount += 1
      const delayMs = getRetryDelayMs(retryCount, classified, baseDelayMs)
      options.onRetry?.({
        delayMs,
        retryCount,
        errorCode: classified.code,
        operationName: options.operationName,
      })
      await sleep(delayMs)
    }
  }
}
