import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function proxy(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // Check auth status
  const {
    data: { user },
  } = await supabase.auth.getUser()

  // Public routes that don't require auth
  // - /login is always public
  // - /api GET requests are public (health checks, read-only queries)
  // - /api POST/PATCH/DELETE require authentication
  // - Cron/scheduler endpoints are public (they use service role key internally)
  const isLoginPage = request.nextUrl.pathname.startsWith('/login')
  const isApiRoute = request.nextUrl.pathname.startsWith('/api')
  const isReadOnlyMethod = request.method === 'GET' || request.method === 'HEAD' || request.method === 'OPTIONS'
  const isCronEndpoint = [
    '/api/performance/capture-snapshot',
    '/api/monitoring/snapshot-capture',
    '/api/funnel-snapshots/capture',
    '/api/funnel-snapshots/backfill',
  ].includes(request.nextUrl.pathname)

  const isPublicRoute = isLoginPage || (isApiRoute && isReadOnlyMethod) || isCronEndpoint

  // If not logged in and trying to access protected route, redirect to login
  if (!user && !isPublicRoute) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  // If logged in and trying to access login page, redirect to review
  if (user && request.nextUrl.pathname === '/login') {
    const url = request.nextUrl.clone()
    url.pathname = '/review'
    return NextResponse.redirect(url)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
