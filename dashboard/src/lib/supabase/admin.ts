import { createClient } from '@supabase/supabase-js'

/**
 * Server-side admin Supabase client (service role).
 *
 * Use this for privileged writes from API routes so we don't depend on
 * browser auth cookies or permissive RLS in production.
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!url) {
    throw new Error(
      'Missing Supabase env var: NEXT_PUBLIC_SUPABASE_URL'
    )
  }

  // Intentionally untyped: our hand-written `Database` type doesn't conform
  // to supabase-js's strict generated-type shape (relationships, etc.).
  // Prefer service role for server-side writes; fall back to anon in local/dev.
  const key = serviceRoleKey || anonKey

  if (!key) {
    throw new Error(
      'Missing Supabase env vars (NEXT_PUBLIC_SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY)'
    )
  }

  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
}

