import type { createClient } from '@/lib/supabase/server'
import type { PublishEventInsert } from '@/lib/publishing/types'

type SupabaseClient = Awaited<ReturnType<typeof createClient>>

interface PublishEventRowForLineage {
  id: number
  master_sku: string
  platform: string
  environment: string
  action: string
  status: string
  published_at: string | null
  batch_id: string | null
  published_by: string | null
  published_title: string | null
  published_description: string | null
  content_version: number | null
  prompt_hash: string | null
  final_payload_hash: string | null
  evidence_hash: string | null
  segment_key: string | null
}

function addDays(dateIso: string, days: number): string {
  const date = new Date(dateIso)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

function inferPublishContentType(event: PublishEventRowForLineage): string {
  const hasTitle = Boolean(event.published_title && event.published_title.trim())
  const hasDescription = Boolean(event.published_description && event.published_description.trim())
  if (hasTitle && hasDescription) return 'title_and_description'
  if (hasTitle) return 'title'
  if (hasDescription) return 'description'
  return 'metadata_only'
}

function inferGeneratedContentTypes(event: PublishEventRowForLineage): Array<'title' | 'description'> {
  const types: Array<'title' | 'description'> = []
  if (event.published_title && event.published_title.trim()) {
    types.push('title')
  }
  if (event.published_description && event.published_description.trim()) {
    types.push('description')
  }
  return types.length > 0 ? types : ['title', 'description']
}

export async function attachPublishEventLineage(
  supabase: SupabaseClient,
  publishEvent: PublishEventRowForLineage,
  originalPayload: PublishEventInsert
): Promise<void> {
  try {
    const packageKey = `publish_event:${publishEvent.id}`
    const packageSourceRef = `publish_events:${publishEvent.id}`

    const { data: packageRow, error: packageError } = await supabase
      .from('change_packages')
      .upsert(
        {
          package_key: packageKey,
          source_type: 'publish_event',
          source_ref: packageSourceRef,
          action: publishEvent.action,
          environment: publishEvent.environment,
          created_by: publishEvent.published_by,
          metadata: {
            batch_id: publishEvent.batch_id,
            publish_event_status: publishEvent.status,
          },
        },
        { onConflict: 'package_key' }
      )
      .select('id')
      .single()

    if (packageError || !packageRow?.id) {
      throw new Error(`change_packages_upsert_failed: ${packageError?.message ?? 'missing package id'}`)
    }

    const changePackageId = packageRow.id as string

    await supabase
      .from('publish_events')
      .update({ change_package_id: changePackageId })
      .eq('id', publishEvent.id)

    await supabase
      .from('change_package_events')
      .upsert(
        {
          change_package_id: changePackageId,
          publish_event_id: publishEvent.id,
          event_type: publishEvent.action || 'publish',
          metadata: {
            status: publishEvent.status,
          },
        },
        { onConflict: 'change_package_id,publish_event_id' }
      )

    await supabase
      .from('change_package_items')
      .upsert(
        {
          change_package_id: changePackageId,
          publish_event_id: publishEvent.id,
          master_sku: publishEvent.master_sku,
          platform: publishEvent.platform,
          content_type: inferPublishContentType(publishEvent),
          published_title: publishEvent.published_title,
          published_description: publishEvent.published_description,
          content_version: publishEvent.content_version,
          prompt_hash: publishEvent.prompt_hash,
          final_payload_hash: publishEvent.final_payload_hash,
          evidence_hash: publishEvent.evidence_hash,
          segment_key: publishEvent.segment_key,
          metadata: {
            batch_id: publishEvent.batch_id,
            environment: publishEvent.environment,
          },
        },
        { onConflict: 'change_package_id,master_sku,platform,content_type' }
      )

    if (publishEvent.status !== 'success' || publishEvent.action !== 'publish') {
      return
    }

    const generatedContentTypes = inferGeneratedContentTypes(publishEvent)
    const { data: generatedRows, error: generatedRowsError } = await supabase
      .from('generated_content')
      .select('id, content_type, approved_version, generation_prompt_hash')
      .eq('master_sku', publishEvent.master_sku)
      .eq('platform', publishEvent.platform)
      .in('content_type', generatedContentTypes)

    if (generatedRowsError || !generatedRows || generatedRows.length === 0) {
      // Keep publish flow non-blocking if generation rows cannot be resolved.
      return
    }

    const generatedContentIds = generatedRows
      .map((row) => row.id as string | null)
      .filter((id): id is string => Boolean(id))

    const latestHistoryByGeneratedContentId = new Map<string, { id: string; request_id: string | null }>()

    if (generatedContentIds.length > 0) {
      const { data: historyRows } = await supabase
        .from('regeneration_history')
        .select('id, generated_content_id, request_id, created_at')
        .in('generated_content_id', generatedContentIds)
        .order('created_at', { ascending: false })

      for (const row of historyRows || []) {
        const generatedContentId = row.generated_content_id as string | null
        if (!generatedContentId || latestHistoryByGeneratedContentId.has(generatedContentId)) {
          continue
        }
        latestHistoryByGeneratedContentId.set(generatedContentId, {
          id: row.id as string,
          request_id: (row.request_id as string | null) ?? null,
        })
      }
    }

    for (const generatedRow of generatedRows) {
      const generatedContentId = generatedRow.id as string | null
      if (!generatedContentId) continue

      const latestHistory = latestHistoryByGeneratedContentId.get(generatedContentId)
      await supabase
        .from('generation_outcome_links')
        .upsert(
          {
            change_package_id: changePackageId,
            publish_event_id: publishEvent.id,
            generated_content_id: generatedContentId,
            regeneration_history_id: latestHistory?.id ?? null,
            request_id: latestHistory?.request_id ?? null,
            master_sku: publishEvent.master_sku,
            platform: publishEvent.platform,
            content_type: generatedRow.content_type,
            content_version: publishEvent.content_version ?? generatedRow.approved_version ?? null,
            prompt_hash: publishEvent.prompt_hash ?? generatedRow.generation_prompt_hash ?? originalPayload.prompt_hash ?? null,
            effect_status: 'pending',
            metadata: {
              batch_id: publishEvent.batch_id,
            },
          },
          { onConflict: 'publish_event_id,content_type' }
        )
    }

    const effectStartDate = (publishEvent.published_at || new Date().toISOString()).slice(0, 10)
    const effectEndDate = addDays(`${effectStartDate}T00:00:00.000Z`, 30)

    await supabase
      .from('generation_effect_windows')
      .upsert(
        {
          change_package_id: changePackageId,
          publish_event_id: publishEvent.id,
          master_sku: publishEvent.master_sku,
          platform: publishEvent.platform,
          environment: publishEvent.environment,
          window_pre_days: 30,
          window_post_days: 30,
          effect_start_date: effectStartDate,
          effect_end_date: effectEndDate,
          metrics: {
            status: 'pending_snapshot_capture',
          },
          metadata: {
            batch_id: publishEvent.batch_id,
          },
        },
        { onConflict: 'publish_event_id,window_pre_days,window_post_days' }
      )
  } catch (error) {
    console.error('[R4] Failed to attach publish lineage:', error)
  }
}
