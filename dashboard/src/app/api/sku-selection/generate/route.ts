import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'

interface GenerateRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    images: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
    num_candidates?: number
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: GenerateRequest = await request.json()
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

    if (!options || (!options.titles && !options.descriptions && !options.images)) {
      return NextResponse.json(
        { error: 'At least one content type (titles, descriptions, or images) must be selected' },
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

    // Create batch job record
    const { data: job, error: jobError } = await supabase
      .from('batch_generation_jobs')
      .insert({
        status: 'queued',
        total_skus: skus.length,
        options: options,
      })
      .select()
      .single()

    if (jobError) {
      console.error('Failed to create batch job:', jobError)
      return NextResponse.json(
        { error: 'Failed to create generation job' },
        { status: 500 }
      )
    }

    // Insert SKU records
    const skuRecords = skus.map((sku) => ({
      job_id: job.id,
      master_sku: sku,
      status: 'pending' as const,
    }))

    const { error: skuError } = await supabase
      .from('batch_generation_job_skus')
      .insert(skuRecords)

    if (skuError) {
      console.error('Failed to create batch job SKUs:', skuError)
      // Clean up the job
      await supabase.from('batch_generation_jobs').delete().eq('id', job.id)
      return NextResponse.json(
        { error: 'Failed to queue SKUs for generation' },
        { status: 500 }
      )
    }

    // Calculate estimated time based on options
    let contentTypesCount = 0
    if (options.titles) contentTypesCount++
    if (options.descriptions) contentTypesCount++
    if (options.images) contentTypesCount += 2 // Images take longer

    const estimatedMinutes = Math.ceil(
      (skus.length * contentTypesCount * options.platforms.length * 0.5) / 60
    ) + 1

    // TODO: In production, trigger Cloud Run job or background worker here
    // For now, the job stays in 'queued' status

    return NextResponse.json({
      success: true,
      job_id: job.id,
      status: 'queued',
      total_skus: skus.length,
      estimated_minutes: Math.max(estimatedMinutes, 1),
    })
  } catch (error) {
    console.error('Generation API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
