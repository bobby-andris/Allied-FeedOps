import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { resolve } from 'path'

/**
 * Populate performance_baselines table with placeholder data
 *
 * Usage: npx tsx dashboard/scripts/populate-baselines.ts
 *
 * Note: This uses placeholder/mock data for immediate unblocking.
 * For production, integrate with Google Ads API via shopping_performance_view queries.
 */

// Load environment variables from .env.local
config({ path: resolve(__dirname, '../.env.local') })

async function populateBaselines() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase environment variables')
    console.error('Please ensure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set')
    process.exit(1)
  }

  const supabase = createClient(supabaseUrl, supabaseKey)

  const testSkus = ['CL-55', '920D-6', '7210']
  const platforms = ['google', 'bing', 'shopify'] as const

  console.log(`Populating baselines for ${testSkus.length} SKUs x ${platforms.length} platforms = ${testSkus.length * platforms.length} records\n`)

  let successCount = 0
  let errorCount = 0

  for (const masterSku of testSkus) {
    for (const platform of platforms) {
      // Generate realistic-looking placeholder data
      const baseImpressions = Math.floor(Math.random() * 1000) + 500
      const baseClicks = Math.floor(Math.random() * 50) + 20
      const ctr = baseClicks / baseImpressions
      const conversions = Math.random() * 5 + 1
      const conversionValue = Math.random() * 500 + 100
      const cost = Math.random() * 100 + 50
      const roas = cost > 0 ? conversionValue / cost : 0

      const baseline = {
        master_sku: masterSku,
        platform,
        avg_impressions: baseImpressions,
        avg_clicks: baseClicks,
        avg_ctr: ctr,
        avg_conversions: conversions,
        avg_conversion_value: conversionValue,
        avg_cost: cost,
        avg_roas: roas,
        period_days: 30,
        baseline_start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        baseline_end_date: new Date().toISOString().split('T')[0],
      }

      const { error } = await supabase
        .from('performance_baselines')
        .upsert(baseline, { onConflict: 'master_sku,platform' })

      if (error) {
        console.error(`❌ Error for ${masterSku}/${platform}:`, error.message)
        errorCount++
      } else {
        console.log(`✓ ${masterSku}/${platform}`)
        successCount++
      }
    }
  }

  console.log(`\nDone! ${successCount} successful, ${errorCount} errors`)

  // Verify data was inserted
  console.log('\nVerifying insertion...')
  const { data: verify, error: verifyError } = await supabase
    .from('performance_baselines')
    .select('master_sku, platform')
    .in('master_sku', testSkus)

  if (verifyError) {
    console.error('Verification error:', verifyError.message)
  } else {
    console.log(`Found ${verify?.length || 0} records in performance_baselines table`)
  }
}

populateBaselines()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error('Fatal error:', err)
    process.exit(1)
  })
