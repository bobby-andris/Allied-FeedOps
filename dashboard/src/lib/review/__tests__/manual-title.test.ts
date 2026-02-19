import { describe, expect, it } from 'vitest'

import {
  FINISH_TOKEN,
  composeTemplateTitle,
  deriveEditableTemplateParts,
  validateManualTitleForPlatform,
  validateManualVariantTitleTemplate,
} from '../manual-title'

describe('manual title template helpers', () => {
  it('derives editable parts when title already contains finish token', () => {
    const result = deriveEditableTemplateParts('Wall Mount Towel Bar - {FINISH_NAME} - Allied Brass')

    expect(result.prefix).toBe('Wall Mount Towel Bar - ')
    expect(result.suffix).toBe(' - Allied Brass')
    expect(result.template).toBe('Wall Mount Towel Bar - {FINISH_NAME} - Allied Brass')
  })

  it('derives editable parts by replacing hardcoded finish names', () => {
    const result = deriveEditableTemplateParts('Wall Mount Towel Bar - Fire Engine Red - Allied Brass')

    expect(result.template).toContain(FINISH_TOKEN)
    expect(result.template).not.toContain('Fire Engine Red')
  })

  it('composeTemplateTitle always keeps exactly one finish token', () => {
    const template = composeTemplateTitle('Wall Mount Towel Bar', '- Allied Brass')

    expect(template).toBe(`Wall Mount Towel Bar ${FINISH_TOKEN} - Allied Brass`)
    expect((template.match(new RegExp(FINISH_TOKEN, 'g')) || []).length).toBe(1)
  })

  it('validation fails when hardcoded finish names are included', () => {
    const validation = validateManualVariantTitleTemplate(
      `Wall Mount Towel Bar ${FINISH_TOKEN} - Fire Engine Red Edition`,
    )

    expect(validation.ok).toBe(false)
    expect(validation.errors.some((error) => error.includes('hardcoded finish'))).toBe(true)
  })

  it('validation fails without the finish token', () => {
    const validation = validateManualVariantTitleTemplate('Wall Mount Towel Bar - Allied Brass')

    expect(validation.ok).toBe(false)
    expect(validation.errors.some((error) => error.includes(FINISH_TOKEN))).toBe(true)
  })

  it('validation succeeds with one token and no hardcoded finishes', () => {
    const validation = validateManualVariantTitleTemplate(
      `Wall Mount Towel Bar ${FINISH_TOKEN} - Allied Brass`,
    )

    expect(validation.ok).toBe(true)
    expect(validation.normalizedTitle).toBe(`Wall Mount Towel Bar ${FINISH_TOKEN} - Allied Brass`)
  })

  it('shopify validation allows finish-agnostic freeform title', () => {
    const validation = validateManualTitleForPlatform(
      'Carolina Collection 24-Inch Towel Bar with Concealed Mount',
      'shopify',
    )

    expect(validation.ok).toBe(true)
    expect(validation.normalizedTitle).toBe('Carolina Collection 24-Inch Towel Bar with Concealed Mount')
  })

  it('shopify validation rejects title with hardcoded finish or brand', () => {
    const withFinish = validateManualTitleForPlatform(
      'Carolina Collection 24-Inch Towel Bar in Fire Engine Red',
      'shopify',
    )
    const withBrand = validateManualTitleForPlatform(
      'Allied Brass Carolina Collection 24-Inch Towel Bar',
      'shopify',
    )

    expect(withFinish.ok).toBe(false)
    expect(withFinish.errors.some((error) => error.includes('hardcoded finish'))).toBe(true)
    expect(withBrand.ok).toBe(false)
    expect(withBrand.errors.some((error) => error.includes('Allied Brass'))).toBe(true)
  })
})
