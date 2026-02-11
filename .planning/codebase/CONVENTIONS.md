# Coding Conventions

**Analysis Date:** 2026-02-11

## Naming Patterns

**Files:**
- TypeScript/React files: `camelCase` or `PascalCase` (components use PascalCase)
  - Example: `SkuReviewClient.tsx`, `sku-utils.ts`, `baseline-capture.ts`
- Utility files: `kebab-case.ts` for standalone modules
- API routes: `[name]/route.ts` following Next.js app router convention
- Test files: `[name].test.ts` or `[name].test.tsx` (co-located in `__tests__` directories or next to source)

**Functions:**
- `camelCase` for all function names (TypeScript and Python)
  - Example: `getSkuCandidates()`, `buildEnhancedPrompt()`, `captureBaseline()`
- Utility/helper functions: Prefix with underscore for internal-only functions
  - Example: `_trimGoogleShortTitle()`, `_normalizeTitle()`

**Variables:**
- `camelCase` for all variables (TypeScript and Python)
  - Example: `mockUsePerformanceData`, `serviceAccountJson`, `baselineStartDate`
- Constants: `UPPER_SNAKE_CASE`
  - Example: `MODEL`, `FINISH_LIST`, `USE_VISION`, `API_VERSION`
- Private class properties: Prefix with underscore
  - Example: `_openai` (lazy-initialized singleton)

**Types:**
- `PascalCase` for TypeScript interfaces and types
  - Example: `RegenerationResult`, `SupabaseErrLike`, `ContentType`
- Generic type parameters: `PascalCase` or single-letter uppercase
  - Example: `T`, `K`, `V`, or `PromptTemplate`
- Union types: `'literal' | 'literal'` syntax (single quotes)
  - Example: `'title' | 'description'`, `'google' | 'bing' | 'shopify'`

**Python-specific:**
- Classes: `PascalCase`
  - Example: `OpenAIProvider`, `ParentSKU`, `Candidate`
- Modules: `snake_case.py`
  - Example: `prompt_loader.py`, `supabase_client.py`, `generator.py`
- Private functions: Prefix with underscore
  - Example: `_trim_google_short_title()`, `_normalize_title_separators()`

## Code Style

**Formatting:**
- No explicit formatter configured; ESLint/Next.js defaults apply
- Line length: Python uses 100 character limit (Ruff config in `pyproject.toml`)
- Indentation: 2 spaces (TypeScript), 4 spaces (Python, implicit)
- Semicolons: Required in TypeScript (Next.js convention)

**Linting:**
- TypeScript: ESLint 9 with Next.js core-web-vitals and typescript plugins (`dashboard/eslint.config.mjs`)
- **CRITICAL**: Underscore prefix does NOT suppress `no-unused-vars`
  - Use `// eslint-disable-next-line @typescript-eslint/no-unused-vars` instead
  - For Map iteration with unused key: `[, value]` destructuring pattern
- Python: Ruff with line-length=100, target-version=py311
- TypeScript strict mode: Enabled (`tsconfig.json` has `"strict": true`)

**Import Organization:**
- Order:
  1. Node.js built-in modules (`node:crypto`, `node:fs`)
  2. Third-party dependencies (`openai`, `@supabase/supabase-js`, `next/server`)
  3. Type imports (`import type { ... }`)
  4. Relative imports (`@/lib/...`, `./...`)
- Group imports with blank lines between categories
- Use absolute paths with `@/` alias (configured in `tsconfig.json` → `paths.@/*`)
- Example from `core.ts`:
  ```typescript
  import OpenAI from 'openai'
  import type { ChatCompletionMessageParam, ChatCompletionContentPart } from 'openai/resources/chat/completions'
  import type { SupabaseClient } from '@supabase/supabase-js'
  import { getProductEvidence, productExistsInCatalog } from '@/lib/evidence'
  import crypto from 'node:crypto'
  ```

## Error Handling

**TypeScript/JavaScript:**
- Throw `Error` or `new Error('message')` for errors
  - Example: `throw new Error('OPENAI_API_KEY environment variable is not set')`
- Provide context-specific error messages
- Use try-catch blocks for external API calls
  - Example from `google-sheets.ts`:
    ```typescript
    try {
      serviceAccountJson = Buffer.from(base64Key, 'base64').toString('utf-8')
    } catch {
      throw new Error('Failed to decode GOOGLE_SERVICE_ACCOUNT_KEY from base64')
    }
    ```
- API routes: Return structured error response with status code
  - Example from `route.ts`:
    ```typescript
    function errorResponse(status: number, payload: {...}) {
      return NextResponse.json(payload, { status })
    }
    ```
- Production vs. development error details: Check `process.env.NODE_ENV`

**Python:**
- Use standard exception hierarchy (raise custom exceptions if needed)
- Log errors before re-raising
  - Example: `logger.error("context", {"code": err.code, "message": err.message})`
- FastAPI endpoints return structured JSON error responses
- Async functions use `asyncio` patterns with proper error propagation

## Logging

**Framework:** No external logging library; uses native logging
- TypeScript: `console.error()`, `console.log()`, `console.warn()`
  - Limited usage in production (prefer structured responses)
  - Example from `route.ts`: `console.error(context, {...})`
- Python: `logging` module with `logger = logging.getLogger(__name__)`
  - FastAPI app configures logging with `basicConfig`
  - Level: `INFO` (configured in `main.py`)
  - Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
  - Used for request tracking and API operations

## Comments

**When to Comment:**
- Document non-obvious algorithms or logic
- Explain WHY, not WHAT (code shows what; comments show why)
- Mark intentional complexity with explanations
- Warn about side effects or dependencies

