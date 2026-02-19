import { describe, expect, it } from 'vitest'

import {
  FINISH_SENTENCE_TOKEN,
  composeDescriptionTemplate,
  deriveEditableDescriptionTemplateParts,
  validateManualDescriptionForPlatform,
  validateManualVariantDescriptionTemplate,
} from '../manual-description'

describe('manual description template helpers', () => {
  it('derives editable parts when description already contains finish sentence token', () => {
    const result = deriveEditableDescriptionTemplateParts(
      `Solid brass shower bracket with precision mounting. ${FINISH_SENTENCE_TOKEN} Built for long-term durability.`,
    )

    expect(result.prefix).toBe('Solid brass shower bracket with precision mounting. ')
    expect(result.suffix).toBe(' Built for long-term durability.')
    expect(result.template).toContain(FINISH_SENTENCE_TOKEN)
  })

  it('normalizes legacy [FINISH_SENTENCE] token to canonical token', () => {
    const result = deriveEditableDescriptionTemplateParts(
      'Solid brass shower bracket with precision mounting. [FINISH_SENTENCE] Built for long-term durability.',
    )

    expect(result.template).toContain(FINISH_SENTENCE_TOKEN)
    expect(result.template).not.toContain('[FINISH_SENTENCE]')
  })

  it('composeDescriptionTemplate keeps exactly one finish sentence token', () => {
    const template = composeDescriptionTemplate(
      'Solid brass shower bracket with precision mounting.',
      'Built for long-term durability.',
    )

    expect(template).toContain(FINISH_SENTENCE_TOKEN)
    expect((template.match(new RegExp(FINISH_SENTENCE_TOKEN, 'g')) || []).length).toBe(1)
  })

  it('validation fails when hardcoded finish names are included', () => {
    const validation = validateManualVariantDescriptionTemplate(
      `Solid brass shower bracket with precision mounting. ${FINISH_SENTENCE_TOKEN} Fire Engine Red finish available.`,
    )

    expect(validation.ok).toBe(false)
    expect(validation.errors.some((error) => error.includes('hardcoded finish'))).toBe(true)
  })

  it('validation fails without finish sentence token', () => {
    const validation = validateManualVariantDescriptionTemplate(
      'Solid brass shower bracket with precision mounting. Built for long-term durability.',
    )

    expect(validation.ok).toBe(false)
    expect(validation.errors.some((error) => error.includes(FINISH_SENTENCE_TOKEN))).toBe(true)
  })

  it('validation succeeds with one token and no hardcoded finishes', () => {
    const validation = validateManualVariantDescriptionTemplate(
      `Solid brass shower bracket with precision mounting. ${FINISH_SENTENCE_TOKEN} Built for long-term durability.`,
    )

    expect(validation.ok).toBe(true)
    expect(validation.normalizedDescription).toContain(FINISH_SENTENCE_TOKEN)
  })

  it('shopify validation allows finish-agnostic freeform description', () => {
    const validation = validateManualDescriptionForPlatform(
      'Crafted from solid brass with concealed mounting hardware for a clean, durable installation.',
      'shopify',
    )

    expect(validation.ok).toBe(true)
    expect(validation.normalizedDescription).toBe(
      'Crafted from solid brass with concealed mounting hardware for a clean, durable installation.',
    )
  })

  it('shopify validation rejects placeholders and hardcoded finish names', () => {
    const withPlaceholder = validateManualDescriptionForPlatform(
      'Solid brass bracket. {FINISH_SENTENCE} Built for durability.',
      'shopify',
    )
    const withFinish = validateManualDescriptionForPlatform(
      'Solid brass bracket in Fire Engine Red with concealed mounting.',
      'shopify',
    )

    expect(withPlaceholder.ok).toBe(false)
    expect(withPlaceholder.errors.some((error) => error.includes('placeholders'))).toBe(true)
    expect(withFinish.ok).toBe(false)
    expect(withFinish.errors.some((error) => error.includes('hardcoded finish'))).toBe(true)
  })
})
