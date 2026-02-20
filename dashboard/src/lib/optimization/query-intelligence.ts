import { computeDecompositionArtifact, decomposeSearchTermIntent, scoreTermAggregate } from '@/lib/optimization/decomposition/engine'
import type {
  NeedsDecisionTerm,
  QueryIntentFeatures,
  QueryRecommendation,
  QueryValueScore,
} from '@/lib/shopping-funnel/types'

export function decomposeSearchTerm(searchTerm: string): QueryIntentFeatures {
  return decomposeSearchTermIntent(searchTerm).intent
}

function deriveFallbackRecommendation(term: NeedsDecisionTerm): QueryRecommendation {
  const primaryAssignment = [...term.custom_label_0s].sort((a, b) => b.impressions - a.impressions)[0]

  if (!primaryAssignment) {
    return {
      action_type: 'funnel',
      default_tier: 'high',
      confidence: 0.55,
      reason_codes: ['fallback_no_assignment'],
    }
  }

  return computeDecompositionArtifact({
    searchTerm: term.search_term,
    customLabel0: primaryAssignment.custom_label_0,
    assignment: primaryAssignment,
    labelCount: term.custom_label_0s.length,
  }).recommendation
}

function deriveFallbackIntent(term: NeedsDecisionTerm): QueryIntentFeatures {
  return decomposeSearchTermIntent(term.search_term).intent
}

function deriveFallbackValue(term: NeedsDecisionTerm): QueryValueScore {
  return scoreTermAggregate(term.custom_label_0s)
}

export function enrichNeedsDecisionTerm(term: NeedsDecisionTerm): NeedsDecisionTerm {
  return {
    ...term,
    intent_features: deriveFallbackIntent(term),
    recommendation: deriveFallbackRecommendation(term),
    value_score: deriveFallbackValue(term),
  }
}
