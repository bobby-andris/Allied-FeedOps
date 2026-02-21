/**
 * Fetch Google Sheets SupplementalFeedData and write to a JSON file.
 *
 * Used by scripts/spot_check_propagation.py as a helper since the Python
 * google-auth library rejects the service account private key (non-standard
 * RSA modulus size), while Node.js googleapis handles it correctly.
 *
 * Uses google-auth-library (from dashboard/node_modules) to obtain a JWT
 * access token, then calls the Sheets REST API directly via fetch.
 *
 * Usage:
 *   node scripts/fetch_sheets_data.js <output_path>
 *
 * Env vars required (from .env.vercel):
 *   GOOGLE_SERVICE_ACCOUNT_KEY     - base64-encoded service account JSON
 *   GOOGLE_SHEETS_SPREADSHEET_ID   - Sheet ID (optional, defaults to production sheet)
 */

'use strict';

// Resolve google-auth-library from the dashboard's node_modules
const Module = require('module');
const _path = require('path');
const dashboardNodeModules = _path.join(__dirname, '..', 'dashboard', 'node_modules');

const GOOGLE_AUTH_LIB = _path.join(dashboardNodeModules, 'google-auth-library');
const { GoogleAuth } = require(GOOGLE_AUTH_LIB);
const fs = require('fs');

const SHEET_ID = process.env.GOOGLE_SHEETS_SPREADSHEET_ID
  || '1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg';
const SHEET_NAME = 'SupplementalFeedData';

const outputPath = process.argv[2] || '/tmp/sheets_data.json';

async function getAccessToken() {
  const b64Key = process.env.GOOGLE_SERVICE_ACCOUNT_KEY;
  if (!b64Key) throw new Error('GOOGLE_SERVICE_ACCOUNT_KEY not set');

  const decoded = Buffer.from(b64Key, 'base64').toString('utf-8');
  const creds = JSON.parse(decoded);

  const auth = new GoogleAuth({
    credentials: {
      client_email: creds.client_email,
      private_key: creds.private_key,
    },
    scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
  });

  const client = await auth.getClient();
  const tokenResp = await client.getAccessToken();
  return tokenResp.token;
}

async function sheetsGet(token, endpoint) {
  const base = 'https://sheets.googleapis.com/v4/spreadsheets';
  const url = `${base}/${SHEET_ID}${endpoint}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Sheets API ${res.status}: ${body.substring(0, 300)}`);
  }
  return res.json();
}

async function main() {
  console.log('[INFO] Authenticating with Google...');
  const token = await getAccessToken();
  console.log('[OK] Access token obtained');

  // Get sheet row count
  console.log('[INFO] Fetching sheet metadata...');
  let totalDataRows = 0;
  try {
    const meta = await sheetsGet(token, '?fields=sheets.properties');
    const ws = (meta.sheets || []).find(s => s.properties.title === SHEET_NAME);
    if (ws) {
      totalDataRows = ws.properties.gridProperties.rowCount - 1;
      console.log(`[INFO] Sheet "${SHEET_NAME}" has ~${totalDataRows} data rows`);
    }
  } catch (e) {
    console.log(`[WARN] Could not get metadata: ${e.message}`);
  }

  // Fetch all data — the Sheets API returns up to 10MB, which fits typical feed sizes
  console.log('[INFO] Fetching all sheet data (this may take a moment for large sheets)...');
  const encoded = encodeURIComponent(`${SHEET_NAME}`);
  const data = await sheetsGet(token, `/values/${encoded}?valueRenderOption=UNFORMATTED_VALUE`);
  const allRows = data.values || [];

  console.log(`[INFO] Fetched ${allRows.length} rows (including header)`);

  if (allRows.length === 0) {
    throw new Error('Sheet is empty');
  }

  // Parse headers
  const headers = allRows[0].map(h => String(h).toLowerCase().trim());
  const idCol    = headers.indexOf('id');
  const titleCol = headers.indexOf('title');
  const descCol  = headers.indexOf('description');

  console.log(`[INFO] Headers: ${JSON.stringify(headers)}`);
  console.log(`[INFO] id col=${idCol}, title col=${titleCol}, description col=${descCol}`);

  // Build offer_id -> {title, description} lookup
  const lookup = {};
  for (let i = 1; i < allRows.length; i++) {
    const row = allRows[i];
    if (!row || row[idCol] == null) continue;
    const rawId = String(row[idCol]).trim();
    if (!rawId) continue;
    const key = rawId.toLowerCase();
    lookup[key] = {
      raw_id: rawId,
      title:       titleCol >= 0 && row[titleCol] != null ? String(row[titleCol]) : '',
      description: descCol  >= 0 && row[descCol]  != null ? String(row[descCol])  : '',
    };
  }

  const result = {
    fetched_at: new Date().toISOString(),
    sheet_id: SHEET_ID,
    sheet_name: SHEET_NAME,
    total_rows: allRows.length - 1,
    headers: headers,
    col_map: { id: idCol, title: titleCol, description: descCol },
    lookup: lookup,
  };

  fs.writeFileSync(outputPath, JSON.stringify(result));
  console.log(`[OK] Sheets data written to ${outputPath} (${Object.keys(lookup).length} offer IDs indexed)`);
}

main().catch(e => {
  console.error('FATAL:', e.message);
  process.exit(1);
});
