import { getAllFinishNames, PLACEHOLDERS } from '@/lib/finish-data'

export const FINISH_SENTENCE_TOKEN = PLACEHOLDERS.FINISH_SENTENCE
export const LEGACY_FINISH_SENTENCE_TOKEN = '[FINISH_SENTENCE]'

const FINISH_NAMES = getAllFinishNames().sort((a, b) => b.length - a.length)
const TOKEN_REGEX = new RegExp(escapeRegex(FINISH_SENTENCE_TOKEN), 'g')
const LEGACY_TOKEN_REGEX = /\[FINISH_SENTENCE\]/gi

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeLineEndings(value: string): string {
  return value.replace(/\r\n/g, '\n')
}

function normalizeTemplate(value: string): string {
  return normalizeLineEndings(value).replace(LEGACY_TOKEN_REGEX, FINISH_SENTENCE_TOKEN).trim()
}

function trimStartWhitespace(value: string): string {
  return value.replace(/^\s+/, '')
}

function trimEndWhitespace(value: string): string {
  return value.replace(/\s+$/, '')
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

function insertFinishSentenceToken(value: string): string {
  const firstPeriodMatch = value.search(/(?<!\d)\.(?!\d)/)
  if (firstPeriodMatch > 0) {
    const before = value.slice(0, firstPeriodMatch + 1).trimEnd()
    const after = value.slice(firstPeriodMatch + 1).trimStart()
    if (!after) return `${before} ${FINISH_SENTENCE_TOKEN}`
    return `${before} ${FINISH_SENTENCE_TOKEN} ${after}`
  }

  if (!value.trim()) return FINISH_SENTENCE_TOKEN
  return `${value.trim()} ${FINISH_SENTENCE_TOKEN}`
}

export function findHardcodedFinishesInDescription(value: string): string[] {
  const sanitized = normalizeTemplate(value).replace(TOKEN_REGEX, '')
  const normalized = sanitized.toLowerCase()
  return FINISH_NAMES.filter((finish) => normalized.includes(finish.toLowerCase()))
}

export function deriveEditableDescriptionTemplateParts(sourceDescription: string | null | undefined): {
  prefix: string
  suffix: string
  template: string
} {
  const source = normalizeTemplate(sourceDescription || '')
  if (!source) {
    return {
      prefix: '',
      suffix: '',
      template: FINISH_SENTENCE_TOKEN,
    }
  }

  let template = source
  if (!template.includes(FINISH_SENTENCE_TOKEN)) {
    const matchedFinish = findFirstFinishMatch(template)
    if (matchedFinish) {
      template = template.replace(new RegExp(escapeRegex(matchedFinish), 'i'), FINISH_SENTENCE_TOKEN)
    } else {
      template = insertFinishSentenceToken(template)
    }
  }

  const firstTokenIndex = template.indexOf(FINISH_SENTENCE_TOKEN)
  if (firstTokenIndex < 0) {
    return { prefix: '', suffix: '', template: FINISH_SENTENCE_TOKEN }
  }

  return {
    prefix: template.slice(0, firstTokenIndex),
    suffix: template.slice(firstTokenIndex + FINISH_SENTENCE_TOKEN.length),
    template,
  }
}

export function composeDescriptionTemplate(prefix: string, suffix: string): string {
  const left = trimEndWhitespace(normalizeTemplate(prefix).replace(TOKEN_REGEX, ''))
  const right = trimStartWhitespace(normalizeTemplate(suffix).replace(TOKEN_REGEX, ''))
  const punctuationStartsSuffix = /^[,.;:!?)]/.test(right)

  if (!left && !right) return FINISH_SENTENCE_TOKEN
  if (!left) return punctuationStartsSuffix ? `${FINISH_SENTENCE_TOKEN}${right}` : `${FINISH_SENTENCE_TOKEN} ${right}`
  if (!right) return `${left} ${FINISH_SENTENCE_TOKEN}`
  return punctuationStartsSuffix
    ? `${left} ${FINISH_SENTENCE_TOKEN}${right}`
    : `${left} ${FINISH_SENTENCE_TOKEN} ${right}`
}

export function validateManualVariantDescriptionTemplate(inputDescription: string): {
  ok: boolean
  normalizedDescription: string
  errors: string[]
} {
  const normalizedDescription = normalizeTemplate(inputDescription)
  const errors: string[] = []

  if (!normalizedDescription) {
    errors.push('Description is required.')
    return { ok: false, normalizedDescription, errors }
  }

  const tokenMatches = normalizedDescription.match(TOKEN_REGEX) || []
  if (tokenMatches.length !== 1) {
    errors.push(`Description must contain exactly one ${FINISH_SENTENCE_TOKEN} token.`)
  }

  if (normalizedDescription.includes(PLACEHOLDERS.FINISH_NAME)) {
    errors.push(`Description must use ${FINISH_SENTENCE_TOKEN} (not ${PLACEHOLDERS.FINISH_NAME}).`)
  }

  const hardcodedFinishes = findHardcodedFinishesInDescription(normalizedDescription)
  if (hardcodedFinishes.length > 0) {
    errors.push(
      `Description contains hardcoded finish names (${hardcodedFinishes.slice(0, 3).join(', ')}). Use ${FINISH_SENTENCE_TOKEN} instead.`,
    )
  }

  return {
    ok: errors.length === 0,
    normalizedDescription,
    errors,
  }
}
