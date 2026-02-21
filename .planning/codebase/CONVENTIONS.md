# Coding Conventions

**Analysis Date:** 2026-02-20

## Naming Patterns

**Files:**
- Components: PascalCase with `.tsx` extension (e.g., `SkuReviewClient.tsx`, `ManualTitleEditor.tsx`)
- Utility/business logic: kebab-case or camelCase with `.ts` extension (e.g., `baseline-capture.ts`, `approval-copy.ts`)
- Route handlers: Lowercase with descriptive names in `/api/` paths (e.g., `route.ts` in `/api/regenerate/`)
- Test files: Adjacent to source with `.test.ts` or `.test.tsx` suffix (e.g., `PublishButton.test.tsx`)
- Hooks: camelCase with `use` prefix (e.g., `usePerformanceData.ts`)

**Functions:**
- camelCase: `buildEvidenceTable()`, `captureBaseline()`, `fetchShoppingPerformance()`, `composeTemplateTitle()`
- Private/internal: Underscore prefix for module scope only (not functions exported), e.g., `_openai` for module variable
- Factory functions: `create*` or `build*` pattern (e.g., `createAdminClient()`, `buildEvidenceTable()`)
- Type guards: `is*` or `*Exists` pattern (e.g., `productExistsInCatalog()`)
- Async operations: Standard camelCase, no special prefix (e.g., `fetchShoppingPerformance()`)

**Variables:**
- Mutable state: camelCase (e.g., `selectedPlatform`, `isSaving`, `errorMessage`)
- Constants: UPPER_SNAKE_CASE (e.g., `INCH_FIELDS`, `FINISH_LIST`, `PLATFORM_CONTEXT`, `USE_VISION`)
- Type guards return `boolean`: Use `is*`, `*Exists`, `has*` prefix (e.g., `productExistsInCatalog()`)
- Lazy initialization: Use `_module` private variable pattern with getter (e.g., `_openai` with `getOpenAIClient()`)

**Types:**
- Interfaces/Types: PascalCase with optional suffix (e.g., `RegenerationResult`, `PublishBatch`, `FeedbackPreset`)
- Type from database/external: Suffix with row type if needed (e.g., `Ga4CampaignRow`, `ProductCatalogRow`)
- Props interfaces: `{ComponentName}Props` (e.g., `ManualTitleEditorProps`)
- Union types: Use discriminated unions with explicit literal types (e.g., `status: 'draft' | 'pending' | 'executing'`)

**Error/Response types:**
- Response/Error interfaces: Use `SaveResponse`, `RegenerationResult`, or simply follow response context

## Code Style

**Formatting:**
- Tool: ESLint (9.x) configured via `eslint.config.mjs`
- Config: Uses Next.js core-web-vitals and typescript rules
- Line length: Approximately 100 characters (observed in code)
- Indentation: 2 spaces (TypeScript/JavaScript)

**Linting:**
- Tool: ESLint with Next.js config (`eslint-config-next`)
- Key rules enforced:
  - No unused variables (with explicit eslint-disable comments when necessary)
  - TypeScript strict mode enabled in `tsconfig.json`
  - Underscore prefix (`_variable`) does NOT suppress `no-unused-vars` — use `// eslint-disable-next-line @typescript-eslint/no-unused-vars` instead
  - Component imports properly typed
- Run: `npm run lint` in dashboard directory

**Python Style:**
- Tool: Ruff (configured in `pyproject.toml`)
- Line length: 100 characters
- Target: Python 3.11+
- Docstrings: Module-level docstrings using triple quotes (e.g., `"""Performance impact monitoring helpers..."""`)

## Import Organization

**Order (TypeScript/JavaScript):**
1. React and external libraries (e.g., `import { useState } from 'react'`)
2. Next.js imports (e.g., `import { NextRequest, NextResponse } from 'next/server'`)
3. UI library imports (radix, shadcn, lucide, etc.)
4. Internal absolute imports using `@/` alias (e.g., `import { Button } from '@/components/ui/button'`)
5. Relative imports (rare; prefer `@/`)

