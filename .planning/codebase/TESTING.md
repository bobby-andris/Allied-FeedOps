# Testing Patterns

**Analysis Date:** 2026-02-20

## Test Framework

**Runner:**
- Vitest 3.2.4 (configured in `dashboard/vitest.config.ts`)
- Primary test framework for TypeScript/JavaScript
- Python: pytest 7.0+ (configured in `pyproject.toml`)

**Assertion Library:**
- Vitest built-in `expect()` API (compatible with Jest)
- Python: pytest `assert` statements

**Run Commands:**
```bash
# TypeScript/JavaScript (from dashboard/ directory)
npm run test              # Run all tests once
npm run test:watch       # Watch mode

# Python (from project root)
pytest tests/ -v         # Run all tests with verbose output
pytest tests/test_performance_impact.py -v  # Run specific file
pytest -k "test_name" -v # Run tests matching pattern
```

## Test File Organization

**Location:**
- TypeScript: Co-located with source in `__tests__/` subdirectory
  - Relative path: `src/components/review/__tests__/PublishButton.test.tsx`
  - Source path: `src/components/review/PublishButton.tsx`
- Python: Separate `tests/` directory at project root
  - Test file: `tests/test_performance_impact.py`
  - Source module: `src/feedops/monitoring/performance_impact.py`

**Naming:**
- TypeScript: `{ComponentName}.test.tsx` or `{module}.test.ts`
- Python: `test_{module}.py` (prefix, not suffix)

**File Count:**
- 28 TypeScript test files as of 2026-02-20
- Coverage: Components, API routes, utilities, business logic
- Selective: Not every file has tests; focus on critical paths and complex logic

## Test Structure

**TypeScript Suite Organization:**
```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ComponentName } from '../ComponentName'

describe('ComponentName', () => {
  beforeEach(() => {
    // Setup before each test
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Cleanup after each test
    vi.restoreAllMocks()
  })

  it('should render with expected props', () => {
    render(<ComponentName prop="value" />)
    expect(screen.getByText('Expected text')).toBeInTheDocument()
  })

  it('should handle user interaction', async () => {
    const user = userEvent.setup()
    render(<ComponentName />)
    await user.click(screen.getByRole('button'))
    expect(screen.getByText('Result')).toBeInTheDocument()
  })
})
```

**Python Test Organization:**
```python
from __future__ import annotations
from datetime import date
import pytest

def test_function_does_something() -> None:
    """Docstring describing test intent."""
    # Arrange
    input_data = date(2026, 2, 20)

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value


class TestGroupName:
    """Group related tests in a class."""

    @pytest.fixture
    def fixture_name(self):
        """Provide test data."""
        return sample_data

    def test_case_one(self, fixture_name):
        assert fixture_name is not None
```

**Patterns:**
- `describe()` blocks group related tests by component/function
- Test names start with `it('should...')` describing behavior
- Tests are isolated: no shared state between tests
- Use `beforeEach()` for setup, `afterEach()` for cleanup
- Python: `def test_*() -> None:` signature for type clarity

## Mocking

**Framework:** Vitest `vi` module (Jest-compatible)

**Patterns:**

**1. Module Mocking (Hoisting Pattern):**
```typescript
const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  resolveCanonicalMasterSku: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/master-sku', () => ({
  resolveCanonicalMasterSku: mocks.resolveCanonicalMasterSku,
}))

import { POST } from '@/app/api/regenerate/batch/route'
```
- Hoisting: Define `vi.hoisted()` at top before imports
- Allows importing and mocking the same module consistently
- Used in `src/app/api/regenerate/batch/__tests__/route.test.ts`

**2. Mock Implementation:**
```typescript
vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(performanceMap)
vi.mocked(googleAds.getDateRange).mockReturnValue({
  startDate: '2026-01-08',
  endDate: '2026-02-07',
})
```
- `mockResolvedValue()` for async functions
- `mockReturnValue()` for sync functions
- `mockImplementation()` for custom behavior (e.g., tracking in-flight count)

