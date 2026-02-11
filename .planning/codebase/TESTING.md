# Testing Patterns

**Analysis Date:** 2026-02-11

## Test Framework

**TypeScript/JavaScript:**
- **Runner:** Vitest (installed but not in dashboard `package.json` scripts yet)
- **Test Library:** `@testing-library/react` for component testing, `@testing-library/user-event` for user interactions
- **Assertion:** Vitest's `expect()` (matching Jest syntax)
- **Mocking:** Vitest `vi` module with `vi.mock()` and `vi.fn()`

**Python:**
- **Runner:** pytest (configured in `pyproject.toml`)
- **Config:** `pytest.ini_options` in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  ```
- **Async:** `pytest-asyncio` for async test support
- **Mocking:** `unittest.mock` (standard library) via `monkeypatch` fixture

**Run Commands:**
```bash
# TypeScript (currently no test script in dashboard/package.json)
# To add: "test": "vitest" in package.json

# Python
pytest tests/ -v                  # Run all tests verbose
pytest tests/test_name.py -v     # Run specific test file
pytest tests/ --asyncio-mode=auto  # Async tests
PYTHONPATH=./src pytest tests/    # Run with Python path set
```

## Test File Organization

**TypeScript:**
- **Location:** Co-located in `__tests__` directories alongside source files
  - Example: `dashboard/src/components/review/__tests__/PerformanceCard.test.tsx`
  - Example: `dashboard/src/lib/__tests__/baseline-capture.test.ts`
- **Naming:** `[ComponentName].test.tsx` or `[module].test.ts`
- **Structure:** One test file per module/component

**Python:**
- **Location:** Separate `tests/` directory at project root
  - `tests/test_openai_provider_max_tokens.py`
  - `tests/test_evidence_multisize.py`
  - `tests/conftest.py` for shared fixtures
- **Naming:** `test_[feature].py` (pytest convention)

## Test Structure

**TypeScript with Vitest:**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ComponentUnderTest } from '../Component'

// Mock external dependencies
vi.mock('@/hooks/useCustomHook', () => ({
  useCustomHook: vi.fn(),
}))

describe('ComponentName', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Feature Group', () => {
    it('should handle specific behavior', () => {
      // Arrange
      const mockData = { /* ... */ }

      // Act
      const result = someFunction(mockData)

      // Assert
      expect(result).toEqual(expectedValue)
    })
  })
})
```

**Key patterns from `PerformanceCard.test.tsx`:**
- Nested `describe()` blocks for feature grouping
  - Example: `describe('Loading State')`, `describe('Expanded State')`
- Mock hooks before import: `vi.mock('@/hooks/usePerformanceData')`
- Type cast mocks: `const mockUsePerformanceData = usePerformanceData as ReturnType<typeof vi.fn>`
- Clear mocks in `beforeEach()` for test isolation
- User interactions with `userEvent.setup()` and async patterns
- `waitFor()` for async state updates in React

**Python with Pytest:**

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_async_function():
    # Arrange
    mock_data = {...}

    # Act
    result = await function_under_test(mock_data)

    # Assert
    assert result == expected_value

def test_with_fixture(sample_catalog_path):
    # Use fixture
    assert sample_catalog_path.exists()
```

**Key patterns from Python tests:**
- `@pytest.mark.asyncio` decorator for async tests
- `monkeypatch` fixture for mocking
  - Example: `monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)`
- Simple function mocking with types.SimpleNamespace for mock responses
- Fixtures defined in `conftest.py` for reusable test data

## Mocking

**TypeScript Mocking (Vitest):**

```typescript
// Before imports:
vi.mock('@/hooks/usePerformanceData', () => ({
  usePerformanceData: vi.fn(),
}))

// After imports:
import { usePerformanceData } from '@/hooks/usePerformanceData'
const mockUsePerformanceData = usePerformanceData as ReturnType<typeof vi.fn>

// Setup in test:
mockUsePerformanceData.mockReturnValue({
  current: { impressions: 45200, clicks: 1446 },
  baseline: null,
  status: 'warning',
  loading: false,
  error: null,
})

// Assertions:
expect(mockUsePerformanceData).toHaveBeenCalledWith('920D-6', 'google')
vi.clearAllMocks()  // In beforeEach()
```

**Python Mocking (monkeypatch):**

```python
def test_function(monkeypatch):
    # Mock module function
    monkeypatch.setattr(googleAds, 'getDateRange', lambda: {
        'startDate': '2026-01-08',
        'endDate': '2026-02-07'
    })

    # Mock provider method
    async def _fake_create(**kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1}
        )
    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
