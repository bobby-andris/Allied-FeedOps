import type { SupabaseClient } from '@supabase/supabase-js'
import type { AssignmentTier } from '@/lib/shopping-funnel/types'
import type {
  GuardrailInput,
  GuardrailRolloutStatus,
  TierMovementRequest,
  TierMovementResult,
  TierMovementBatchRequest,
  TierMovementBatchResult,
} from '@/lib/intent/types'
import { evaluateGuardrails } from '@/lib/intent/policy'
import { insertRowsSafe, extractErrorMessage } from '@/lib/intent/persistence'

const TIER_TO_LABEL_PREFIX: Record<Exclude<AssignmentTier, 'campaign_negative'>, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const CONFIDENCE_GATES = {
  autoSafe: 0.75,
  reviewRequired: 0.55,
}

function deriveLabelValue(customLabel0: string, targetTier: AssignmentTier): string | null {
  if (targetTier === 'campaign_negative') {
    return null
  }

  const prefix = TIER_TO_LABEL_PREFIX[targetTier]
  if (!prefix) return null

  // custom_label_0 format examples: "Bathroom Accessories - High", "Towel Bars - Medium"
  // Replace the tier suffix while preserving the category prefix
  const dashIndex = customLabel0.lastIndexOf(' - ')
  if (dashIndex >= 0) {
    return `${customLabel0.substring(0, dashIndex)} - ${prefix}`
  }

  // If no dash separator, just use the prefix
  return prefix
}

export function validateTierMovement(
  request: TierMovementRequest,
  guardrailStatus: GuardrailRolloutStatus
): { valid: boolean; reason?: string } {
  if (guardrailStatus === 'blocked') {
    return { valid: false, reason: 'Guardrails are in blocked state — all movements are suspended' }
  }

  if (guardrailStatus === 'hold' && request.confidence < CONFIDENCE_GATES.autoSafe) {
    return { valid: false, reason: 'Guardrails are in hold state — only high-confidence movements allowed' }
  }

  if (request.confidence < CONFIDENCE_GATES.reviewRequired) {
    return { valid: false, reason: `Confidence ${request.confidence.toFixed(2)} is below observe-only threshold (${CONFIDENCE_GATES.reviewRequired})` }
  }

  if (request.currentTier === request.targetTier) {
    return { valid: false, reason: 'Current tier matches target tier — no movement needed' }
  }

  if (request.action === 'hold') {
    return { valid: false, reason: 'Policy action is hold — no movement recommended' }
  }

  return { valid: true }
}

export async function executeTierMovement(
  supabase: SupabaseClient,
  request: TierMovementRequest,
  guardrailStatus: GuardrailRolloutStatus,
  dryRun: boolean = false
): Promise<TierMovementResult> {
  const validation = validateTierMovement(request, guardrailStatus)

  if (!validation.valid) {
    const isBlockedByGuardrail = validation.reason?.includes('blocked') || validation.reason?.includes('hold')
    const isReviewNeeded = validation.reason?.includes('observe-only') ||
      (guardrailStatus === 'hold' && request.confidence >= CONFIDENCE_GATES.reviewRequired)

    return {
      searchTerm: request.searchTerm,
      customLabel0: request.customLabel0,
      currentTier: request.currentTier,
      targetTier: request.targetTier,
      status: isBlockedByGuardrail ? 'blocked' : isReviewNeeded ? 'review_required' : 'failed',
      reasonCodes: [...request.reasonCodes, 'validation_failed'],
      error: validation.reason,
    }
  }

  if (request.confidence >= CONFIDENCE_GATES.reviewRequired && request.confidence < CONFIDENCE_GATES.autoSafe) {
    return {
      searchTerm: request.searchTerm,
      customLabel0: request.customLabel0,
      currentTier: request.currentTier,
      targetTier: request.targetTier,
      status: 'review_required',
      reasonCodes: [...request.reasonCodes, 'confidence_requires_review'],
    }
  }

  if (dryRun) {
    return {
      searchTerm: request.searchTerm,
      customLabel0: request.customLabel0,
      currentTier: request.currentTier,
      targetTier: request.targetTier,
      status: 'applied',
      sheetRowUpdated: false,
      reasonCodes: [...request.reasonCodes, 'dry_run'],
    }
  }

  try {
    // 1. Log the execution action
    const actionRow = {
      action_type: 'tier_movement',
      search_term: request.searchTerm,
      custom_label_0: request.customLabel0,
      status: 'applied',
      policy_version: request.policyVersion,
      action_payload: {
        previous_tier: request.currentTier,
        new_tier: request.targetTier,
        action: request.action,
        new_label_value: deriveLabelValue(request.customLabel0, request.targetTier),
      },
      reason_codes: request.reasonCodes,
      created_by: request.requestedBy ?? null,
    }

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', [actionRow])
    const executionLogId = actionInsert.warning ? undefined : 'logged'

    // 2. Create cross-tier negative if promoting (prevent old tier from matching)
    let negativeRegistryId: string | undefined
    if (request.action === 'promote_to_medium' || request.action === 'promote_to_high' || request.action === 'negative') {
      const negativeRow = {
        term: request.searchTerm,
        scope: request.action === 'negative' ? 'global' : `shopping_${request.currentTier}`,
        source_policy: request.policyVersion,
        confidence: request.confidence,
        reason_codes: request.reasonCodes,
        active: true,
        metadata: {
          movement_from: request.currentTier,
          movement_to: request.targetTier,
          custom_label_0: request.customLabel0,
        },
        created_by: request.requestedBy ?? null,
      }

      const negativeInsert = await insertRowsSafe(supabase, 'negative_registry', [negativeRow])
      negativeRegistryId = negativeInsert.warning ? undefined : 'logged'
    }

    // 3. Update term_intent_state to reflect new tier
    await supabase
      .from('term_intent_state')
      .upsert(
        {
          search_term: request.searchTerm,
          normalized_search_term: request.searchTerm.toLowerCase().trim(),
          custom_label_0: request.customLabel0,
          intent_class: 'PRODUCT_HIGH',
          route_action: 'funnel',
          shopping_tier: request.targetTier,
          confidence: request.confidence,
          requires_review: false,
          policy_version: request.policyVersion,
          last_decided_at: new Date().toISOString(),
          metadata: {
            last_movement: request.action,
            previous_tier: request.currentTier,
          },
        },
        {
          onConflict: 'normalized_search_term,coalesce(custom_label_0,\'__all__\')',
          ignoreDuplicates: false,
        }
      )

    return {
      searchTerm: request.searchTerm,
      customLabel0: request.customLabel0,
      currentTier: request.currentTier,
      targetTier: request.targetTier,
      status: 'applied',
      executionLogId,
      negativeRegistryId,
      sheetRowUpdated: false, // Sheet update happens separately via updateSupplementalFeedTiers
      reasonCodes: [...request.reasonCodes, 'tier_movement_applied'],
    }
  } catch (error) {
    return {
      searchTerm: request.searchTerm,
      customLabel0: request.customLabel0,
      currentTier: request.currentTier,
      targetTier: request.targetTier,
      status: 'failed',
      reasonCodes: [...request.reasonCodes, 'execution_error'],
      error: extractErrorMessage(error),
    }
  }
}

