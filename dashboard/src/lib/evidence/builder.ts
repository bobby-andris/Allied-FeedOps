/**
 * Evidence table builder for LLM prompts
 * Ported from Python: src/feedops/pipeline/evidence.py
 */

import type { Evidence, ProductCatalogRow, EvidenceContext } from './types'
import { detectDesignStyle, detectFunctionalFeatures, getRoomContext } from './enrichment'
import { getFinishMetadata, getFinishShortDescription } from './finish-metadata'

// Fields that should have "in" suffix
const INCH_FIELDS = new Set([
  'product_length',
  'product_height',
  'product_width',
  'projection',
  'center_to_center',
  'diameter',
  'mirror_height',
  'mirror_width',
  'thickness',
])

// Fields that should have "lb" suffix
const POUND_FIELDS = new Set(['product_weight', 'weight_capacity'])

/**
 * Format a number, removing unnecessary decimals
 */
function formatNumber(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(2)
}

/**
 * Format a value with appropriate unit suffix
 */
function formatWithUnit(field: string, value: number): string {
  if (INCH_FIELDS.has(field)) return `${formatNumber(value)} in`
  if (POUND_FIELDS.has(field)) return `${formatNumber(value)} lb`
  return formatNumber(value)
}

/**
 * Build evidence table from product catalog rows
 */
