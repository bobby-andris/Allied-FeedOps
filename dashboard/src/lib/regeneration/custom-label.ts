export const CATCHALL_CUSTOM_LABEL = '__catchall__'

export function normalizeCustomLabelValue(value: string | null | undefined): string | null {
  if (!value) return null
  const normalized = value.trim().toLowerCase()
  return normalized.length > 0 ? normalized : null
}

export function isCatchallCustomLabel(value: string | null | undefined): boolean {
  return normalizeCustomLabelValue(value) === CATCHALL_CUSTOM_LABEL
}
