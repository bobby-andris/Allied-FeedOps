/**
 * Hybrid Multi-SKU Batch Generation
 *
 * Detects multi-SKU product families and uses hybrid approach:
 * - Base SKU: Full generation (existing pipeline)
 * - Variant SKUs: Adaptation from base content
 */

import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { ensureAllData } from '@/lib/data-collection/ensure-data'
import {
  detectMultiSkuFamilies,
  extractSpecDifference,
} from '@/lib/multi-sku-detection'
import {
  regenerateContent,
  adaptVariantContent,
  type Platform,
  type ContentType,
} from '@/lib/regeneration/core'

interface GenerateHybridRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
  }
}

interface JobStatus {
  job_id: string
  total_skus: number
  processed: number
  base_skus_generated: number
  variant_skus_adapted: number
  errors: Array<{
    sku: string
    platform: string
    content_type: string
    error: string
  }>
}

export async function POST(request: NextRequest) {
  try {
    const body: GenerateHybridRequest = await request.json()
    const { skus, options } = body

    // Validate input
    if (!skus || !Array.isArray(skus) || skus.length === 0) {
      return NextResponse.json(
        { error: 'No SKUs provided' },
        { status: 400 }
      )
    }

    if (skus.length > 100) {
      return NextResponse.json(
        { error: 'Maximum 100 SKUs per batch' },
        { status: 400 }
      )
    }

    if (!options || (!options.titles && !options.descriptions)) {
      return NextResponse.json(
        { error: 'At least one content type must be selected' },
        { status: 400 }
      )
    }

    if (!options.platforms || options.platforms.length === 0) {
      return NextResponse.json(
        { error: 'At least one platform must be selected' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()

    // Ensure data collection (non-blocking, best-effort)
    ensureAllData(skus, supabase)
      .then((result) => {
        if (result.success) {
          console.log(`Data collection triggered for ${skus.length} SKUs`, result.details)
        }
      })
      .catch((error) => {
        console.warn('Data collection background task failed:', error)
      })

    // Detect multi-SKU families
    const families = await detectMultiSkuFamilies(supabase, skus)

    // Get single-SKU products (not in any family)
    const familySkus = new Set(families.flatMap(f => f.masterSkus))
    const singleSkus = skus.filter(sku => !familySkus.has(sku))

    console.log(`Detected ${families.length} multi-SKU families and ${singleSkus.length} single SKUs`)

    // Create job record
    const jobId = `hybrid-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`

    const { data: jobData, error: jobInsertError } = await supabase
      .from('batch_generation_jobs')
      .insert({
        status: 'processing',
        total_skus: skus.length,
        completed_skus: 0,
        failed_skus: 0,
        options: {
          titles: options.titles,
          descriptions: options.descriptions,
          platforms: options.platforms,
          hybrid: true,
        },
      })
      .select()
      .single()

    if (jobInsertError || !jobData) {
      console.error('Failed to create job record:', jobInsertError)
      return NextResponse.json(
        { error: 'Failed to create generation job' },
        { status: 500 }
      )
    }

    const actualJobId = jobData.id

    // Process in background
    processHybridGeneration(
      supabase,
      actualJobId,
      families,
      singleSkus,
      options
    ).catch((error) => {
      console.error('Background generation failed:', error)
    })

    return NextResponse.json({
      success: true,
      job_id: actualJobId,
      status: 'processing',
      total_skus: skus.length,
      multi_sku_families: families.length,
      single_skus: singleSkus.length,
      strategy: {
        base_skus: families.length + singleSkus.length,
        variant_skus: families.reduce((sum, f) => sum + f.variantSkus.length, 0),
      },
    })
  } catch (error) {
    console.error('Hybrid generation API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * Background processing function
 */
async function processHybridGeneration(
  supabase: ReturnType<typeof createAdminClient>,
  jobId: string,
  families: Awaited<ReturnType<typeof detectMultiSkuFamilies>>,
  singleSkus: string[],
  options: GenerateHybridRequest['options']
) {
  const status: JobStatus = {
    job_id: jobId,
    total_skus: families.reduce((sum, f) => sum + f.masterSkus.length, 0) + singleSkus.length,
    processed: 0,
    base_skus_generated: 0,
    variant_skus_adapted: 0,
    errors: [],
  }

  const platforms = options.platforms as Platform[]
  const contentTypes: ContentType[] = []
  if (options.titles) contentTypes.push('title')
  if (options.descriptions) contentTypes.push('description')

  try {
    // Process single SKUs (full generation)
    for (const sku of singleSkus) {
      for (const platform of platforms) {
        for (const contentType of contentTypes) {
          try {
            const result = await regenerateContent(supabase, sku, platform, contentType)

            if (result.success) {
              status.base_skus_generated++
              console.log(`✓ Generated ${sku} / ${platform} / ${contentType}`)
            } else {
              status.errors.push({
                sku,
                platform,
                content_type: contentType,
                error: result.error || 'Unknown error',
              })
              console.error(`✗ Failed ${sku} / ${platform} / ${contentType}: ${result.error}`)
            }
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error)
            status.errors.push({
              sku,
              platform,
              content_type: contentType,
              error: errorMessage,
            })
            console.error(`✗ Exception for ${sku} / ${platform} / ${contentType}:`, error)
          }

          status.processed++

          // Update job progress every 5 SKUs
          if (status.processed % 5 === 0) {
            await updateJobProgress(supabase, jobId, status)
          }
        }
      }
    }

    // Process multi-SKU families (hybrid approach)
    for (const family of families) {
      console.log(`Processing family: ${family.masterSkus.join(', ')}`)

      // Step 1: Generate base SKU (full generation)
      const baseSku = family.baseSku

      for (const platform of platforms) {
        for (const contentType of contentTypes) {
          try {
            const result = await regenerateContent(supabase, baseSku, platform, contentType)

            if (result.success) {
              status.base_skus_generated++
              console.log(`✓ Generated BASE ${baseSku} / ${platform} / ${contentType}`)
            } else {
              status.errors.push({
                sku: baseSku,
                platform,
                content_type: contentType,
                error: result.error || 'Unknown error',
              })
              console.error(`✗ Failed BASE ${baseSku} / ${platform} / ${contentType}: ${result.error}`)
            }
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error)
            status.errors.push({
              sku: baseSku,
              platform,
              content_type: contentType,
              error: errorMessage,
            })
          }

          status.processed++
          await updateJobProgress(supabase, jobId, status)
        }
      }

      // Step 2: Adapt variant SKUs
      for (const variantSku of family.variantSkus) {
        const { baseSpec, variantSpec } = extractSpecDifference(baseSku, variantSku)

        for (const platform of platforms) {
          for (const contentType of contentTypes) {
            try {
              const result = await adaptVariantContent(
                supabase,
                baseSku,
                variantSku,
                platform,
                contentType,
                baseSpec,
                variantSpec
              )

              if (result.success) {
                status.variant_skus_adapted++
                console.log(`✓ Adapted VARIANT ${variantSku} / ${platform} / ${contentType} (from ${baseSku})`)
              } else {
                status.errors.push({
                  sku: variantSku,
                  platform,
                  content_type: contentType,
                  error: result.error || 'Unknown error',
                })
                console.error(`✗ Failed VARIANT ${variantSku} / ${platform} / ${contentType}: ${result.error}`)
              }
            } catch (error) {
              const errorMessage = error instanceof Error ? error.message : String(error)
              status.errors.push({
                sku: variantSku,
                platform,
                content_type: contentType,
                error: errorMessage,
              })
            }

            status.processed++
            await updateJobProgress(supabase, jobId, status)
          }
        }
      }
    }

    // Final update
    await supabase
      .from('batch_generation_jobs')
      .update({
        status: 'completed',
        completed_skus: status.processed,
        failed_skus: status.errors.length,
        completed_at: new Date().toISOString(),
      })
      .eq('id', jobId)

    console.log(`✓ Hybrid generation completed: ${status.base_skus_generated} base + ${status.variant_skus_adapted} adapted, ${status.errors.length} errors`)
  } catch (error) {
    console.error('Hybrid generation processing error:', error)

    await supabase
      .from('batch_generation_jobs')
      .update({
        status: 'failed',
        completed_skus: status.processed,
        failed_skus: status.errors.length,
        error_message: error instanceof Error ? error.message : 'Unknown error',
        completed_at: new Date().toISOString(),
      })
      .eq('id', jobId)
  }
}

/**
 * Update job progress
 */
async function updateJobProgress(
  supabase: ReturnType<typeof createAdminClient>,
  jobId: string,
  status: JobStatus
) {
  await supabase
    .from('batch_generation_jobs')
    .update({
      completed_skus: status.processed,
      failed_skus: status.errors.length,
    })
    .eq('id', jobId)
}

/**
 * GET endpoint to check job status
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const jobId = searchParams.get('job_id')

  if (!jobId) {
    return NextResponse.json(
      { error: 'job_id parameter required' },
      { status: 400 }
    )
  }

  const supabase = createAdminClient()

  const { data: jobData, error } = await supabase
    .from('batch_generation_jobs')
    .select('*')
    .eq('id', jobId)
    .maybeSingle()

  if (error || !jobData) {
    return NextResponse.json(
      { error: 'Job not found' },
      { status: 404 }
    )
  }

  return NextResponse.json({
    job_id: jobData.id,
    status: jobData.status,
    total_skus: jobData.total_skus,
    completed_skus: jobData.completed_skus,
    failed_skus: jobData.failed_skus,
    created_at: jobData.created_at,
    completed_at: jobData.completed_at,
    error: jobData.error_message,
  })
}
