import { getAllFinishNames, PLACEHOLDERS } from '@/lib/finish-data'

export const FINISH_TOKEN = PLACEHOLDERS.FINISH_NAME

const FINISH_NAMES = getAllFinishNames().sort((a, b) => b.length - a.length)
const TOKEN_REGEX = new RegExp(escapeRegex(FINISH_TOKEN), 'g')

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function findFirstFinishMatch(value: string): string | null {
  const lower = value.toLowerCase()
  for (const finish of FINISH_NAMES) {
    if (lower.includes(finish.toLowerCase())) {
      return finish
    }
  }
  return null
}

export function findHardcodedFinishes(value: string): string[] {
  const sanitized = value.replace(TOKEN_REGEX, '')
  const normalized = sanitized.toLowerCase()
  return FINISH_NAMES.filter((finish) => normalized.includes(finish.toLowerCase()))
}

export function deriveEditableTemplateParts(sourceTitle: string | null | undefined): {
  prefix: string
  suffix: string
  template: string
} {
  const title = normalizeWhitespace(sourceTitle || '')

  if (!title) {
    return {
      prefix: '',
      suffix: '',
      template: FINISH_TOKEN,
    }
  }

  let template = title
  if (!template.includes(FINISH_TOKEN)) {
    const matchedFinish = findFirstFinishMatch(template)
    if (matchedFinish) {
      template = template.replace(new RegExp(escapeRegex(matchedFinish), 'i'), FINISH_TOKEN)
    } else {
      template = `${template} - ${FINISH_TOKEN}`
    }
  }

  const firstTokenIndex = template.indexOf(FINISH_TOKEN)
  if (firstTokenIndex < 0) {
    return { prefix: '', suffix: '', template: FINISH_TOKEN }
  }

  return {
    prefix: template.slice(0, firstTokenIndex),
    suffix: template.slice(firstTokenIndex + FINISH_TOKEN.length),
    template,
  }
}

export function composeTemplateTitle(prefix: string, suffix: string): string {
  const left = prefix.replace(TOKEN_REGEX, '').trim()
  const right = suffix.replace(TOKEN_REGEX, '').trim()
  const punctuationStartsSuffix = /^[,.;:!?)]/.test(right)

  if (!left && !right) return FINISH_TOKEN
  if (!left) return punctuationStartsSuffix ? `${FINISH_TOKEN}${right}` : `${FINISH_TOKEN} ${right}`
  if (!right) return `${left} ${FINISH_TOKEN}`
  return punctuationStartsSuffix
    ? `${left} ${FINISH_TOKEN}${right}`
    : `${left} ${FINISH_TOKEN} ${right}`
}

export function validateManualVariantTitleTemplate(inputTitle: string): {
  ok: boolean
  normalizedTitle: string
  errors: string[]
} {
  const normalizedTitle = normalizeWhitespace(inputTitle)
  const errors: string[] = []

  if (!normalizedTitle) {
    errors.push('Title is required.')
    return { ok: false, normalizedTitle, errors }
  }

  const tokenMatches = normalizedTitle.match(TOKEN_REGEX) || []
  if (tokenMatches.length !== 1) {
    errors.push(`Title must contain exactly one ${FINISH_TOKEN} token.`)
  }

  const hardcodedFinishes = findHardcodedFinishes(normalizedTitle)
  if (hardcodedFinishes.length > 0) {
    errors.push(
      `Title contains hardcoded finish names (${hardcodedFinishes.slice(0, 3).join(', ')}). Use ${FINISH_TOKEN} instead.`,
    )
  }

  return {
    ok: errors.length === 0,
    normalizedTitle,
    errors,
  }
}
