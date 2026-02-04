/**
 * Import product catalog from Acatalog.csv into Supabase
 *
 * Usage:
 *   cd dashboard
 *   npx tsx scripts/import-catalog.ts ../data/Acatalog.csv
 *
 * Prerequisites:
 *   - Run migration 008_product_catalog.sql first
 *   - Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars
 *   - npm install csv-parse (or add to package.json)
 */

import { createClient } from '@supabase/supabase-js'
import { parse } from 'csv-parse/sync'
import * as fs from 'fs'
import * as path from 'path'

// Column index mapping (0-indexed, based on CSV header order)
// Note: Columns 24-28 are PRODUCT dimensions, columns 29-32 are BOX dimensions
const COLUMN_MAP: Record<number, string> = {
  0: 'master_sku',
  1: 'option_sku',
  2: 'core_sku',
  3: 'upc',
  4: 'gtin',
  5: 'gmc_id',
  6: 'amazon_asin',
  7: 'finish_name',
  8: 'finish_code',
  9: 'position',
  10: 'category',
  11: 'collection',
  12: 'title',
  // Skip 13-15 (pricing - excluded per plan)
  16: 'narrative_copy', // CSV: "Narraive Copy" (typo)
  17: 'bullet_1',
  18: 'bullet_2',
  19: 'bullet_3',
  20: 'bullet_4',
  21: 'bullet_5',
  22: 'bullet_6',
  // First occurrence of dimensions = PRODUCT (24-28, but 0-indexed: 23-27)
  23: 'product_length',
  24: 'product_height',
  25: 'product_width',
  26: 'projection',
  27: 'product_weight',
  // Second occurrence = BOX (29-32, but 0-indexed: 28-31)
  28: 'box_length',
  29: 'box_height',
  30: 'box_width',
  31: 'box_weight',
  32: 'installation_url',
  33: 'specification_url',
  34: 'main_image_filename',
  35: 'main_image_url',
  36: 'alt_image_1',
  37: 'alt_image_2',
  38: 'alt_image_3',
  39: 'alt_image_4',
  40: 'center_to_center',
  41: 'diameter',
  42: 'screw_size',
  43: 'mirror_height',
  44: 'mirror_width',
  45: 'thickness',
  46: 'weight_capacity',
  47: 'material',
  48: 'style',
  49: 'shape',
  50: 'orientation',
  51: 'tilting',
  52: 'mounting_type',
  53: 'assembly_required',
  54: 'item_number',
  55: 'included_items',
}

// Columns that should be parsed as numeric
const NUMERIC_COLUMNS = new Set([
  'position',
  'product_length',
  'product_height',
  'product_width',
  'projection',
  'product_weight',
  'box_length',
  'box_height',
  'box_width',
  'box_weight',
  'center_to_center',
  'diameter',
  'mirror_height',
  'mirror_width',
  'thickness',
  'weight_capacity',
])

function transformRow(row: string[]): Record<string, unknown> {
  const result: Record<string, unknown> = {}

  for (const [indexStr, colName] of Object.entries(COLUMN_MAP)) {
    const index = parseInt(indexStr)
    const value = row[index]?.trim() || null

    if (value === null || value === '') {
      result[colName] = null
      continue
    }

    // Type conversions
    if (colName === 'assembly_required') {
      result[colName] = value.toLowerCase() === 'true' || value === '1'
    } else if (colName === 'position') {
      const parsed = parseInt(value)
      result[colName] = isNaN(parsed) ? null : parsed
    } else if (NUMERIC_COLUMNS.has(colName)) {
      const parsed = parseFloat(value)
      result[colName] = isNaN(parsed) ? null : parsed
    } else {
      result[colName] = value
    }
  }

  return result
}

async function importCatalog(csvPath: string) {
  // Validate environment
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!supabaseUrl || !supabaseKey) {
    console.error(
      'Error: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set'
    )
    console.error('Set these in your .env.local file or export them')
    process.exit(1)
  }

  // Resolve CSV path
  const resolvedPath = path.resolve(csvPath)
  if (!fs.existsSync(resolvedPath)) {
    console.error(`Error: CSV file not found: ${resolvedPath}`)
    process.exit(1)
  }

  console.log(`Reading CSV from: ${resolvedPath}`)
  const csvContent = fs.readFileSync(resolvedPath, 'utf-8')

  // Parse CSV (skip header row by using columns: false and slicing)
  const records: string[][] = parse(csvContent, {
    columns: false,
    skip_empty_lines: true,
    relax_column_count: true, // Handle rows with missing columns
  })

  // Skip header row
  const dataRows = records.slice(1)
  console.log(`Found ${dataRows.length} data rows to import`)

  // Create Supabase client
  const supabase = createClient(supabaseUrl, supabaseKey)

  // Verify table exists
  const { error: checkError } = await supabase
    .from('product_catalog')
    .select('id')
    .limit(1)

  if (checkError) {
    console.error('Error accessing product_catalog table:', checkError.message)
    console.error('Make sure migration 008_product_catalog.sql has been run')
    process.exit(1)
  }

  // Batch upsert for performance
  const BATCH_SIZE = 500
  let imported = 0
  let errors = 0

  for (let i = 0; i < dataRows.length; i += BATCH_SIZE) {
    const batch = dataRows.slice(i, i + BATCH_SIZE).map(transformRow)

    // Filter out rows without required fields
    const validBatch = batch.filter(
      (row) =>
        row.master_sku &&
        row.option_sku &&
        row.finish_name &&
        row.finish_code &&
        row.category &&
        row.title
    )

    if (validBatch.length !== batch.length) {
      console.warn(
        `  Skipped ${batch.length - validBatch.length} rows with missing required fields`
      )
    }

    if (validBatch.length === 0) {
      continue
    }

    const { error } = await supabase
      .from('product_catalog')
      .upsert(validBatch, { onConflict: 'option_sku' })

    if (error) {
      console.error(`Error at batch starting row ${i}:`, error.message)
      errors += validBatch.length
    } else {
      imported += validBatch.length
    }

    // Progress update every 10 batches
    if ((i / BATCH_SIZE) % 10 === 0) {
      console.log(`Progress: ${Math.min(i + BATCH_SIZE, dataRows.length)}/${dataRows.length} rows processed`)
    }
  }

  console.log('\n=== Import Complete ===')
  console.log(`Imported: ${imported} rows`)
  console.log(`Errors: ${errors} rows`)
  console.log(`Total: ${dataRows.length} rows`)

  // Verify final count
  const { count, error: countError } = await supabase
    .from('product_catalog')
    .select('*', { count: 'exact', head: true })

  if (!countError && count !== null) {
    console.log(`\nVerification: ${count} rows in product_catalog table`)
  }
}

// Run import
const csvPath = process.argv[2]
if (!csvPath) {
  console.error('Usage: npx tsx scripts/import-catalog.ts <path-to-csv>')
  console.error('Example: npx tsx scripts/import-catalog.ts ../data/Acatalog.csv')
  process.exit(1)
}

importCatalog(csvPath).catch((err) => {
  console.error('Import failed:', err)
  process.exit(1)
})
