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

// Default column mapping for GMC supplemental feed
// Column letters map to 0-indexed positions
// Note: structured_title/structured_description are used for AI-generated content per GMC policy
const DEFAULT_COLUMN_MAP: SheetColumnMap = {
  id: 0, // Column A - offer ID (GMC ID)
  title: 1, // Column B - product title (standard)
  description: 2, // Column C - product description (standard)
  structured_title: 3, // Column D - structured title (AI-generated)
  structured_description: 4, // Column E - structured description (AI-generated)
  digital_source_type: 5, // Column F - 'trained_algorithmic_media' for AI content
  short_title: 6, // Column G - short title for Demand Gen
  lifestyle_image_link: 7, // Column H - lifestyle image URL
  custom_label_4: 8, // Column I - FeedOps tracking label
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
 * Build column name to index mapping from headers.
 */
export function buildColumnMap(headers: string[]): SheetColumnMap {
  const columnMap: SheetColumnMap = { ...DEFAULT_COLUMN_MAP }

  headers.forEach((header, idx) => {
    // Normalize header names (lowercase, strip whitespace, replace spaces with underscores)
    const normalized = header.trim().toLowerCase().replace(/\s+/g, '_')
    columnMap[normalized] = idx
  })

  return columnMap
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
  const columnLetter = String.fromCharCode(65 + idColumn)
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
      // Row numbers are 1-indexed in sheets, and we skip header, so row = i + 1
      idToRow.set(String(value), i + 1)
    }
  }

  return idToRow
}

/**
 * Convert row data dict to an array of values in column order.
 */
function rowDataToValues(
  rowData: GoogleSheetsRow,
  columnMap: SheetColumnMap,
  numColumns: number
): (string | undefined)[] {
  const values: (string | undefined)[] = new Array(numColumns).fill(undefined)

  const entries: [keyof GoogleSheetsRow, string | undefined][] = [
    ['id', rowData.id],
    ['title', rowData.title],
    ['description', rowData.description],
    ['structured_title', rowData.structured_title],
    ['structured_description', rowData.structured_description],
    ['digital_source_type', rowData.digital_source_type],
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
        const columnLetter = String.fromCharCode(65 + colIdx)
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

  // Add the column header
  const newColIdx = numColumns
  const columnLetter = String.fromCharCode(65 + newColIdx)
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

export interface PublishToGoogleSheetsResult {
  success: boolean
  updated_count: number
  appended_count: number
  total_variants: number
  errors: string[]
  offer_ids: string[]
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

    // Check for required columns
    if (columnMap.id === undefined) {
      result.errors.push("Required column 'id' not found in sheet headers")
      return result
    }

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