export async function executeTierMovementBatch(
  supabase: SupabaseClient,
  batch: TierMovementBatchRequest,
  guardrailInput: GuardrailInput
): Promise<TierMovementBatchResult> {
  const guardrailDecision = evaluateGuardrails(guardrailInput)

  const results: TierMovementResult[] = []

  for (const movement of batch.movements) {
    const result = await executeTierMovement(
      supabase,
      { ...movement, requestedBy: movement.requestedBy ?? batch.createdBy },
      guardrailDecision.status,
      batch.dryRun
    )
    results.push(result)
  }

  return {
    results,
    appliedCount: results.filter((r) => r.status === 'applied').length,
    failedCount: results.filter((r) => r.status === 'failed').length,
    blockedCount: results.filter((r) => r.status === 'blocked').length,
    reviewRequiredCount: results.filter((r) => r.status === 'review_required').length,
    guardrailStatus: guardrailDecision.status,
    executedAt: new Date().toISOString(),
  }
}

/**
 * Update custom_label_0 values in the Google Sheets supplemental feed.
 *
 * This function updates the `custom_label_0` column (column E) for rows that match
 * the given offer IDs. It's used after tier movements to propagate tier changes
 * to the GMC supplemental feed.
 *
 * IMPORTANT: This modifies PRODUCTION data. Only call after tier movements are
 * logged to policy_action_execution_log.
 */
export async function updateSupplementalFeedTiers(
  movements: Array<{
    gmcOfferIds: string[]
    newLabelValue: string
  }>
): Promise<{ updated: number; errors: string[] }> {
  // Dynamic import to avoid pulling in googleapis when not needed
  const { getGoogleSheetsClient, getSpreadsheetId, getColumnHeaders, buildColumnMap, getExistingIds } =
    await import('@/lib/publishing/google-sheets')

  const sheets = await getGoogleSheetsClient()
  const spreadsheetId = getSpreadsheetId()
  const sheetName = 'SupplementalFeedData'

  const headers = await getColumnHeaders(sheets, spreadsheetId, sheetName)
  const columnMap = buildColumnMap(headers)
  const existingIds = await getExistingIds(sheets, spreadsheetId, sheetName)

  const customLabel0ColIdx = columnMap.custom_label_0
  if (customLabel0ColIdx === undefined) {
    return { updated: 0, errors: ['custom_label_0 column not found in sheet headers'] }
  }

  const errors: string[] = []
  let updatedCount = 0

  // Build batch update data
  const data: Array<{ range: string; values: string[][] }> = []

  for (const movement of movements) {
    for (const offerId of movement.gmcOfferIds) {
      const normalizedId = offerId.toLowerCase()
      const rowNum = existingIds.get(normalizedId)

      if (rowNum === undefined) {
        errors.push(`Offer ID ${offerId} not found in sheet`)
        continue
      }

      // Column E (index 4) = custom_label_0
      const columnLetter = String.fromCharCode(65 + customLabel0ColIdx)
      data.push({
        range: `${sheetName}!${columnLetter}${rowNum}`,
        values: [[movement.newLabelValue]],
      })
      updatedCount++
    }
  }

  if (data.length > 0) {
    await sheets.spreadsheets.values.batchUpdate({
      spreadsheetId,
      requestBody: {
        valueInputOption: 'RAW',
        data,
      },
    })
  }

  return { updated: updatedCount, errors }
}
