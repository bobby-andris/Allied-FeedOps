/**
 * Test script for hybrid multi-SKU content generation
 *
 * Usage:
 *   tsx dashboard/scripts/test-hybrid-generation.ts
 */

import { createAdminClient } from '../src/lib/supabase/admin'
import {
  detectMultiSkuFamilies,
  getRelatedMasterSkus,
  extractSpecDifference,
} from '../src/lib/multi-sku-detection'
import {
  regenerateContent,
  adaptVariantContent,
} from '../src/lib/regeneration/core'

async function testDetection() {
  console.log('\n=== Testing Multi-SKU Detection ===\n')

  const supabase = createAdminClient()

  // Test with DMF-2/2X family
  const testSku = 'DMF-2/2X'
  console.log(`Finding related SKUs for: ${testSku}`)

  const relatedSkus = await getRelatedMasterSkus(supabase, testSku)
  console.log(`Found ${relatedSkus.length} related SKUs:`, relatedSkus)

  if (relatedSkus.length > 1) {
    const { baseSpec, variantSpec } = extractSpecDifference(relatedSkus[0], relatedSkus[1])
    console.log(`\nSpec difference: ${baseSpec} → ${variantSpec}`)
  }

  // Test family detection with multiple SKUs
  const testSkus = ['DMF-2/2X', 'WP-2/16-GAL', '920D-6']
  console.log(`\nDetecting families in: [${testSkus.join(', ')}]`)

  const families = await detectMultiSkuFamilies(supabase, testSkus)
  console.log(`Found ${families.length} multi-SKU families:`)

  families.forEach((family, idx) => {
    console.log(`\nFamily ${idx + 1}:`)
    console.log(`  Product ID: ${family.productId}`)
    console.log(`  Base SKU: ${family.baseSku}`)
    console.log(`  Variant SKUs: [${family.variantSkus.join(', ')}]`)
  })
}

async function testGeneration() {
  console.log('\n=== Testing Hybrid Content Generation ===\n')

  const supabase = createAdminClient()

  // Test with a small multi-SKU family
  const baseSku = 'DMF-2/2X'
  const variantSku = 'DMF-2/3X'
  const platform = 'google' as const
  const contentType = 'title' as const

  console.log(`Step 1: Generating base content for ${baseSku}`)

  const baseResult = await regenerateContent(supabase, baseSku, platform, contentType)

  if (!baseResult.success) {
    console.error(`❌ Base generation failed: ${baseResult.error}`)
    return
  }

  console.log(`✅ Base content generated:`)
  console.log(`   "${baseResult.content}"`)
  console.log(`   Model: ${baseResult.model}`)
  console.log(`   Used evidence: ${baseResult.usedEvidence}`)

  console.log(`\nStep 2: Adapting content for variant ${variantSku}`)

  const { baseSpec, variantSpec } = extractSpecDifference(baseSku, variantSku)
  console.log(`   Spec difference: ${baseSpec} → ${variantSpec}`)

  const variantResult = await adaptVariantContent(
    supabase,
    baseSku,
    variantSku,
    platform,
    contentType,
    baseSpec,
    variantSpec
  )

  if (!variantResult.success) {
    console.error(`❌ Variant adaptation failed: ${variantResult.error}`)
    return
  }

  console.log(`✅ Variant content adapted:`)
  console.log(`   "${variantResult.content}"`)
  console.log(`   Model: ${variantResult.model}`)
  console.log(`   Mode: ${variantResult.mode}`)

  console.log(`\n=== Comparison ===`)
  console.log(`Base (${baseSku}):    "${baseResult.content}"`)
  console.log(`Variant (${variantSku}): "${variantResult.content}"`)
}

async function testFullBatch() {
  console.log('\n=== Testing Full Batch Generation ===\n')

  const supabase = createAdminClient()

  // Test with DMF-2 family (2X, 3X only for speed)
  const testSkus = ['DMF-2/2X', 'DMF-2/3X']

  console.log(`Detecting families in: [${testSkus.join(', ')}]`)

  const families = await detectMultiSkuFamilies(supabase, testSkus)

  if (families.length === 0) {
    console.log('No multi-SKU families detected (testing as single SKUs)')
    return
  }

  const family = families[0]
  console.log(`\nProcessing family:`)
  console.log(`  Base: ${family.baseSku}`)
  console.log(`  Variants: [${family.variantSkus.join(', ')}]`)

  const platforms = ['google'] as const
  const contentTypes = ['title'] as const

  // Generate base
  console.log(`\nGenerating base SKU: ${family.baseSku}`)

  for (const platform of platforms) {
    for (const contentType of contentTypes) {
      const result = await regenerateContent(supabase, family.baseSku, platform, contentType)

      if (result.success) {
        console.log(`  ✅ ${platform} ${contentType}: "${result.content?.substring(0, 60)}..."`)
      } else {
        console.log(`  ❌ ${platform} ${contentType}: ${result.error}`)
      }
    }
  }

  // Adapt variants
  for (const variantSku of family.variantSkus) {
    console.log(`\nAdapting variant SKU: ${variantSku}`)

    const { baseSpec, variantSpec } = extractSpecDifference(family.baseSku, variantSku)

    for (const platform of platforms) {
      for (const contentType of contentTypes) {
        const result = await adaptVariantContent(
          supabase,
          family.baseSku,
          variantSku,
          platform,
          contentType,
          baseSpec,
          variantSpec
        )

        if (result.success) {
          console.log(`  ✅ ${platform} ${contentType}: "${result.content?.substring(0, 60)}..."`)
        } else {
          console.log(`  ❌ ${platform} ${contentType}: ${result.error}`)
        }
      }
    }
  }

  console.log(`\n✅ Batch generation complete!`)
}

async function main() {
  const args = process.argv.slice(2)
  const mode = args[0] || 'all'

  try {
    switch (mode) {
      case 'detect':
        await testDetection()
        break
      case 'generate':
        await testGeneration()
        break
      case 'batch':
        await testFullBatch()
        break
      case 'all':
      default:
        await testDetection()
        await testGeneration()
        break
    }

    console.log('\n✅ All tests complete!\n')
  } catch (error) {
    console.error('\n❌ Test failed:', error)
    process.exit(1)
  }
}

main()
