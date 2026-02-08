/**
 * Verification script to read published data from Google Sheets
 *
 * Usage: npx tsx verify-sheets-data.ts
 */

import { google } from 'googleapis'

async function verifyPublishedData() {
  const spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID
  if (!spreadsheetId) {
    throw new Error('Missing GOOGLE_SHEETS_SPREADSHEET_ID')
  }

  const sheetName = process.env.GOOGLE_SHEETS_SHEET_NAME_STAGING || 'SupplementalFeedData'

  // Initialize Google Sheets API
  const auth = new google.auth.GoogleAuth({
    credentials: JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY || '{}'),
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  })

  const sheets = google.sheets({ version: 'v4', auth })

  // Read the first 70000 rows to find our data
  console.log('Reading sheet data...')
  const response = await sheets.spreadsheets.values.get({
    spreadsheetId,
    range: `${sheetName}!A61788:B61810`, // Target the rows we just added
  })

  const rows = response.data.values || []

  console.log('\nSample of published rows:')
  console.log('Row | Offer ID | MPN')
  console.log('--- | -------- | ---')

  rows.slice(0, 15).forEach((row, idx) => {
    const rowNum = 61788 + idx
    const offerId = row[0] || '(empty)'
    const mpn = row[1] || '(empty)'
    console.log(`${rowNum} | ${offerId} | ${mpn}`)
  })

  // Verify format
  console.log('\nVerification:')
  const hasUppercaseIds = rows.some(row => row[0]?.startsWith('shopify_US_'))
  const hasLowercaseIds = rows.some(row => row[0]?.startsWith('shopify_us_'))
  const hasMpnValues = rows.some(row => row[1]?.includes('FT-16-'))

  console.log(`✓ Has uppercase IDs (shopify_US_): ${hasUppercaseIds}`)
  console.log(`✗ Has lowercase IDs (shopify_us_): ${hasLowercaseIds}`)
  console.log(`✓ Has MPN values (FT-16-*): ${hasMpnValues}`)

  if (hasUppercaseIds && !hasLowercaseIds && hasMpnValues) {
    console.log('\n✅ All checks passed!')
  } else {
    console.log('\n❌ Some checks failed')
  }
}

verifyPublishedData().catch(console.error)