**3. Global Stubs:**
```typescript
const fetchMock = vi.fn().mockResolvedValue(
  new Response(JSON.stringify({ success: true }), { status: 200 })
)
vi.stubGlobal('fetch', fetchMock)
```
- Replace global functions like `fetch`
- Cleanup with `vi.unstubAllGlobals()` in `afterEach()`

**4. DOM/Library Mocks:**
```typescript
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))
```
- Mock third-party libraries (sonner toast notifications)
- Return minimal interface matching usage

**5. Supabase Client Mocks:**
```typescript
function createSupabaseMock() {
  const single = vi.fn().mockResolvedValue({ data: {...}, error: null })
  const limit = vi.fn(() => ({ single }))
  const eq = vi.fn(() => ({ limit }))
  const select = vi.fn(() => ({ eq }))
  const from = vi.fn((table: string) => {
    if (table === 'variant_index') return { select }
    if (table === 'performance_baselines') return { upsert }
    return {}
  })

  return { from } as unknown as SupabaseClient
}
```
- Chain builder pattern matching Supabase API
- Supports `.from(table).select(...).eq(...).limit(...).single()`
- Type cast to `SupabaseClient` at end

**What to Mock:**
- External API calls (Google Ads, Supabase, Shopify)
- Third-party libraries (toast, external services)
- `fetch()` for HTTP mocking
- Current date/time (via mocking utilities)

**What NOT to Mock:**
- Built-in functions (Math, String, Array methods)
- Internal utility functions (use real implementations)
- Database schema/queries (mock the client, not the queries)
- Component children (render real components)

## Fixtures and Factories

**Test Data:**

**TypeScript Factory Pattern:**
```typescript
function createSupabaseMock(shopifyProductId: string | null = '1234567890'): MockContext {
  const single = vi.fn().mockResolvedValue({
    data: shopifyProductId ? { shopify_product_id: shopifyProductId } : null,
    error: null,
  })
  // ... build chain
  return { supabase, upsert }
}

// Usage
const { supabase, upsert } = createSupabaseMock('1234567890')
```

**TypeScript Test Data Objects:**
```typescript
const mockPerformanceData = {
  master_sku: '920D-6',
  platform: 'google',
  avg_impressions: 42100,
  avg_clicks: 1263,
  avg_ctr: 0.03,
}

render(<PerformanceCard baselines={[mockPerformanceData]} snapshots={[]} />)
```

**Python Fixtures (conftest.py):**
```python
@pytest.fixture
def sample_catalog_path() -> Path:
    """Path to sample catalog CSV for testing."""
    return Path("samples/sample-catalog.csv")

# Usage in test
def test_loads_catalog(sample_catalog_path):
    assert sample_catalog_path.exists()
```

**Location:**
- TypeScript: Inline factory functions in test file (near top)
- Python: Fixtures in `tests/conftest.py` for reuse across tests
- Inline data: Use for single-test scenarios, factories for complex multi-test setups

## Coverage

**Requirements:** Not enforced (no coverage thresholds in config)

**View Coverage:**
```bash
npm run test -- --coverage  # Would need coverage plugin configured
```

**Current State:**
- No coverage configuration in `vitest.config.ts`
- Testing is selective, focusing on:
  - Complex business logic (baseline capture, performance calculations)
  - API routes with multiple branches
  - Component interactions and state
  - Edge cases (null data, errors, concurrency)

**Test Types:**

**Unit Tests:**
- Scope: Single function or small module
- Approach: Pure function testing, isolated from dependencies
- Example: `test_compute_diff_in_diff_lift_pct_uses_relative_changes()` in `test_performance_impact.py`
- Focus: Logic correctness, edge cases (zero denominators, null values)
- Files: `src/lib/__tests__/`, `src/components/review/__tests__/`

**Integration Tests:**
- Scope: Multiple modules working together (typically with mock external services)
- Approach: Mock external APIs but test internal integration
- Example: `captureBaseline` test mocking Google Ads but testing Supabase flow
- Focus: Data transformations, end-to-end flow verification
- Files: API route tests in `src/app/api/**/__tests__/`

**Component Tests:**
- Scope: React components with user interactions
- Approach: Render component, simulate user events, verify DOM changes
- Example: `PublishButton.test.tsx` rendering button, clicking, verifying results
- Tools: `@testing-library/react`, `@testing-library/user-event`
- Pattern: `render()` → user interaction → assertion on DOM

