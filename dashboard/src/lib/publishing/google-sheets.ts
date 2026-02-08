/**
 * Google Sheets integration for GMC supplemental feed updates.
 *
 * Pushes optimized product content (title, description, lifestyle images) to a Google Sheet
 * that serves as a supplemental feed for Google Merchant Center.
 *
 * Authentication uses a base64-encoded service account JSON from GOOGLE_SERVICE_ACCOUNT_KEY env var.
 */

import { google, sheets_v4 } from 'googleapis'
import type { GoogleSheetsRow, SheetColumnMap, Environment } from './types'

// DOCUMENTATION ONLY — not used at runtime. The actual column mapping is built
// dynamically from sheet headers via buildColumnMap(). These positions reflect the
// *intended* layout but may not match the real sheet. Writing to default positions
// without verifying against actual headers caused data corruption (see git blame).
//
// Actual production sheet (as of 2026-02-06):
//   A:id  B:mpn  C:product_type  D:pattern  E:custom_label_0  F:custom_label_1
//   G:custom_label_2  H:title  I:google_product_category  J:description  K:custom_label_4
//
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _REFERENCE_COLUMN_MAP: SheetColumnMap = {
  id: 0,
  title: 7,
  description: 9,
  custom_label_4: 10,
}

// Check if we should use structured-only mode (omit standard title/description)
// When true, GMC will use structured_title/structured_description exclusively
const USE_STRUCTURED_ONLY = process.env.FEEDOPS_GMC_STRUCTURED_ONLY === '1'

/**
 * Get authenticated Google Sheets client using service account credentials.
 */
export async function getGoogleSheetsClient(): Promise<sheets_v4.Sheets> {
  const base64Key = process.env.GOOGLE_SERVICE_ACCOUNT_KEY
  if (!base64Key) {
    throw new Error(
      'Missing GOOGLE_SERVICE_ACCOUNT_KEY environment variable. ' +
        'Please set it to a base64-encoded service account JSON.'
    )
  }

  // Decode the base64 service account key
  let serviceAccountJson: string
  try {
    serviceAccountJson = Buffer.from(base64Key, 'base64').toString('utf-8')
  } catch {
    throw new Error('Failed to decode GOOGLE_SERVICE_ACCOUNT_KEY from base64')
  }

  let credentials: {
    client_email: string
    private_key: string
    project_id?: string
  }
  try {
    credentials = JSON.parse(serviceAccountJson)
  } catch {
    throw new Error('Failed to parse service account JSON from GOOGLE_SERVICE_ACCOUNT_KEY')
  }

  // Create JWT auth client
  const auth = new google.auth.GoogleAuth({
    credentials: {
      client_email: credentials.client_email,
      private_key: credentials.private_key,
    },
    projectId: credentials.project_id,
    scopes: [
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/drive',
    ],
  })

  return google.sheets({ version: 'v4', auth })
}

/**
 * Get spreadsheet ID from environment variable.
 */
export function getSpreadsheetId(): string {
  const spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID
  if (!spreadsheetId) {
    throw new Error(
      'Missing GOOGLE_SHEETS_SPREADSHEET_ID environment variable.'
    )
  }
  return spreadsheetId
}

/**
 * Fetch column headers from the first row of the sheet.
 */
export async function getColumnHeaders(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  sheetName?: string
): Promise<string[]> {
  const range = sheetName ? `${sheetName}!1:1` : '1:1'

  const response = await sheets.spreadsheets.values.get({
    spreadsheetId,
    range,
  })

  const values = response.data.values
  if (!values || values.length === 0) {
    return []
  }

  return values[0].map((v) => String(v || ''))
}

/**
 * Convert a 0-based column index to Excel-style letter notation.
 * Handles multi-letter columns beyond Z (e.g., 26 → AA, 27 → AB).
 */
function columnIndexToLetter(index: number): string {
  let letter = ''
  let col = index
  while (col >= 0) {
    letter = String.fromCharCode(65 + (col % 26)) + letter
    col = Math.floor(col / 26) - 1
  }
  return letter
}

/**
 * Build column name to index mapping from actual sheet headers.
 *
 * IMPORTANT: This builds the map ONLY from headers present in the sheet.
 * Columns not found in the sheet will have undefined indices and will be
 * safely skipped during writes. This prevents writing to wrong columns
 * when the sheet layout doesn't match hardcoded assumptions.
 */