**JSDoc/TypeDoc:**
- Use JSDoc for exported functions and types
- Format: `/** description */` for simple descriptions
- Multi-line: `/** line 1 ... @param ... @returns ... */`
- Example from `sku-utils.ts`:
  ```typescript
  /**
   * Generate all possible database SKU formats for a URL SKU.
   * Use this when looking up a SKU in the database - try each candidate
   * until you find a match.
   *
   * IMPORTANT: Slash-format candidates are prioritized first...
   * @param urlSku The SKU as it appears in the URL (hyphens only)
   * @returns Array of possible database formats to try, prioritized by likelihood
   */
  ```

**Documentation Comments:**
- Use `/** */` for public APIs (functions, types, modules)
- Use `// ` for inline code comments explaining complex logic
- Use `// eslint-disable-next-line` for linting suppressions (include the rule)

## Function Design

**Size:**
- Keep functions focused on single responsibility
- Example: `_trimGoogleShortTitle()` (34 lines), `_normalizeTitle()` (56 lines) — focused on title normalization
- Complex generation functions break down into helpers

**Parameters:**
- Use typed parameters (TypeScript) or type hints (Python)
- Prefer objects for multiple related parameters
  - Example: `RegenerationRequest` interface groups request fields
- Use union types for exclusive options
  - Example: `Platform = 'google' | 'bing' | 'shopify'`

**Return Values:**
- Return typed objects for clarity
  - Example: `RegenerationResult` interface with `success`, `content`, `error` fields
- Return `null` or `undefined` for absence (not error states)
- Use `| null` in return types explicitly
  - Example: `captureBaseline(...): Promise<BaselineData | null>`

**Async/Await:**
- Prefer `async/await` over `.then()` chains
- Always handle errors in async functions with try-catch
- Use `Promise<T>` for explicit async return types

## Module Design

**Exports:**
- Named exports for utilities and functions
  - Example: `export function getSkuCandidates(...)`
- Default export for React components (PascalCase names)
  - Example: `export default function PerformanceCard(...)`
- Type exports: Use `export type {...}` syntax
  - Example: `export type ContentType = 'title' | 'description'`

**Barrel Files:**
- Use barrel exports (`index.ts`) for grouping related utilities
  - Example: `@/lib/evidence` exports multiple evidence functions
- Structure: one main export per file, re-export in index

**Lazy Initialization:**
- Use function-scoped initialization for expensive resources
  - Example from `core.ts`: `getOpenAIClient()` lazy-initializes OpenAI singleton
  ```typescript
  let _openai: OpenAI | null = null
  export function getOpenAIClient(): OpenAI {
    if (!_openai) {
      _openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })
    }
    return _openai
  }
  ```

## Database Conventions

**Column Naming:**
- `snake_case` for all columns
- Use `_at` suffix for timestamps: `created_at`, `updated_at`, `approved_at`
- Use `_status` for status fields: `approval_status`, `publish_status`
- Use `avg_` prefix for average metrics: `avg_impressions`, `avg_ctr`

**Query Patterns:**
- Always check `docs/database/SCHEMA.md` before writing queries
- Use type-safe client methods (Supabase JS SDK methods)
- For JSONB columns: parse with `(column#>>'{}')::jsonb` in SQL before array operations
- LATERAL joins for expanding JSONB arrays: `CROSS JOIN LATERAL jsonb_array_elements_text(...)`

**Case Sensitivity:**
- Use `LOWER()` on both sides for case-insensitive string matching
- Or use `regexp_replace()` for pattern-based joins

## TypeScript Patterns

**Strict Mode Features:**
- All variables/parameters must be typed
- No implicit `any` (enabled by default)
- Use union types for multi-state values
- Use type guards or `in` operator for narrowing

**Interface vs Type:**
- Use `interface` for object shapes (allows declaration merging)
- Use `type` for unions, tuples, or primitives
- Export both as `export type` or `export interface`

**Generics:**
- Use for reusable utilities (BaseModel, Response wrappers)
- Constrain with `extends` keyword when needed
- Example: `type ContentType<T extends 'title' | 'description'> = ...`

**Optional Chaining:**
- Use `?.` for optional property access
- Combine with `?? null` to default to null explicitly
  - Example: `component?.property ?? null`
- Prevents `undefined` from propagating unexpectedly

## React/Next.js Patterns

**Components:**
- Functional components only (no class components)
- Use `'use client'` directive for client-side components
- Use `type` suffix for component prop interfaces
  - Example: `interface PerformanceCardProps { ... }`

**Hooks:**
- Custom hooks use `use` prefix
  - Example: `usePerformanceData()`, `useSkuData()`
- Always return typed objects
- Lazy load state with initializer function to avoid SSR mismatch
  - Example from CLAUDE.md: `useState(() => { if (typeof window === 'undefined') return default; ... })`

**Server Components:**
- Default: async server components (app router)
- No `'use client'` needed unless interactivity required
- Fetch data directly in server components

## Third-Party Library Patterns

**Zod (Validation):**
- Use for runtime schema validation
- Define schemas at module level
- Example: `CANDIDATE_SCHEMA` in Python, input validation in API routes

**Pydantic (Python validation):**
- Use `BaseModel` for API request/response models
- Use `Field` for additional metadata and defaults
- Example from `main.py`: `BaseModel` with type hints

**OpenAI API:**
- Use `openai` package for TypeScript, `openai` Python package
- Handle streaming and non-streaming responses
- Check API version constants (e.g., `gpt-5.2` for newer models)

**Supabase:**
- Use Supabase client methods (`.from().select().eq()` patterns)
- Always await async operations
- Destructure errors: `{ data, error }`
- Use type-safe row types from generated types (or `any` if not generated)

---

*Convention analysis: 2026-02-11*