**E2E Tests:**
- Framework: Not used (would be Playwright or Cypress)
- Status: Functional testing done manually or via staging deployment

## Common Patterns

**Async Testing (React):**
```typescript
it('waits for async operations to complete', async () => {
  const user = userEvent.setup()
  render(<ComponentWithAsyncLoad />)

  // Wait for promise to resolve
  await waitFor(() => {
    expect(screen.getByText('Loaded')).toBeInTheDocument()
  })
})

// Alternative: vi.waitFor() for non-DOM async operations
await vi.waitFor(() => {
  expect(mocks.apiCall).toHaveBeenCalledTimes(1)
})
```

**Error Testing:**
```typescript
it('handles API errors gracefully', async () => {
  vi.mocked(fetchFunction).mockRejectedValue(new Error('Network error'))

  const result = await functionUnderTest()

  expect(result).toBeNull()  // Or check error state
})

// Spy on console.error to verify error is logged
const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
// ... run code that errors
expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining('Failed'))
```

**Mock State Verification:**
```typescript
it('calls API with correct parameters', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
  vi.stubGlobal('fetch', fetchMock)

  await functionThatFetches()

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/api/endpoint'),
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    })
  )
})
```

**Concurrent Operations Testing:**
```typescript
it('processes batch operations concurrently', async () => {
  let inFlight = 0
  let maxInFlight = 0

  const fetchMock = vi.fn().mockImplementation(async () => {
    inFlight += 1
    maxInFlight = Math.max(maxInFlight, inFlight)
    await new Promise(resolve => setTimeout(resolve, 30))
    inFlight -= 1
    return new Response(JSON.stringify({ success: true }), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)

  await batchFunction()

  expect(maxInFlight).toBeGreaterThanOrEqual(2)  // Verify concurrency
})
```

## Setup and Configuration

**TypeScript Configuration (`dashboard/vitest.config.ts`):**
```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',           // Browser environment for DOM tests
    globals: true,                  // Global test functions (describe, it, expect)
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    exclude: ['node_modules', '.next'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

**Setup File (`dashboard/src/test/setup.ts`):**
```typescript
import '@testing-library/jest-dom/vitest'
```
- Adds matchers like `.toBeInTheDocument()`, `.toHaveClass()`, etc.

**Python Configuration (`pyproject.toml`):**
```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```
- `testpaths`: Where to find tests
- `asyncio_mode`: Auto-detect async tests

## Test Quality Patterns

**Descriptive Test Names:**
```typescript
// Good: Behavior-focused
it('marks funnel decisions incomplete until all custom_label_0 assignments are set')
it('renders readiness errors without duplicate React keys when multiple blockers exist for one platform')

// Avoid: Implementation-focused
it('checks status')
it('validates input')
```

**Arrange-Act-Assert:**
```typescript
it('does something', () => {
  // Arrange: Set up test data and mocks
  const mockData = { id: '1', name: 'Test' }
  const { supabase, upsert } = createSupabaseMock()

  // Act: Call function under test
  const result = await captureBaseline(supabase, 'SKU-1', 'google')

  // Assert: Verify expectations
  expect(result).toEqual(expectedValue)
  expect(upsert).toHaveBeenCalledTimes(1)
})
```

**Test Isolation:**
```typescript
afterEach(() => {
  vi.clearAllMocks()      // Clear mock call history
  vi.restoreAllMocks()    // Restore mocked implementations
  vi.unstubAllGlobals()   // Remove global stubs (fetch, etc.)
})
```

**Boundary/Edge Cases:**
```typescript
it('returns null when no performance data is available', async () => {
  vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(new Map())
  const result = await captureBaseline(supabase, '920D-6', 'google')
  expect(result).toBeNull()
  expect(upsert).not.toHaveBeenCalled()  // Side effect not triggered
})

it('returns None when a pre-period denominator is zero', () => {
  result = compute_diff_in_diff_lift_pct(
    treated_pre=0,
    treated_post=10,
    control_pre=8,
    control_post=9,
  )
  assert result is None
})
```

---

*Testing analysis: 2026-02-20*