export function buildColumnMap(headers: string[]): SheetColumnMap {
  const columnMap: Record<string, number | undefined> = {}

  headers.forEach((header, idx) => {
    // Normalize header names (lowercase, strip whitespace, replace spaces with underscores)
    const normalized = header.trim().toLowerCase().replace(/\s+/g, '_')
    if (normalized) {
      columnMap[normalized] = idx
    }
  })

  return columnMap as SheetColumnMap
}

/**
 * Fetch existing offer IDs from the sheet and map them to row numbers.
 * Returns a Map of offer_id -> row_number (1-indexed).
 */
export async function getExistingIds(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  sheetName?: string,
  idColumn: number = 0
): Promise<Map<string, number>> {
  // Get the ID column letter (A = 0, B = 1, etc.)
  const columnLetter = columnIndexToLetter(idColumn)
  const range = sheetName
    ? `${sheetName}!${columnLetter}:${columnLetter}`
    : `${columnLetter}:${columnLetter}`

  const response = await sheets.spreadsheets.values.get({
    spreadsheetId,
    range,
  })

  const values = response.data.values || []
  const idToRow = new Map<string, number>()

  // Skip header row (index 0), data starts at row 2 (index 1)
  for (let i = 1; i < values.length; i++) {
    const value = values[i]?.[0]
    if (value) {
      // Normalize to lowercase for case-insensitive matching
      // (Sheet may have "shopify_US_xxx" while DB has "shopify_us_xxx")
      const normalizedId = String(value).toLowerCase()
      // Row numbers are 1-indexed in sheets, and we skip header, so row = i + 1
      idToRow.set(normalizedId, i + 1)
    }
  }

  return idToRow
}

/**
 * Build GMC compound format for structured content fields.
 * Format: trained_algorithmic_media:"content text"
 *
 * Properly escapes quotes in content text per GMC specification.
 */
function buildCompoundFormat(content: string): string {
  // Escape any existing quotes in the content
  const escapedContent = content.replace(/"/g, '\\"')
  return `trained_algorithmic_media:"${escapedContent}"`
}

/**
 * Convert row data dict to an array of values in column order.
 *
 * For structured fields, builds compound format: trained_algorithmic_media:"content"
 */
function rowDataToValues(
  rowData: GoogleSheetsRow,
  columnMap: SheetColumnMap,
  numColumns: number
): (string | undefined)[] {
  const values: (string | undefined)[] = new Array(numColumns).fill(undefined)

  // Build compound format for structured fields if present
  const structuredTitle = rowData.structured_title
    ? buildCompoundFormat(rowData.structured_title)
    : undefined

  const structuredDescription = rowData.structured_description
    ? buildCompoundFormat(rowData.structured_description)
    : undefined

  const entries: [keyof GoogleSheetsRow, string | undefined][] = [
    ['id', rowData.id],
    ['title', rowData.title],
    ['description', rowData.description],
    ['structured_title', structuredTitle],
    ['structured_description', structuredDescription],
    ['short_title', rowData.short_title],
    ['lifestyle_image_link', rowData.lifestyle_image_link],
    ['custom_label_4', rowData.custom_label_4],
  ]

  for (const [field, value] of entries) {
    const colIdx = columnMap[field]
    if (colIdx !== undefined && colIdx < numColumns && value !== undefined) {
      values[colIdx] = value
    }
  }

  return values
}

/**
 * Update existing rows in the sheet.
 */
async function updateRows(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  updates: Array<{ rowNum: number; data: GoogleSheetsRow }>,
  columnMap: SheetColumnMap,
  numColumns: number,
  sheetName?: string
): Promise<number> {
  if (updates.length === 0) return 0

  // Prepare batch update data
  const data: sheets_v4.Schema$ValueRange[] = []

  for (const { rowNum, data: rowData } of updates) {
    const values = rowDataToValues(rowData, columnMap, numColumns)

    // Update each cell individually to preserve existing values in other columns
    for (let colIdx = 0; colIdx < values.length; colIdx++) {
      if (values[colIdx] !== undefined) {
        const columnLetter = columnIndexToLetter(colIdx)
        const range = sheetName
          ? `${sheetName}!${columnLetter}${rowNum}`
          : `${columnLetter}${rowNum}`

        data.push({
          range,
          values: [[values[colIdx]]],
        })
      }
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

  return updates.length
}

/**
 * Append new rows to the sheet.
 */
async function appendRows(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  rows: GoogleSheetsRow[],
  columnMap: SheetColumnMap,
  numColumns: number,
  sheetName?: string
): Promise<number> {
  if (rows.length === 0) return 0

  const valuesList = rows.map((row) => {
    const values = rowDataToValues(row, columnMap, numColumns)
    // Replace undefined with empty string for append
    return values.map((v) => v ?? '')
  })

  const range = sheetName ? `${sheetName}!A:Z` : 'A:Z'

  await sheets.spreadsheets.values.append({
    spreadsheetId,
    range,
    valueInputOption: 'RAW',
    insertDataOption: 'INSERT_ROWS',
    requestBody: {
      values: valuesList,
    },
  })

  return rows.length
}

/**
 * Ensure the lifestyle_image_link column exists in the sheet.
 */
async function ensureLifestyleImageColumn(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  columnMap: SheetColumnMap,
  numColumns: number,
  sheetName?: string
): Promise<{ columnMap: SheetColumnMap; numColumns: number }> {
  if (columnMap.lifestyle_image_link !== undefined) {
    return { columnMap, numColumns }
  }

  // Get current sheet properties to check grid size
  const sheetMetadata = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: 'sheets(properties(title,sheetId,gridProperties))',
  })

  const targetSheet = sheetMetadata.data.sheets?.find(
    (s) => s.properties?.title === (sheetName || 'Sheet1')
  )

  const currentGridColumns = targetSheet?.properties?.gridProperties?.columnCount || 0
  const requiredColumns = numColumns + 1 // Need one more column

  // Expand grid if necessary
  if (requiredColumns > currentGridColumns && targetSheet?.properties?.sheetId !== undefined) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId,
      requestBody: {
        requests: [
          {
            appendDimension: {
              sheetId: targetSheet.properties.sheetId,
              dimension: 'COLUMNS',
              length: requiredColumns - currentGridColumns,
            },
          },
        ],
      },
    })
  }

  // Add the column header
  const newColIdx = numColumns
  const columnLetter = columnIndexToLetter(newColIdx)
  const range = sheetName ? `${sheetName}!${columnLetter}1` : `${columnLetter}1`

  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range,
    valueInputOption: 'RAW',
    requestBody: {
      values: [['lifestyle_image_link']],
    },
  })

  return {
    columnMap: { ...columnMap, lifestyle_image_link: newColIdx },
    numColumns: numColumns + 1,
  }
}

