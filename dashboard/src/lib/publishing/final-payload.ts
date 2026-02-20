import { createHash } from 'crypto'

export interface FinalVariantPayload {
  gmc_offer_id: string
  finish: string
  finish_code: string | null
  title: string
  description: string
  image_url?: string
}

export function buildGoogleFinalPayloadSnapshot(
  variants: FinalVariantPayload[],
): Record<string, unknown> {
  return {
    snapshot_version: 1,
    platform: 'google',
    variant_count: variants.length,
    variants: variants.map((variant) => ({
      gmc_offer_id: variant.gmc_offer_id,
      finish: variant.finish,
      finish_code: variant.finish_code,
      title: variant.title,
      description: variant.description,
      image_url: variant.image_url || null,
    })),
  }
}

export function buildShopifyFinalPayloadSnapshot(args: {
  shopify_product_id: string
  title: string
  description: string
}): Record<string, unknown> {
  return {
    snapshot_version: 1,
    platform: 'shopify',
    shopify_product_id: args.shopify_product_id,
    title: args.title,
    description: args.description,
  }
}

export function buildBingFinalPayloadSnapshot(args: {
  offer_ids: string[]
  title: string
  description: string
  publish_mode: 'readiness_recorded'
}): Record<string, unknown> {
  return {
    snapshot_version: 1,
    platform: 'bing',
    publish_mode: args.publish_mode,
    offer_ids: args.offer_ids,
    title: args.title,
    description: args.description,
  }
}

function stableSortObject(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => stableSortObject(item))
  }
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return Object.keys(obj)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = stableSortObject(obj[key])
        return acc
      }, {})
  }
  return value
}

export function canonicalizeForHash(value: unknown): string {
  return JSON.stringify(stableSortObject(value))
}

export function sha256Hex(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

export function hashCanonicalJson(value: unknown): string {
  return sha256Hex(canonicalizeForHash(value))
}

export function normalizeSegmentKey(value: string | null | undefined): string | null {
  const normalized = (value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
  return normalized || null
}

export function buildPublishLineageHashes(args: {
  finalPayloadSnapshot?: Record<string, unknown> | null
  promptHash?: string | null
  evidenceInput?: unknown
  segmentKey?: string | null
}): {
  final_payload_hash?: string
  prompt_hash?: string
  evidence_hash?: string
  segment_key?: string
} {
  const lineage: {
    final_payload_hash?: string
    prompt_hash?: string
    evidence_hash?: string
    segment_key?: string
  } = {}

  if (args.finalPayloadSnapshot) {
    lineage.final_payload_hash = hashCanonicalJson(args.finalPayloadSnapshot)
  }
  if (args.promptHash && args.promptHash.trim()) {
    lineage.prompt_hash = args.promptHash.trim()
  }
  if (args.evidenceInput !== undefined) {
    lineage.evidence_hash = hashCanonicalJson(args.evidenceInput)
  }
  const normalizedSegment = normalizeSegmentKey(args.segmentKey)
  if (normalizedSegment) {
    lineage.segment_key = normalizedSegment
  }

  return lineage
}
