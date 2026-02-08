import { NextResponse } from 'next/server'
import { google } from 'googleapis'

export async function GET() {
  try {
    const spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID
    if (!spreadsheetId) {
      return NextResponse.json({ error: 'Missing GOOGLE_SHEETS_SPREADSHEET_ID' }, { status: 500 })
    }

    const sheetName = process.env.GOOGLE_SHEETS_SHEET_NAME_STAGING || 'SupplementalFeedData'

    // Initialize Google Sheets API
    const auth = new google.auth.GoogleAuth({
      credentials: JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY || '{}'),
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    })

    const sheets = google.sheets({ version: 'v4', auth })

    // Read rows 61788-61810 (the ones we just published)
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId,
      range: `${sheetName}!A61788:B61810`,
    })

    const rows = response.data.values || []

    // Analyze the data
    const hasUppercaseIds = rows.some(row => row[0]?.startsWith('shopify_US_'))
    const hasLowercaseIds = rows.some(row => row[0]?.startsWith('shopify_us_'))
    const hasMpnValues = rows.some(row => row[1]?.includes('FT-16-'))

    return NextResponse.json({
      success: true,
      rowCount: rows.length,
      sampleRows: rows.slice(0, 10).map((row, idx) => ({
        rowNumber: 61788 + idx,
        offerId: row[0] || '(empty)',
        mpn: row[1] || '(empty)',
      })),
      verification: {
        hasUppercaseIds,
        hasLowercaseIds,
        hasMpnValues,
        allChecksPassed: hasUppercaseIds && !hasLowercaseIds && hasMpnValues,
      },
    })
  } catch (error) {
    console.error('Error verifying sheets:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