/**
 * Ensure structured_title and structured_description columns exist in the sheet.
 * These columns are required for GMC AI content disclosure compliance.
 *
 * Adds both columns at the end of the sheet if they don't exist.
 */
async function ensureStructuredColumns(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  columnMap: SheetColumnMap,
  numColumns: number,
  sheetName?: string
): Promise<{ columnMap: SheetColumnMap; numColumns: number }> {
  const needsStructuredTitle = columnMap.structured_title === undefined
  const needsStructuredDescription = columnMap.structured_description === undefined

  // If both columns exist, return unchanged
  if (!needsStructuredTitle && !needsStructuredDescription) {
    return { columnMap, numColumns }
  }

  // Build batch update for missing columns
  const updates: { column: string; index: number }[] = []
  let currentColIdx = numColumns

  if (needsStructuredTitle) {
    updates.push({ column: 'structured_title', index: currentColIdx })
    currentColIdx++
  }

  if (needsStructuredDescription) {
    updates.push({ column: 'structured_description', index: currentColIdx })
    currentColIdx++
  }

  // Get current sheet properties to check grid size
  const sheetMetadata = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: 'sheets(properties(title,sheetId,gridProperties))',
  })

  const targetSheet = sheetMetadata.data.sheets?.find(
    (s) => s.properties?.title === (sheetName || 'Sheet1')
  )

  const currentGridColumns = targetSheet?.properties?.gridProperties?.columnCount || 0
  const requiredColumns = currentColIdx // currentColIdx is already the total needed

  // Expand grid if necessary
  if (requiredColumns > currentGridColumns && targetSheet?.properties?.sheetId !== undefined) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId,
      requestBody: {
        requests: [
          {
            appendDimension: {
              sheetId: targetSheet.properties.sheetId,
              dimension: 'COLUMNS',
              length: requiredColumns - currentGridColumns,
            },
          },
        ],
      },
    })
  }

  // Add column headers in batch
  const data: sheets_v4.Schema$ValueRange[] = updates.map(({ column, index }) => {
    const columnLetter = columnIndexToLetter(index)
    const range = sheetName ? `${sheetName}!${columnLetter}1` : `${columnLetter}1`
    return {
      range,
      values: [[column]],
    }
  })

  await sheets.spreadsheets.values.batchUpdate({
    spreadsheetId,
    requestBody: {
      valueInputOption: 'RAW',
      data,
    },
  })

  // Update column map with new indices
  const updatedColumnMap = { ...columnMap }
  for (const { column, index } of updates) {
    updatedColumnMap[column] = index
  }

  return {
    columnMap: updatedColumnMap,
    numColumns: currentColIdx,
  }
}

