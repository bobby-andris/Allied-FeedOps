/**
 * One-time script to delete the 920D-6 rows that were incorrectly appended
 * to the Google Sheet due to the case-sensitivity bug.
 *
 * Run with: npx tsx scripts/delete-920d6-rows.ts
 */

import { google } from 'googleapis'

const SPREADSHEET_ID = '1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg'
const SHEET_NAME = 'SupplementalFeedData'

// 920D-6 offer IDs that need to be deleted (25 total)
const OFFER_IDS_TO_DELETE = [
  'shopify_us_4538762494084_32096757612676',
  'shopify_us_4538762494084_32096757645444',
  'shopify_us_4538762494084_32096757678212',
  'shopify_us_4538762494084_32096757710980',
  'shopify_us_4538762494084_32096757743748',
  'shopify_us_4538762494084_32096757776516',
  'shopify_us_4538762494084_32096757809284',
  'shopify_us_4538762494084_32096757842052',
  'shopify_us_4538762494084_32096757874820',
  'shopify_us_4538762494084_32096757907588',
  'shopify_us_4538762494084_32096757940356',
  'shopify_us_4538762494084_32096757973124',
  'shopify_us_4538762494084_32096758005892',
  'shopify_us_4538762494084_32096758038660',
  'shopify_us_4538762494084_32096758071428',
  'shopify_us_4538762494084_32096758104196',
  'shopify_us_4538762494084_32096758136964',
  'shopify_us_4538762494084_43099054342370',
  'shopify_us_4538762494084_43099054375138',
  'shopify_us_4538762494084_43099054407906',
  'shopify_us_4538762494084_43099054440674',
  'shopify_us_4538762494084_43099054473442',
  'shopify_us_4538762494084_43099054506210',
  'shopify_us_4538762494084_43099054538978',
  'shopify_us_4538762494084_43099054571746',
]

async function deleteRows() {
  // Authenticate
  const serviceAccountKey = process.env.GOOGLE_SERVICE_ACCOUNT_KEY
  if (!serviceAccountKey) {
    throw new Error('GOOGLE_SERVICE_ACCOUNT_KEY environment variable is required')
  }

  const credentials = JSON.parse(Buffer.from(serviceAccountKey, 'base64').toString('utf-8'))
  const auth = new google.auth.GoogleAuth({
    credentials,
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  })

  const sheets = google.sheets({ version: 'v4', auth })

  // Get all IDs from column A
  console.log('Reading all offer IDs from sheet...')
  const response = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: `${SHEET_NAME}!A:A`,
  })

  const values = response.data.values || []
  const rowsToDelete: number[] = []

  // Find rows containing the 920D-6 offer IDs (case-insensitive)
  for (let i = 1; i < values.length; i++) {
    const cellValue = values[i]?.[0]
    if (cellValue) {
      const normalizedValue = String(cellValue).toLowerCase()
      if (OFFER_IDS_TO_DELETE.includes(normalizedValue)) {
        rowsToDelete.push(i) // 0-indexed in array, will convert to sheet index
      }
    }
  }

  console.log(`Found ${rowsToDelete.length} rows to delete:`, rowsToDelete.slice(0, 5).map(i => i + 1), '...')

  if (rowsToDelete.length === 0) {
    console.log('No rows found to delete. They may have already been removed.')
    return
  }

  // Get sheet ID
  const sheetMetadata = await sheets.spreadsheets.get({
    spreadsheetId: SPREADSHEET_ID,
    fields: 'sheets(properties(title,sheetId))',
  })

  const targetSheet = sheetMetadata.data.sheets?.find(
    (s) => s.properties?.title === SHEET_NAME
  )

  if (!targetSheet?.properties?.sheetId) {
    throw new Error(`Sheet "${SHEET_NAME}" not found`)
  }

  const sheetId = targetSheet.properties.sheetId

  // Delete rows in reverse order (from bottom to top) to avoid index shifting
  console.log('Deleting rows...')
  const requests = rowsToDelete
    .sort((a, b) => b - a) // Sort descending
    .map((rowIndex) => ({
      deleteDimension: {
        range: {
          sheetId,
          dimension: 'ROWS',
          startIndex: rowIndex, // 0-indexed
          endIndex: rowIndex + 1, // Exclusive
        },
      },
    }))

  await sheets.spreadsheets.batchUpdate({
    spreadsheetId: SPREADSHEET_ID,
    requestBody: { requests },
  })

  console.log(`✅ Successfully deleted ${rowsToDelete.length} rows for 920D-6`)
}

deleteRows().catch((error) => {
  console.error('Error deleting rows:', error)
  process.exit(1)
})