**Path Aliases:**
- `@/*` resolves to `./src/*` (defined in `tsconfig.json`)
- Always use absolute `@/` imports, never relative paths for cross-module imports
- Example: `import { Badge } from '@/components/ui/badge'` not `import { Badge } from '../ui/badge'`

**Example:**
```typescript
'use client'

import { useMemo, useState } from 'react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { composeTemplateTitle } from '@/lib/review/manual-title'
```

## Error Handling

**Patterns:**
- `try/catch` blocks in async functions, with console.error logging
- Structured error responses using helper functions (e.g., `errorResponse()` in `/api/regenerate/route.ts`)
- Type guards for error discrimination: `error instanceof Error ? error.message : 'Unknown error'`
- Supabase errors logged with context helper (e.g., `logSupabaseError()`) showing code, message, details, hint
- Error objects should include context (e.g., which step failed) and actionable messages for users

**Example from `/api/performance/capture-snapshot/route.ts`:**
```typescript
async function postPipeline(path: string, body: Record<string, unknown>) {
  const response = await fetch(`${PIPELINE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : `Pipeline call failed: ${path}`
    throw new Error(detail)
  }
  return payload
}
```

**Production vs Development:**
- In production, return sanitized error responses without internal details (see `errorResponse()` in regenerate route)
- In development, include full error context for debugging

## Logging

**Framework:** Console (native, no external logging library)

**Patterns:**
- `console.error()` for errors with context (e.g., `console.error('Snapshot capture failed:', error)`)
- `console.log()` for debugging (rarely used in production paths)
- Python: Uses `logging` module via `logger = logging.getLogger(__name__)`
- Log message format: Descriptive context + data (e.g., `'Snapshot capture failed:', error`)

**When to Log:**
- Errors that might be retried or indicate a system issue
- Integration points (API calls, database operations)
- Performance-critical operations (timing, completion)
- NOT verbose tracing of normal control flow

## Comments

**When to Comment:**
- Complex algorithmic logic (e.g., difference-in-differences computation)
- Non-obvious design decisions or workarounds
- Integration-specific details (e.g., GMC offer ID format transformation)
- Historical context for bugs/fixes (documented in code blame)

**Avoid:**
- Obvious comments that repeat code (e.g., `// increment counter` above `count++`)
- Outdated comments (assume code comments decay)

**Block Comments:**
- Use `/**` block comments for multi-line explanations
- Example from `src/lib/publishing/google-sheets.ts`:
```typescript
/**
 * Google Sheets integration for GMC supplemental feed updates.
 *
 * Pushes optimized product content (title, description, lifestyle images) to a Google Sheet
 * that serves as a supplemental feed for Google Merchant Center.
 */
```

**JSDoc/TSDoc:**
- Used for public functions with parameters and return types
- Pattern: `@param {type} name - description`, `@returns {type} description`
- Example from `src/lib/google-ads.ts`:
```typescript
/**
 * @param shopifyProductIds - Array of Shopify product IDs (e.g., ['4545063682180'])
 * @param startDate - Start date in YYYY-MM-DD format
 * @param endDate - End date in YYYY-MM-DD format
 * @returns Map of Shopify product ID to aggregated performance metrics
 */
```

## Function Design

**Size:** Functions should be focused and testable. Average 30-60 lines for API routes, 15-30 for utilities.

**Parameters:**
- Use typed objects/interfaces for multiple params (especially 3+)
- Use named parameters with `*` prefix in Python for clarity (e.g., `treated_pre: float`)
- Keyword-only arguments in Python: `def compute_diff_in_diff_lift_pct(*, treated_pre: float, ...)`
- Avoid parameter lists longer than 4 (group related params)

**Return Values:**
- Use explicit return types (TypeScript enforces; Python via type hints)
- Return early to reduce nesting
- Null/undefined: Only when value may not exist (e.g., `baseline?: PerformanceBaseline`)
- Use `Promise<Type>` for async, never bare `Promise`
- Pattern: Return structured results or null, not undefined