export interface PublishToGoogleSheetsResult {
  success: boolean
  updated_count: number
  appended_count: number
  total_variants: number
  errors: string[]
  offer_ids: string[]
}

/**
 * A variant with its own expanded title and description.
 * Used for per-variant publishing where {FINISH_NAME} has been replaced.
 */
export interface ExpandedVariantRow {
  gmc_offer_id: string
  master_sku: string
  finish_code: string | null
  title: string
  description: string
  image_url?: string
}

/**
 * Publish content to Google Sheets supplemental feed for a single SKU.
 *
 * For each offer ID provided, this function:
 * 1. Checks if the offer ID already exists in the sheet
 * 2. Updates the existing row if found
 * 3. Appends a new row if not found
 */
export async function publishToGoogleSheets(
  offerIds: string[],
  title: string,
  description: string,
  environment: Environment,
  imageUrl?: string,
  sheetName?: string
): Promise<PublishToGoogleSheetsResult> {
  const result: PublishToGoogleSheetsResult = {
    success: false,
    updated_count: 0,
    appended_count: 0,
    total_variants: 0,
    errors: [],
    offer_ids: offerIds,
  }

  if (offerIds.length === 0) {
    result.errors.push('No offer IDs provided')
    return result
  }

  const trackingLabel = `feedops-${environment}`

  try {
    const sheets = await getGoogleSheetsClient()
    const spreadsheetId = getSpreadsheetId()

    // Get existing IDs from the sheet
    const existingIds = await getExistingIds(sheets, spreadsheetId, sheetName)

    // Get column headers and build mapping
    const headers = await getColumnHeaders(sheets, spreadsheetId, sheetName)
    let columnMap = buildColumnMap(headers)
    let numColumns = headers.length

    // Ensure lifestyle_image_link column exists
    const ensured = await ensureLifestyleImageColumn(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensured.columnMap
    numColumns = ensured.numColumns

    // Ensure structured columns exist
    const ensuredStructured = await ensureStructuredColumns(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensuredStructured.columnMap
    numColumns = ensuredStructured.numColumns

    // Check for required columns
    if (columnMap.id === undefined) {
      result.errors.push("Required column 'id' not found in sheet headers")
      return result
    }

    // Log column mapping for debugging
    console.log('[publishToGoogleSheets] Column mapping from sheet headers:', {
      id: columnMap.id,
      title: columnMap.title,
      description: columnMap.description,
      structured_title: columnMap.structured_title,
      structured_description: columnMap.structured_description,
      lifestyle_image_link: columnMap.lifestyle_image_link,
      custom_label_4: columnMap.custom_label_4,
      numColumns,
    })

    // Build rows from offer IDs
    const rowsToUpdate: Array<{ rowNum: number; data: GoogleSheetsRow }> = []
    const rowsToAppend: GoogleSheetsRow[] = []

    for (const offerId of offerIds) {
      result.total_variants++

      // Build row data per GMC AI content disclosure policy:
      // - Always set structured_title/structured_description for AI-generated content
      // - Set digital_source_type to indicate AI-generated content
      // - If FEEDOPS_GMC_STRUCTURED_ONLY=1, omit standard title/description
      //   (otherwise GMC ignores structured fields when standard fields are present)
      const rowData: GoogleSheetsRow = {
        id: offerId,
        // Standard fields - omit if structured-only mode
        title: USE_STRUCTURED_ONLY ? undefined : title,
        description: USE_STRUCTURED_ONLY ? undefined : description,
        // Structured fields - always set for AI-generated content
        structured_title: title,
        structured_description: description,
        digital_source_type: 'trained_algorithmic_media',
        // Other fields
        custom_label_4: trackingLabel,
        lifestyle_image_link: imageUrl,
      }

      const existingRow = existingIds.get(offerId)
      if (existingRow !== undefined) {
        rowsToUpdate.push({ rowNum: existingRow, data: rowData })
      } else {
        rowsToAppend.push(rowData)
      }
    }

    // Execute updates
    if (rowsToUpdate.length > 0) {
      const updated = await updateRows(
        sheets,
        spreadsheetId,
        rowsToUpdate,
        columnMap,
        numColumns,
        sheetName
      )
      result.updated_count = updated
    }

    // Execute appends
    if (rowsToAppend.length > 0) {
      const appended = await appendRows(
        sheets,
        spreadsheetId,
        rowsToAppend,
        columnMap,
        numColumns,
        sheetName
      )
      result.appended_count = appended
    }

    result.success = true
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    result.errors.push(`Google Sheets API error: ${message}`)
  }

  return result
}

/**
 * Publish expanded variants to Google Sheets supplemental feed.
 *
 * Unlike publishToGoogleSheets, this function accepts variants that have already
 * been expanded (each with their own unique title and description).
 *
 * This is the preferred method for publishing when using {FINISH_NAME} templates
 * since each variant gets its own finish-specific content.
 */
export async function publishExpandedVariantsToGoogleSheets(
  variants: ExpandedVariantRow[],
  environment: Environment,
  sheetName?: string
): Promise<PublishToGoogleSheetsResult> {
  const result: PublishToGoogleSheetsResult = {
    success: false,
    updated_count: 0,
    appended_count: 0,
    total_variants: 0,
    errors: [],
    offer_ids: variants.map((v) => v.gmc_offer_id),
  }

  if (variants.length === 0) {
    result.errors.push('No variants provided')
    return result
  }

  const trackingLabel = `feedops-${environment}`

  try {
    const sheets = await getGoogleSheetsClient()
    const spreadsheetId = getSpreadsheetId()

    // Get existing IDs from the sheet
    const existingIds = await getExistingIds(sheets, spreadsheetId, sheetName)

    // Get column headers and build mapping
    const headers = await getColumnHeaders(sheets, spreadsheetId, sheetName)
    let columnMap = buildColumnMap(headers)
    let numColumns = headers.length

    // Ensure lifestyle_image_link column exists
    const ensured = await ensureLifestyleImageColumn(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensured.columnMap
    numColumns = ensured.numColumns

    // Ensure structured columns exist
    const ensuredStructured = await ensureStructuredColumns(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensuredStructured.columnMap
    numColumns = ensuredStructured.numColumns

    // Check for required columns
    if (columnMap.id === undefined) {
      result.errors.push("Required column 'id' not found in sheet headers")
      return result
    }

    // Log column mapping for debugging
    console.log('[publishExpandedVariants] Column mapping from sheet headers:', {
      id: columnMap.id,
      title: columnMap.title,
      description: columnMap.description,
      structured_title: columnMap.structured_title,
      structured_description: columnMap.structured_description,
      lifestyle_image_link: columnMap.lifestyle_image_link,
      custom_label_4: columnMap.custom_label_4,
      numColumns,
      totalVariants: variants.length,
    })

    // Build rows from variants - each variant has its OWN title/description
    const rowsToUpdate: Array<{ rowNum: number; data: GoogleSheetsRow }> = []
    const rowsToAppend: GoogleSheetsRow[] = []

    for (const variant of variants) {
      result.total_variants++

      // Normalize to lowercase for case-insensitive lookup
      const existingRow = existingIds.get(variant.gmc_offer_id.toLowerCase())
      const isNewRow = existingRow === undefined

      // Build row data per GMC AI content disclosure policy
      const rowData: GoogleSheetsRow = {
        // Transform to GMC format: shopify_US_ (uppercase) not shopify_us_ (lowercase)
        id: variant.gmc_offer_id.replace('shopify_us_', 'shopify_US_'),
        // MPN (Manufacturer Part Number): Only set for NEW rows (not updates)
        mpn: isNewRow && variant.finish_code ? `${variant.master_sku}-${variant.finish_code}` : undefined,
        // Standard fields - omit if structured-only mode
        title: USE_STRUCTURED_ONLY ? undefined : variant.title,
        description: USE_STRUCTURED_ONLY ? undefined : variant.description,
        // Structured fields - always set for AI-generated content
        structured_title: variant.title,
        structured_description: variant.description,
        digital_source_type: 'trained_algorithmic_media',
        // Other fields
        custom_label_4: trackingLabel,
        lifestyle_image_link: variant.image_url,
      }

      if (isNewRow) {
        rowsToAppend.push(rowData)
      } else {
        rowsToUpdate.push({ rowNum: existingRow, data: rowData })
      }
    }

    // Execute updates
    if (rowsToUpdate.length > 0) {
      const updated = await updateRows(
        sheets,
        spreadsheetId,
        rowsToUpdate,
        columnMap,
        numColumns,
        sheetName
      )
      result.updated_count = updated
    }

    // Execute appends
    if (rowsToAppend.length > 0) {
      const appended = await appendRows(
        sheets,
        spreadsheetId,
        rowsToAppend,
        columnMap,
        numColumns,
        sheetName
      )
      result.appended_count = appended
    }

    result.success = true
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    result.errors.push(`Google Sheets API error: ${message}`)
  }

  return result
}
