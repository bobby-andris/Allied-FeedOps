/**
 * Evidence table builder module for enriching LLM prompts
 *
 * This module provides rich product context for the regeneration API,
 * porting the Python pipeline's evidence table logic to TypeScript.
 */

// Types
export type {
  Evidence,
  EvidenceContext,
  ProductCatalogRow,
  DesignStyleContext,
  FunctionalFeature,
  ProductEvidenceResult,
} from './types'

// Builder functions
export { buildEvidenceTable, formatEvidenceMarkdown } from './builder'

// Enrichment functions
export {
  detectDesignStyle,
  detectFunctionalFeatures,
  getRoomContext,
} from './enrichment'

// Finish metadata
export {
  FINISH_METADATA,
  getFinishMetadata,
  getFinishShortDescription,
} from './finish-metadata'
export type { FinishMeta } from './finish-metadata'

// Query helpers
export {
  getProductEvidence,
  getVariantEvidence,
  productExistsInCatalog,
  getFinishCodeFromVariantIndex,
} from './queries'

// Search query insights
export {
  getSearchQueriesForMasterSku,
  getSearchQueriesForVariant,
  formatSearchQueriesForEvidence,
  getSearchInsightsForSku,
} from './search-queries'
export type { SearchQueryInsight, VariantSearchQuery } from './search-queries'
