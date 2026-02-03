import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { isGoogleAdsConfigured } from '@/lib/google-ads'

// Types for health check response
interface ServiceStatus {
  status: 'connected' | 'error' | 'not_configured' | 'configured'
  latency?: number
  error?: string
  [key: string]: unknown
}

interface HealthResponse {
  supabase: ServiceStatus
  googleAds: ServiceStatus
  gmc: ServiceStatus
  shopify: ServiceStatus
  googleAnalytics: ServiceStatus
}

// Timeout wrapper for async operations
async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  serviceName: string
): Promise<T> {
  const timeout = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error(`${serviceName} health check timed out after ${timeoutMs}ms`)), timeoutMs)
  })
  return Promise.race([promise, timeout])
}

// Sanitize error messages to avoid exposing sensitive details
function sanitizeError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)
  // Remove any potential credential-related info
  return message
    .replace(/key[=:]\s*["']?[^"'\s]+["']?/gi, 'key=***')
    .replace(/token[=:]\s*["']?[^"'\s]+["']?/gi, 'token=***')
    .replace(/secret[=:]\s*["']?[^"'\s]+["']?/gi, 'secret=***')
    .replace(/password[=:]\s*["']?[^"'\s]+["']?/gi, 'password=***')
    .substring(0, 200) // Truncate long messages
}

// Check Supabase connectivity
async function checkSupabase(): Promise<ServiceStatus> {
  const startTime = performance.now()
  try {
    const supabase = await createClient()
    const { error } = await supabase
      .from('sku_approvals')
      .select('count')
      .limit(1)
    
    const latency = Math.round(performance.now() - startTime)
    
    if (error) {
      return {
        status: 'error',
        latency,
        error: sanitizeError(error.message),
      }
    }
    
    return {
      status: 'connected',
      latency,
      projectId: 'qezuszwufortkiutlhym',
    }
  } catch (error) {
    return {
      status: 'error',
      latency: Math.round(performance.now() - startTime),
      error: sanitizeError(error),
    }
  }
}

// Check Google Ads configuration
async function checkGoogleAds(): Promise<ServiceStatus> {
  try {
    const configured = isGoogleAdsConfigured()
    
    if (!configured) {
      return {
        status: 'not_configured',
        error: 'Missing required Google Ads credentials',
      }
    }
    
    const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID
    
    return {
      status: 'connected',
      customerId: customerId || undefined,
    }
  } catch (error) {
    return {
      status: 'error',
      error: sanitizeError(error),
    }
  }
}

// Check Google Sheets/GMC connectivity
async function checkGoogleSheets(): Promise<ServiceStatus> {
  const startTime = performance.now()
  try {
    const base64Key = process.env.GOOGLE_SERVICE_ACCOUNT_KEY
    const spreadsheetId = process.env.GOOGLE_SHEETS_SPREADSHEET_ID
    
    if (!base64Key) {
      return {
        status: 'not_configured',
        error: 'Missing GOOGLE_SERVICE_ACCOUNT_KEY',
      }
    }
    
    if (!spreadsheetId) {
      return {
        status: 'not_configured',
        error: 'Missing GOOGLE_SHEETS_SPREADSHEET_ID',
      }
    }
    
    // Dynamically import to avoid issues if googleapis isn't installed
    const { google } = await import('googleapis')
    
    // Decode the base64 service account key
    const serviceAccountJson = Buffer.from(base64Key, 'base64').toString('utf-8')
    const credentials = JSON.parse(serviceAccountJson)
    
    // Create auth client
    const auth = new google.auth.GoogleAuth({
      credentials: {
        client_email: credentials.client_email,
        private_key: credentials.private_key,
      },
      projectId: credentials.project_id,
      scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    })
    
    const sheets = google.sheets({ version: 'v4', auth })
    
    // Simple metadata request to verify access
    const response = await sheets.spreadsheets.get({
      spreadsheetId,
      fields: 'properties.title',
    })
    
    const latency = Math.round(performance.now() - startTime)
    
    return {
      status: 'connected',
      latency,
      spreadsheetId,
      spreadsheetTitle: response.data.properties?.title,
    }
  } catch (error) {
    return {
      status: 'error',
      latency: Math.round(performance.now() - startTime),
      error: sanitizeError(error),
    }
  }
}

