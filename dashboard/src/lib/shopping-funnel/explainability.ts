import type { DecompositionArtifact } from '@/lib/optimization/decomposition/types'
import type { ConfidenceComponents, NeedsDecisionExplainability } from '@/lib/shopping-funnel/types'

interface BuildNeedsDecisionExplainabilityOptions {
  artifact: DecompositionArtifact
  primaryCustomLabel0: string | null
}

function toConfidenceComponents(
  metadata: Record<string, unknown>
): ConfidenceComponents | undefined {
  const raw = metadata.recommendation_confidence_components
  if (!raw || typeof raw !== 'object') {
    return undefined
  }

  const payload = raw as Record<string, unknown>

  const base = Number(payload.base)
  const final = Number(payload.final)

  if (!Number.isFinite(base) || !Number.isFinite(final)) {
    return undefined
  }

  const components: ConfidenceComponents = {
    base,
    final,
  }

  if (Number.isFinite(Number(payload.clicks_bonus))) {
    components.clicks_bonus = Number(payload.clicks_bonus)
  }
  if (Number.isFinite(Number(payload.conversions_bonus))) {
    components.conversions_bonus = Number(payload.conversions_bonus)
  }
  if (Number.isFinite(Number(payload.label_count_bonus))) {
    components.label_count_bonus = Number(payload.label_count_bonus)
  }
  if (Number.isFinite(Number(payload.override_bonus))) {
    components.override_bonus = Number(payload.override_bonus)
  }

  return components
}

export function buildNeedsDecisionExplainability(
  options: BuildNeedsDecisionExplainabilityOptions
): NeedsDecisionExplainability {
  const { artifact, primaryCustomLabel0 } = options

  const recommendationConfidenceComponents = toConfidenceComponents(
    artifact.recommendationMetadata ?? {}
  )

  return {
    parser_version: artifact.parserVersion,
    score_version: artifact.scoreVersion,
    recommendation_version: artifact.recommendationVersion,
    primary_custom_label_0: primaryCustomLabel0,
    reason_codes: artifact.recommendation.reason_codes ?? [],
    intent_confidence: artifact.intentConfidence ?? null,
    recommendation_confidence: artifact.recommendation.confidence ?? null,
    intent_confidence_components: artifact.diagnostics?.confidence_components,
    recommendation_confidence_components: recommendationConfidenceComponents,
    diagnostics: {
      normalized_search_term: artifact.diagnostics.normalized_search_term,
      selected_product_object: artifact.diagnostics.selected_product_object,
      product_object_candidates: artifact.diagnostics.matched_tokens.product_object_candidates ?? [],
      modifier_tokens: artifact.diagnostics.matched_tokens.modifier ?? [],
      use_case_tokens: artifact.diagnostics.matched_tokens.use_case ?? [],
      brand_tokens: artifact.diagnostics.matched_tokens.brand ?? [],
      competitor_tokens: artifact.diagnostics.matched_tokens.competitor ?? [],
      risk_tokens: artifact.diagnostics.matched_tokens.risk ?? [],
      ambiguity_multiple_product_objects:
        artifact.diagnostics.ambiguity_flags.multiple_product_objects ?? false,
    },
  }
}