export function buildEvidenceTable(
  rows: ProductCatalogRow[],
  context: EvidenceContext
): Evidence[] {
  if (rows.length === 0) return []

  const evidence: Evidence[] = []

  // Use first row as representative (all share same master_sku)
  const primary = rows[0]

  // ==================== Core Identification ====================
  evidence.push({
    field: 'master_sku',
    value: primary.master_sku,
    source: 'catalog',
  })
  evidence.push({
    field: 'category',
    value: primary.category,
    source: 'catalog',
  })

  if (primary.collection) {
    evidence.push({
      field: 'collection',
      value: primary.collection,
      source: 'catalog',
    })
  }

  // ==================== Current Content (baseline) ====================
  evidence.push({
    field: 'current_title',
    value: primary.title,
    source: 'catalog',
  })

  if (primary.narrative_copy) {
    evidence.push({
      field: 'current_description',
      value: primary.narrative_copy,
      source: 'catalog',
    })
  }

  // ==================== Feature Bullets ====================
  const bullets = [
    primary.bullet_1,
    primary.bullet_2,
    primary.bullet_3,
    primary.bullet_4,
    primary.bullet_5,
    primary.bullet_6,
  ].filter(Boolean) as string[]

  for (let i = 0; i < bullets.length; i++) {
    evidence.push({
      field: `bullet_${i + 1}`,
      value: bullets[i],
      source: 'catalog',
    })
  }

  // ==================== Material and Style Attributes ====================
  const attrs: Array<{ field: keyof ProductCatalogRow; label: string }> = [
    { field: 'material', label: 'material' },
    { field: 'style', label: 'style' },
    { field: 'shape', label: 'shape' },
    { field: 'orientation', label: 'orientation' },
    { field: 'tilting', label: 'tilting' },
    { field: 'mounting_type', label: 'mounting_type' },
  ]

  for (const attr of attrs) {
    const value = primary[attr.field]
    if (value && typeof value === 'string') {
      evidence.push({
        field: attr.label,
        value: value,
        source: 'catalog',
      })
    }
  }

  // Assembly required
  if (primary.assembly_required !== null) {
    evidence.push({
      field: 'assembly_required',
      value: primary.assembly_required ? 'Yes' : 'No',
      source: 'catalog',
    })
  }

  // ==================== Dimensions ====================
  const dimFields: Array<{ field: keyof ProductCatalogRow; label: string }> = [
    { field: 'product_length', label: 'product_length' },
    { field: 'product_height', label: 'product_height' },
    { field: 'product_width', label: 'product_width' },
    { field: 'projection', label: 'projection' },
    { field: 'product_weight', label: 'product_weight' },
    { field: 'center_to_center', label: 'center_to_center' },
    { field: 'diameter', label: 'diameter' },
    { field: 'mirror_height', label: 'mirror_height' },
    { field: 'mirror_width', label: 'mirror_width' },
    { field: 'thickness', label: 'thickness' },
    { field: 'weight_capacity', label: 'weight_capacity' },
  ]

  for (const dim of dimFields) {
    const value = primary[dim.field]
    if (value !== null && value !== 0 && typeof value === 'number') {
      evidence.push({
        field: dim.label,
        value: formatWithUnit(dim.label, value),
        source: 'catalog',
      })
    }
  }

  // ==================== Included Items ====================
  if (primary.included_items) {
    evidence.push({
      field: 'included_items',
      value: primary.included_items,
      source: 'catalog',
    })
  }

  // ==================== Available Finishes ====================
  const finishes = [...new Set(rows.map((r) => r.finish_name))].sort()
  evidence.push({
    field: 'available_finishes',
    value: finishes.join(', '),
    source: 'catalog',
  })
  evidence.push({
    field: 'finish_count',
    value: finishes.length.toString(),
    source: 'catalog',
  })

  // ==================== Platform-Specific Finish Context ====================
  if (context.platform !== 'shopify' && context.finish_code) {
    const variantRow = rows.find((r) => r.finish_code === context.finish_code)
    if (variantRow) {
      evidence.push({
        field: 'selected_finish',
        value: variantRow.finish_name,
        source: 'variant_context',
      })
      evidence.push({
        field: 'selected_finish_code',
        value: variantRow.finish_code,
        source: 'variant_context',
      })

      // Add finish metadata
      const finishMeta = getFinishMetadata(variantRow.finish_name)
      if (finishMeta) {
        evidence.push({
          field: 'finish_category',
          value: finishMeta.category,
          source: 'finish_metadata',
        })
        evidence.push({
          field: 'finish_style_affinities',
          value: finishMeta.style_affinities.join(', '),
          source: 'finish_metadata',
        })
        const shortDesc = getFinishShortDescription(variantRow.finish_name)
        if (shortDesc) {
          evidence.push({
            field: 'finish_character',
            value: shortDesc,
            source: 'finish_metadata',
          })
        }
      }

      // Variant-specific image URL
      if (variantRow.main_image_url) {
        evidence.push({
          field: 'product_image_url',
          value: variantRow.main_image_url,
          source: 'catalog',
        })
      }
    }
  } else if (primary.main_image_url) {
    // Shopify: use representative image
    evidence.push({
      field: 'product_image_url',
      value: primary.main_image_url,
      source: 'catalog',
    })
  }

  // ==================== On-the-fly Enrichment ====================

  // Design style
  const designStyle = detectDesignStyle(primary)
  evidence.push({
    field: 'design_style',
    value: `${designStyle.style} (${designStyle.tone_guidance})`,
    source: 'enrichment',
  })

  // Functional features
  const features = detectFunctionalFeatures(primary)
  if (features.length > 0) {
    const titleKeywords = features
      .filter((f) => f.title_keyword)
      .map((f) => f.title_keyword as string)
    if (titleKeywords.length > 0) {
      evidence.push({
        field: 'feature_title_keywords',
        value: titleKeywords.join(', '),
        source: 'enrichment',
      })
    }

    const benefits = features.map((f) => f.benefit)
    evidence.push({
      field: 'feature_benefits',
      value: benefits.join('; '),
      source: 'enrichment',
    })
  }

  // Room context
  const roomContext = getRoomContext(primary.category)
  evidence.push({
    field: 'room_context',
    value: roomContext,
    source: 'enrichment',
  })

  // Competitive edge (material-aware)
  const material = primary.material?.toLowerCase() ?? ''
  let competitiveEdge: string
  if (material.includes('brass')) {
    competitiveEdge = 'Solid brass construction outlasts die-cast zinc and plastic alternatives at similar price points.'
  } else if (material.includes('iron')) {
    competitiveEdge = 'Durable iron construction built to last.'
  } else if (material.includes('steel')) {
    competitiveEdge = 'Sturdy steel construction built to last.'
  } else {
    competitiveEdge = 'Quality construction built to last.'
  }
  evidence.push({
    field: 'competitive_edge',
    value: competitiveEdge,
    source: 'enrichment',
  })

  // Warranty info (standard for Allied Brass)
  evidence.push({
    field: 'warranty',
    value: 'Limited lifetime warranty',
    source: 'enrichment',
  })

  return evidence
}

/**
 * Format evidence as markdown table for LLM prompt
 */
export function formatEvidenceMarkdown(evidence: Evidence[]): string {
  const lines = [
    '## Available Product Data',
    '',
    '| Attribute | Value | Source |',
    '|-----------|-------|--------|',
  ]

  for (const e of evidence) {
    // Escape pipe characters in values and truncate long values
    let value = e.value.replace(/\|/g, '\\|')
    if (value.length > 500) {
      value = value.substring(0, 497) + '...'
    }
    lines.push(`| ${e.field} | ${value} | ${e.source} |`)
  }

  return lines.join('\n')
}