// Check Shopify connectivity
async function checkShopify(): Promise<ServiceStatus> {
  const startTime = performance.now()
  try {
    const storeUrl = process.env.SHOPIFY_STORE_URL
    const accessToken = process.env.SHOPIFY_ACCESS_TOKEN
    
    if (!storeUrl || !accessToken) {
      return {
        status: 'not_configured',
        error: 'Missing SHOPIFY_STORE_URL or SHOPIFY_ACCESS_TOKEN',
      }
    }
    
    // Normalize store URL
    let host = storeUrl
      .replace('https://', '')
      .replace('http://', '')
      .trim()
      .replace(/\/$/, '')
    
    const slashIndex = host.indexOf('/')
    if (slashIndex !== -1) {
      host = host.substring(0, slashIndex)
    }
    
    const endpoint = `https://${host}/admin/api/2026-01/graphql.json`
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': accessToken,
      },
      body: JSON.stringify({
        query: 'query { shop { name } }',
      }),
    })
    
    const latency = Math.round(performance.now() - startTime)
    
    if (!response.ok) {
      return {
        status: 'error',
        latency,
        error: `Shopify API returned ${response.status}`,
      }
    }
    
    const data = await response.json()
    
    if (data.errors && data.errors.length > 0) {
      return {
        status: 'error',
        latency,
        error: sanitizeError(data.errors[0].message),
      }
    }
    
    return {
      status: 'connected',
      latency,
      shopName: data.data?.shop?.name,
      storeUrl: host,
    }
  } catch (error) {
    return {
      status: 'error',
      latency: Math.round(performance.now() - startTime),
      error: sanitizeError(error),
    }
  }
}

// Check Google Analytics configuration
async function checkGoogleAnalytics(): Promise<ServiceStatus> {
  try {
    const serviceAccountKey = process.env.GOOGLE_SERVICE_ACCOUNT_KEY
    
    if (!serviceAccountKey) {
      return {
        status: 'not_configured',
        error: 'Missing GOOGLE_SERVICE_ACCOUNT_KEY',
      }
    }
    
    // GA4 property ID for Allied Brass
    // Note: No client implementation exists yet, just checking credentials
    return {
      status: 'configured',
      propertyId: 'Allied Brass - GA4 (Old)',
      note: 'Credentials available, client not implemented',
    }
  } catch (error) {
    return {
      status: 'error',
      error: sanitizeError(error),
    }
  }
}

export async function GET() {
  const TIMEOUT_MS = 5000
  
  try {
    // Run all health checks in parallel with timeouts
    const [supabase, googleAds, gmc, shopify, googleAnalytics] = await Promise.allSettled([
      withTimeout(checkSupabase(), TIMEOUT_MS, 'Supabase'),
      withTimeout(checkGoogleAds(), TIMEOUT_MS, 'Google Ads'),
      withTimeout(checkGoogleSheets(), TIMEOUT_MS, 'Google Sheets'),
      withTimeout(checkShopify(), TIMEOUT_MS, 'Shopify'),
      withTimeout(checkGoogleAnalytics(), TIMEOUT_MS, 'Google Analytics'),
    ])
    
    // Extract results, handling rejected promises
    const extractResult = (result: PromiseSettledResult<ServiceStatus>): ServiceStatus => {
      if (result.status === 'fulfilled') {
        return result.value
      }
      return {
        status: 'error',
        error: sanitizeError(result.reason),
      }
    }
    
    const response: HealthResponse = {
      supabase: extractResult(supabase),
      googleAds: extractResult(googleAds),
      gmc: extractResult(gmc),
      shopify: extractResult(shopify),
      googleAnalytics: extractResult(googleAnalytics),
    }
    
    return NextResponse.json(response)
  } catch (error) {
    return NextResponse.json(
      { error: 'Health check failed', details: sanitizeError(error) },
      { status: 500 }
    )
  }
}