**Example from `src/lib/baseline-capture.ts`:**
```typescript
export async function captureBaseline(
  supabase: SupabaseClient,
  masterSku: string,
  platform: Platform
): Promise<PerformanceBaseline | null> {
  // Implementation
  return result ?? null
}
```

## Module Design

**Exports:**
- One primary export per file (or cohesive group of related functions)
- Use named exports for utilities, default export only for React components in some cases
- Public functions documented with JSDoc/TSDoc
- Type exports explicitly marked: `export type { Interface }`

**Barrel Files:**
- Used in `src/components/search-insights/index.ts` and `src/lib/evidence/index.ts`
- Re-export public API from directory without exposing internal organization
- Example from `src/lib/evidence/index.ts`:
```typescript
export { buildEvidenceTable } from './builder'
export type { Evidence, EvidenceContext } from './types'
```

**Module Purpose:**
- Utilities: `src/lib/*` - Shared business logic, data transformation, external integrations
- Components: `src/components/*` - React UI components organized by feature/domain
- Routes: `src/app/api/*` - Next.js API endpoints organized by resource
- Types: `src/lib/supabase/types.ts` - Database/API type definitions

## Component Patterns (React)

**File Naming:**
- Filenames match exported component name exactly (e.g., `ManualTitleEditor.tsx` exports `ManualTitleEditor`)
- Multiple variant exports use numbered suffixes: `SkuReviewClient.tsx`, `SkuReviewClient.magazine.tsx`, `SkuReviewClient.original.tsx`

**Use Client Marker:**
- All interactive components use `'use client'` directive at top (Next.js 13+ App Router)
- Hooks (useState, useMemo, etc.) require client directive

**Props Type:**
- Always define `interface ComponentNameProps` with explicit types
- Optional props: `prop?: Type` (not `prop: Type | undefined`)
- Handlers: `on{Event}: (args: Type) => void` (e.g., `onSaved: (title: string) => void`)

**State Management:**
- Use React hooks (useState, useMemo, useCallback)
- Avoid over-memoization; profile before optimizing
- Use zustand for cross-component state (if needed, not currently used)

**Conditional Rendering:**
- Use ternary operators for single conditions
- Use `&&` for presence checks, but avoid when value could be `0` or `false`
- Use optional chaining (`?.`) to prevent errors on undefined

## Python Conventions

**Module Layout:**
- Docstrings at module top describing purpose and major functions
- Imports (external, then internal)
- Constants (UPPER_SNAKE_CASE)
- Classes/Functions in logical groups
- `if __name__ == '__main__':` block if executable

**Function Docstrings:**
- One-line summary if simple, multi-line for complex functions
- Args/Returns sections using standard format
- Example from `src/feedops/monitoring/performance_impact.py`:
```python
def compute_diff_in_diff_lift_pct(
    *,
    treated_pre: float,
    treated_post: float,
    control_pre: float,
    control_post: float,
) -> float | None:
    """Return percentage-point difference-in-differences lift.

    Formula:
      DID% = ((treated_post - treated_pre) / treated_pre) * 100
           - ((control_post - control_pre) / control_pre) * 100

    Returns None when a pre-period denominator is zero.
    """
```

**Type Hints:**
- Always use type hints (Python 3.11+)
- Use `from __future__ import annotations` for forward references
- Union types: `float | None` (not `Optional[float]`)
- Collections: `list[Type]`, `dict[Key, Value]`, `tuple[Type, ...]`

## Special Patterns

**Lazy Initialization:**
- Module-level variable pattern for singleton resources (e.g., OpenAI client)
- Private variable (`_openai`) with public getter function (`getOpenAIClient()`)
- Ensures client only created on first use, never recreated

**Environment Variables:**
- TypeScript: Accessed via `process.env.VARIABLE_NAME`
- Python: Via Pydantic `settings.VARIABLE_NAME` or `os.getenv()`
- Defaults always provided for non-critical vars (e.g., model name)

**Type Assertion:**
- Use sparingly; prefer better type design
- Pattern: `value as Type` when type system can't infer but you know it's safe
- Document WHY assertion is needed in comment

---

*Convention analysis: 2026-02-20*
