# Task: Production Readiness Audit

## Objective

Comprehensive audit to ensure the FeedOps dashboard is production-ready, secure, and performs well.

## Context

**Live URL:** https://allied-feed-ops.vercel.app
**Repository:** Allied-FeedOps
**Stack:** Next.js 14+, Supabase, Vercel

## Phase 1: Security Audit

### 1.1 Authentication & Authorization

**Check middleware protection:**
```typescript
// File: dashboard/src/middleware.ts
// Verify POST/PATCH/DELETE routes require auth
```

**Verification steps:**
1. Test unauthenticated POST to `/api/regenerate` - should return 401
2. Test unauthenticated POST to `/api/publish/*` - should return 401
3. Test unauthenticated GET to `/api/stats` - should work (read-only)
4. Verify session handling works correctly

**Expected middleware pattern:**
```typescript
const isPublicRoute =
  isLoginPage ||
  (isApiRoute && isReadOnlyMethod)
```

### 1.2 Environment Variables

**Audit for exposed secrets:**
- [ ] No API keys in client-side code
- [ ] No secrets in git history
- [ ] Vercel environment variables properly scoped (Production/Preview/Development)

**Required server-only variables:**
```
OPENAI_API_KEY
GOOGLE_SERVICE_ACCOUNT_KEY
SUPABASE_SERVICE_ROLE_KEY
SHOPIFY_ACCESS_TOKEN
```

**Client-safe variables (NEXT_PUBLIC_*):**
```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### 1.3 API Input Validation

**Check all POST/PATCH routes for:**
- Input validation (Zod recommended)
- SQL injection prevention (parameterized queries)
- XSS prevention (sanitize user inputs)
- Rate limiting consideration

**Example validation pattern:**
```typescript
import { z } from 'zod'

const schema = z.object({
  master_sku: z.string().min(1).max(50),
  feedback: z.string().max(1000).optional(),
})

const parsed = schema.safeParse(body)
if (!parsed.success) {
  return NextResponse.json({ error: parsed.error }, { status: 400 })
}
```

### 1.4 CORS & Headers

**Verify security headers in next.config.js:**
```javascript
const securityHeaders = [
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
]
```

## Phase 2: Performance Audit

### 2.1 Build Analysis

```bash
cd dashboard
npm run build

# Check bundle sizes
npx @next/bundle-analyzer
```

**Target metrics:**
- First Load JS < 100KB per route
- No duplicate dependencies
- Dynamic imports for heavy components (charts)

### 2.2 Database Query Optimization

**Audit Supabase queries for:**
- Proper indexing used
- No N+1 query patterns
- Pagination for large datasets
- Select only needed columns

**Example optimized query:**
```typescript
// Bad
const { data } = await supabase.from('sku_approvals').select('*')

// Good
const { data } = await supabase
  .from('sku_approvals')
  .select('master_sku, approval_status, approved_at')
  .eq('approval_status', 'pending')
  .order('created_at', { ascending: false })
  .limit(50)
```

### 2.3 Caching Strategy

**Implement caching for:**
- Static API responses (stats that don't change frequently)
- User session data
- Expensive computations

**Example with Next.js caching:**
```typescript
export async function GET() {
  return NextResponse.json(data, {
    headers: {
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300'
    }
  })
}
```

### 2.4 Image Optimization

**Check for:**
- Using next/image for all images
- Proper width/height or fill
- Lazy loading for below-fold images
- WebP/AVIF format support

## Phase 3: Error Handling & Monitoring

### 3.1 Error Boundaries

**Add error boundaries to:**
- Dashboard layout
- Chart components
- Data fetching components

**Example:**
```typescript
'use client'

export function ChartErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallback={<div className="p-4 text-red-500">Failed to load chart</div>}
    >
      {children}
    </ErrorBoundary>
  )
}
```

### 3.2 API Error Responses

**Standardize error responses:**
```typescript
interface ApiError {
  error: string
  code?: string
  details?: unknown
}

