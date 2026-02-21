/**
 * Semi-automated Shopping→Search Graduation with experiment holdout logic.
 *
 * Extends the base evaluateShoppingToSearchGraduation with holdout
 * experiment support and batch processing.
 */

import { evaluateShoppingToSearchGraduation } from '@/lib/intent/policy'
import type {
  ShoppingToSearchGraduationInput,
  ShoppingToSearchGraduationDecision,
  INTENT_POLICY_VERSION as PolicyVersionType,
} from '@/lib/intent/types'
import { INTENT_POLICY_VERSION } from '@/lib/intent/types'

// Re-export the policy version type reference to keep lint happy
export type { PolicyVersionType }

export interface GraduationWithHoldoutInput extends ShoppingToSearchGraduationInput {
  /** If true, this term is in the experiment holdout cohort. */
  isHoldout?: boolean
  /** Experiment key identifying the holdout experiment. */
  experimentKey?: string
}

export interface GraduationWithHoldoutDecision extends ShoppingToSearchGraduationDecision {
  /** Whether the term was excluded due to holdout. */
  holdoutExcluded: boolean
  /** The experiment key, if any. */
  experimentKey?: string
}

export interface GraduationBatchInput {
  terms: GraduationWithHoldoutInput[]
  /** If provided, assigns a percentage of eligible terms to holdout. */
  experimentKey?: string
  /** Holdout percentage (0-1). Defaults to 0.1 (10%). */
  holdoutRate?: number
}

export interface GraduationBatchResult {
  results: GraduationWithHoldoutDecision[]
  eligibleCount: number
  holdoutCount: number
  ineligibleCount: number
  experimentKey?: string
}

/**
 * Evaluates a single term for graduation, respecting holdout experiment logic.
 * If the term is in the holdout cohort, returns eligible=false with reason.
 */
export function evaluateGraduationWithHoldout(
  input: GraduationWithHoldoutInput
): GraduationWithHoldoutDecision {
  // Run the base graduation evaluation
  const baseDecision = evaluateShoppingToSearchGraduation(input)

  // If not eligible by base policy, pass through
  if (!baseDecision.eligible) {
    return {
      ...baseDecision,
      holdoutExcluded: false,
      experimentKey: input.experimentKey,
    }
  }

  // If term is in holdout, exclude it
  if (input.isHoldout) {
    return {
      ...baseDecision,
      eligible: false,
      holdoutExcluded: true,
      experimentKey: input.experimentKey,
      reasonCodes: [...baseDecision.reasonCodes, 'holdout_experiment_active'],
    }
  }

  return {
    ...baseDecision,
    holdoutExcluded: false,
    experimentKey: input.experimentKey,
  }
}

/**
 * Deterministic holdout assignment based on term hash.
 * Returns true if the term should be in the holdout cohort.
 */
function assignToHoldout(searchTerm: string, holdoutRate: number): boolean {
  // Simple hash: sum char codes, mod 1000, compare to rate threshold
  let hash = 0
  for (let i = 0; i < searchTerm.length; i++) {
    hash = (hash * 31 + searchTerm.charCodeAt(i)) & 0x7fffffff
  }
  return (hash % 1000) / 1000 < holdoutRate
}

/**
 * Processes a batch of graduation candidates.
 * Optionally assigns terms to an experiment holdout cohort.
 */
export function buildGraduationBatch(
  terms: GraduationWithHoldoutInput[],
  experimentKey?: string,
  holdoutRate: number = 0.1
): GraduationBatchResult {
  const results: GraduationWithHoldoutDecision[] = []
  let eligibleCount = 0
  let holdoutCount = 0
  let ineligibleCount = 0

  for (const term of terms) {
    // Determine holdout status
    const isHoldout =
      term.isHoldout ??
      (experimentKey != null ? assignToHoldout(term.searchTerm, holdoutRate) : false)

    const input: GraduationWithHoldoutInput = {
      ...term,
      isHoldout,
      experimentKey: term.experimentKey ?? experimentKey,
    }

    const decision = evaluateGraduationWithHoldout(input)
    results.push(decision)

    if (decision.holdoutExcluded) {
      holdoutCount++
    } else if (decision.eligible) {
      eligibleCount++
    } else {
      ineligibleCount++
    }
  }

  return {
    results,
    eligibleCount,
    holdoutCount,
    ineligibleCount,
    experimentKey,
  }
}

// Re-export for convenience
export { INTENT_POLICY_VERSION }