```

**What to Mock:**
- External API calls (OpenAI, Google Ads, Supabase)
- Browser APIs (localStorage, window, fetch)
- Hooks and context providers
- System functions (dates, random values)
- Database queries

**What NOT to Mock:**
- Utility functions from the same module (test the real implementation)
- React components rendering helpers
- Standard library functions (Math, Array methods, etc.)
- Custom validators unless they have side effects

## Fixtures and Factories

**TypeScript:**
- Create mock data objects inline in tests
- Example from `PerformanceCard.test.tsx`:
  ```typescript
  mockUsePerformanceData.mockReturnValue({
    current: {
      impressions: 45200,
      clicks: 1446,
      ctr: 0.032,
      conversions: 89,
      conversion_value: 2847,
    },
    baseline: {
      avg_impressions: 42100,
      avg_clicks: 1263,
      avg_ctr: 0.030,
      avg_conversions: 71,
      avg_conversion_value: 2201,
    },
    status: 'warning',
    loading: false,
    error: null,
  })
  ```

**Python:**
- **Location:** `tests/conftest.py` for shared fixtures
  - Example:
    ```python
    @pytest.fixture
    def sample_catalog_path() -> Path:
        """Path to sample catalog CSV for testing."""
        return Path("samples/sample-catalog.csv")

    @pytest.fixture
    def temp_db_path(tmp_path: Path) -> Path:
        """Temporary database path for testing."""
        return tmp_path / "test_feedops.db"
    ```
- **Usage in tests:** Fixtures injected as parameters
  ```python
  def test_load_catalog(sample_catalog_path):
      assert sample_catalog_path.exists()
  ```
- **Pytest built-ins:** `tmp_path`, `monkeypatch`, `capsys` available without definition

## Coverage

**Requirements:** Not enforced (no coverage thresholds in config)

**Current state:**
- Limited test suite: 2 TypeScript test files, multiple Python test files
- Dashboard tests: UI component testing (PerformanceCard), utility testing (baseline-capture)
- Python tests: Provider integration, data loading, title normalization

**View Coverage:**
```bash
# Python (if coverage plugin installed)
pytest tests/ --cov=src/feedops --cov-report=html
# Then open htmlcov/index.html

# TypeScript (if coverage support added to vitest config)
vitest --coverage
```

## Test Types

**Unit Tests:**
- **Scope:** Single function or component
- **Approach:** Mock external dependencies, test logic in isolation
- **Examples:**
  - `test_baseline-capture.test.ts`: Tests `captureBaseline()` function with mocked Supabase and Google Ads
  - Python provider tests: Test OpenAI API call parameters without hitting real API

**Integration Tests:**
- **Scope:** Multiple modules working together
- **Approach:** Use real services (Supabase test DB) or realistic mocks
- **Examples:**
  - `test_review_dashboard.py`: Tests data loading and transformation
  - `test_evidence_multisize.py`: Tests evidence table building with real product data

**E2E Tests:**
- **Framework:** Not implemented (no Cypress, Playwright, or similar)
- **Note:** Dashboard has no end-to-end test automation; manual testing via browser

**Component Tests:**
- **Scope:** React components with user interactions
- **Approach:** Render component, mock hooks, simulate user actions
- **Key libraries:** `@testing-library/react`, `@testing-library/user-event`
- **Example from `PerformanceCard.test.tsx`:**
  ```typescript
  it('toggles between collapsed and expanded on click', async () => {
    const user = userEvent.setup()
    render(<PerformanceCard sku="920D-6" />)
    const trigger = screen.getByRole('button', { name: /performance/i })

    // Initially collapsed
    expect(screen.queryByText(/CURRENT/i)).not.toBeInTheDocument()

    // Click to expand
    await user.click(trigger)
    await waitFor(() => {
      expect(screen.getByText(/CURRENT/i)).toBeInTheDocument()
    })
  })
  ```

## Common Patterns

**Async Testing:**

TypeScript:
```typescript
it('should handle async operations', async () => {
  const user = userEvent.setup()
  render(<Component />)
  await user.click(button)
  await waitFor(() => {
    expect(screen.getByText('Expected')).toBeInTheDocument()
  })
})
```

Python:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

**Error Testing:**

TypeScript:
```typescript
it('handles fetch errors gracefully', () => {
  mockUsePerformanceData.mockReturnValue({
    current: null,
    baseline: null,
    status: 'no-data',
    loading: false,
    error: 'Failed to fetch performance data',
  })
  render(<PerformanceCard sku="920D-6" />)
  expect(screen.getByText(/failed to load performance/i)).toBeInTheDocument()
})
```

Python:
```python
def test_validation_error(monkeypatch):
    monkeypatch.setattr(provider, 'validate', lambda x: None)
    with pytest.raises(ValueError, match="Invalid input"):
        provider.generate(invalid_data)
```

**Accessibility Testing:**

```typescript
it('supports keyboard navigation', async () => {
  const user = userEvent.setup()
  render(<PerformanceCard sku="920D-6" />)
  const trigger = screen.getByRole('button', { name: /performance/i })

  // Tab to focus
  await user.tab()
  expect(trigger).toHaveFocus()

  // Enter to activate
  await user.keyboard('{Enter}')
  await waitFor(() => {
    expect(screen.getByText(/baseline/i)).toBeInTheDocument()
  })
})

it('announces state to screen readers', () => {
  render(<PerformanceCard sku="920D-6" />)
  const trigger = screen.getByRole('button', { name: /performance/i })
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
})
```

**State Assertion Patterns:**

TypeScript:
- Use `screen.getByText()` / `screen.queryByText()` for DOM assertions
- Use `queryByText()` (returns null if not found) vs `getByText()` (throws if not found)
- Chain assertions: `expect(element).toHaveClass('bg-green-500')`
- Test IDs: `screen.getByTestId('status-indicator')`

Python:
- Simple equality: `assert result == expected_value`
- Decimal precision: `assert result?.avg_cvr == 0.05`
- Null checks: `assert result is None`
- Collection checks: `assert len(result) > 0`

## Test Data Characteristics

**TypeScript:**
- Real data from production (SKU IDs, timestamps)
  - Example: `sku="920D-6"`, `impressions: 45200`, `ctr: 0.032`
- Performance metrics use realistic ranges
- Mock hook return shapes exactly match real hook signatures

**Python:**
- Use factory patterns for generating test models
- Create realistic Pydantic models with all required fields
- Use actual product family structures (DMF-2/2X, DMF-2/3X, etc.)
- Test with sample CSV files (e.g., `samples/sample-catalog.csv`)

---

*Testing analysis: 2026-02-11*