// Consistent error handling
try {
  // ... operation
} catch (error) {
  console.error('Operation failed:', error)
  return NextResponse.json(
    { error: 'Operation failed', code: 'INTERNAL_ERROR' },
    { status: 500 }
  )
}
```

### 3.3 Logging

**Add structured logging for:**
- API requests (method, path, duration, status)
- Database operations
- External API calls (OpenAI, Google Ads)
- Errors with stack traces

**Consider Vercel's logging or external service:**
- Vercel Logs (built-in)
- LogRocket / Sentry for frontend
- Datadog / New Relic for backend

## Phase 4: Accessibility Audit

### 4.1 WCAG Compliance

**Check for:**
- [ ] Proper heading hierarchy (h1 → h2 → h3)
- [ ] Alt text on images
- [ ] Form labels and ARIA attributes
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] Color contrast ratio ≥ 4.5:1

**Tools:**
- Chrome DevTools Lighthouse
- axe DevTools extension
- WAVE Web Accessibility Evaluator

### 4.2 Responsive Design

**Test on:**
- Desktop (1920x1080, 1440x900)
- Tablet (768x1024)
- Mobile (375x667, 390x844)

**Check:**
- Tables scroll horizontally on mobile
- Modals/dialogs are usable
- Touch targets ≥ 44px
- No horizontal overflow

## Phase 5: Testing

### 5.1 Unit Tests (if not present)

**Priority areas for testing:**
- SKU scoring algorithm
- API route handlers
- Utility functions

```bash
# Install testing dependencies
npm install -D vitest @testing-library/react @testing-library/jest-dom

# Run tests
npm test
```

### 5.2 E2E Tests (recommended)

**Using Playwright:**
```bash
npm install -D @playwright/test
npx playwright install
```

**Critical paths to test:**
1. Login flow
2. SKU review and approval
3. Batch creation
4. Content regeneration
5. Publishing flow

### 5.3 Manual QA Checklist

**Authentication:**
- [ ] Login works with valid credentials
- [ ] Login fails gracefully with invalid credentials
- [ ] Session persists across page refreshes
- [ ] Logout works correctly

**Review Flow:**
- [ ] SKU list loads with data
- [ ] Clicking SKU navigates to detail page
- [ ] Content comparison displays correctly
- [ ] Approve/Reject buttons work
- [ ] Regenerate modal opens and submits

**Batch Management:**
- [ ] Batch list displays
- [ ] Create batch modal works
- [ ] SKUs can be added to batch
- [ ] Batch can be executed

**Publishing:**
- [ ] Publish to staging works
- [ ] Publish to production works
- [ ] Publish history shows events

**Settings:**
- [ ] API health statuses display
- [ ] Connected services show green
- [ ] Error states show red with message

## Phase 6: Documentation

### 6.1 README Updates

**Ensure README.md includes:**
- Project description
- Setup instructions
- Environment variables needed
- Development commands
- Deployment process

### 6.2 API Documentation

**Document all API routes:**

| Route | Method | Description | Auth Required |
|-------|--------|-------------|---------------|
| `/api/health` | GET | Health check | No |
| `/api/stats` | GET | Dashboard stats | No |
| `/api/content/[sku]` | GET | Get SKU content | No |
| `/api/regenerate` | POST | Regenerate content | Yes |
| `/api/publish/*` | POST | Publish content | Yes |
| `/api/batches` | GET/POST | Batch management | Yes |

### 6.3 Runbook

**Create operational runbook covering:**
- How to deploy updates
- How to rollback
- How to handle common errors
- Contact info for escalation

## Phase 7: Pre-Launch Checklist

### 7.1 Infrastructure

- [ ] Vercel project configured correctly
- [ ] Custom domain set up (if applicable)
- [ ] SSL certificate valid
- [ ] Environment variables set for production

### 7.2 Database

- [ ] All migrations applied
- [ ] Indexes created for common queries
- [ ] Row-level security policies reviewed
- [ ] Backup strategy confirmed

### 7.3 Monitoring

- [ ] Uptime monitoring configured
- [ ] Error alerting set up
- [ ] Performance monitoring enabled
- [ ] Log retention policy defined

### 7.4 Compliance

- [ ] No PII exposure risks
- [ ] Cookie consent if needed
- [ ] Privacy policy updated
- [ ] Terms of service updated

## Success Criteria

1. [ ] All security checks pass
2. [ ] Lighthouse performance score ≥ 80
3. [ ] Lighthouse accessibility score ≥ 90
4. [ ] No TypeScript errors
5. [ ] No console errors in production
6. [ ] All manual QA items checked
7. [ ] Documentation complete
8. [ ] Monitoring in place

## Rollback Plan

If issues are discovered post-launch:

1. **Vercel Rollback:**
   ```bash
   # List deployments
   vercel ls

   # Rollback to previous
   vercel rollback [deployment-url]
   ```

2. **Database Rollback:**
   - Use Supabase point-in-time recovery
   - Or restore from backup

3. **Communication:**
   - Notify stakeholders
   - Update status page (if applicable)
