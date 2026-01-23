# Allied FeedOps: Implementation Plan

**Status**: READY FOR EXECUTION  
**Date**: 2026-01-23  
**Estimated Tasks**: 25 tasks across 5 phases

---

## Phase 1: Project Setup & Data Models (Tasks 1-6)

### Task 1.1: Initialize Python Project Structure
**Time**: 3 min  
**Files**:
- `pyproject.toml` - Project config with dependencies
- `src/feedops/__init__.py` - Package init
- `src/feedops/py.typed` - Type hints marker
- `.python-version` - Python version (3.11+)

**Dependencies**:
```toml
[project]
dependencies = [
    "pandas>=2.0",
    "pydantic>=2.0",
    "openai>=1.0",
    "google-generativeai>=0.3",
    "httpx>=0.25",
    "python-dotenv>=1.0",
    "typer>=0.9",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.1", "mypy>=1.0"]
```

**Verification**: `pip install -e .` succeeds

---

### Task 1.2: Create Core Data Models
**Time**: 5 min  
**Files**:
- `src/feedops/models/__init__.py`
- `src/feedops/models/product.py` - ParentSKU, Variant models
- `src/feedops/models/candidate.py` - Candidate, Claim, Score models
- `src/feedops/models/evidence.py` - Evidence, VerificationRow models

**Models**:
```python
# product.py
class Variant(BaseModel):
    option_sku: str
    finish: str
    finish_code: str
    gmc_id: str  # shopify_US_{product_id}_{variant_id}
    shopify_product_id: str  # extracted from gmc_id
    shopify_variant_id: str  # extracted from gmc_id
    # ... all CSV fields mapped

class ParentSKU(BaseModel):
    master_sku: str
    category: str
    collection: str
    current_title: str
    current_description: str
    material: str
    # ... common attributes
    variants: list[Variant]

# candidate.py
class Claim(BaseModel):
    claim: str
    source_field: str
    source_value: str
    verified: bool = False

class Score(BaseModel):
    specificity: int  # 0-10
    benefit_coverage: int
    keyword_inclusion: int
    format_adherence: int
    brand_voice: int
    factual_accuracy: int
    
    @property
    def composite(self) -> float:
        return sum([...]) / 60 * 100

class Candidate(BaseModel):
    title: str
    description: str
    claims: list[Claim]
    self_score: Score
    verified_score: Score | None = None
```

**Verification**: `python -c "from feedops.models import ParentSKU, Candidate"` succeeds

---

### Task 1.3: Create CSV Column Mapping Configuration
**Time**: 3 min  
**Files**:
- `src/feedops/config/column_mapping.py` - Column name → model field mapping
- `src/feedops/config/__init__.py`

**Content**:
```python
CSV_COLUMN_MAPPING = {
    "MasterSKU": "master_sku",
    "OPTION SKU": "option_sku",
    "CoreSKU": "core_sku",
    # ... full mapping from design doc
}

# Handle duplicate column names by position
POSITIONAL_COLUMNS = {
    23: "product_length",  # First Length
    24: "product_height",  # First Height
    # ...
    28: "shipping_length",  # Second Length
    # ...
}
```

**Verification**: Import succeeds, mapping covers all 55 columns

---

### Task 1.4: Create Catalog CSV Loader
**Time**: 5 min  
**Files**:
- `src/feedops/loaders/__init__.py`
- `src/feedops/loaders/catalog.py` - Load and parse Product Catalog CSV

**Functions**:
```python
def load_catalog(path: Path) -> pd.DataFrame:
    """Load catalog CSV with duplicate column handling."""

def get_parent_sku(df: pd.DataFrame, master_sku: str) -> ParentSKU:
    """Extract ParentSKU with all variants from catalog."""

def list_master_skus(df: pd.DataFrame) -> list[str]:
    """List all unique MasterSKU values."""
```

**Verification**: `feedops.loaders.load_catalog("data/catalog/Product Catalog.csv")` returns DataFrame with 75k+ rows

---

### Task 1.5: Create SQLite Database Schema
**Time**: 4 min  
**Files**:
- `src/feedops/db/__init__.py`
- `src/feedops/db/schema.py` - Table definitions
- `src/feedops/db/connection.py` - Connection management

**Tables**:
```sql
-- optimization_runs: audit log
-- content_versions: title/description history
-- rollback_data: previous values for rollback
```

**Verification**: `feedops.db.init_db()` creates `feedops.db` with tables

---

### Task 1.6: Create Environment Config Loader
**Time**: 2 min  
**Files**:
- `src/feedops/config/env.py` - Load and validate env vars

**Content**:
```python
class Settings(BaseSettings):
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    shopify_store_url: str | None = None
    # ... etc
    
    model_config = SettingsConfigDict(env_file=".env")

def get_settings() -> Settings:
    """Load settings, validate at least one LLM key exists."""
```

**Verification**: `feedops.config.get_settings()` loads without exposing values

---

## Phase 2: Provider Interfaces (Tasks 7-12)

### Task 2.1: Create Base Provider Interface
**Time**: 2 min  
**Files**:
- `src/feedops/providers/__init__.py`
- `src/feedops/providers/base.py` - Abstract base classes

**Interfaces**:
```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate_candidate(self, prompt: str) -> dict: ...

class DataProvider(ABC):
    @abstractmethod
    async def fetch_product(self, identifier: str) -> dict | None: ...
```

---

### Task 2.2: Create OpenAI Provider
**Time**: 5 min  
**Files**:
- `src/feedops/providers/llm/__init__.py`
- `src/feedops/providers/llm/openai_provider.py`

**Features**:
- Structured output with JSON mode
- Retry with exponential backoff
- Token usage logging (no secrets)
- JSON repair loop on validation failure

**Verification**: Unit test with mock API response

---

### Task 2.3: Create Gemini Provider
**Time**: 4 min  
**Files**:
- `src/feedops/providers/llm/gemini_provider.py`

**Features**:
- Same interface as OpenAI
- JSON output parsing
- Fallback provider logic

**Verification**: Unit test with mock API response

---

### Task 2.4: Create LLM Provider Factory
**Time**: 2 min  
**Files**:
- `src/feedops/providers/llm/factory.py`

**Content**:
```python
def get_llm_provider(provider: str = "openai") -> LLMProvider:
    """Return configured LLM provider with fallback chain."""
```

---

### Task 2.5: Create Shopify Provider (Optional)
**Time**: 5 min  
**Files**:
- `src/feedops/providers/shopify.py`

**Features**:
- Fetch product by ID
- Fetch product metafields
- Extract from GMCID format

**Verification**: Healthcheck fetches 1 product

---

### Task 2.6: Create Merchant Center Provider Stub
**Time**: 3 min  
**Files**:
- `src/feedops/providers/merchant_center.py`

**Features**:
- Read product by item_id (Content API)
- Generate patch preview JSON (no write for MVP)
- Stub for future PATCH implementation

**Verification**: Can generate patch preview JSON

---

## Phase 3: Pipeline Core (Tasks 13-18)

### Task 3.1: Create Evidence Table Builder
**Time**: 4 min  
**Files**:
- `src/feedops/pipeline/evidence.py`

**Functions**:
```python
def build_evidence_table(parent_sku: ParentSKU) -> list[Evidence]:
    """Convert ParentSKU to structured evidence table for prompt."""

def format_evidence_markdown(evidence: list[Evidence]) -> str:
    """Format evidence as markdown table for prompt injection."""
```

---

### Task 3.2: Create Prompt Template System
**Time**: 5 min  
**Files**:
- `src/feedops/pipeline/prompts.py`
- `src/feedops/templates/optimize_prompt.txt` - Main prompt template

**Features**:
- Evidence table injection
- Rubric criteria injection
- JSON schema specification
- Constraint enforcement

---

### Task 3.3: Create Candidate Generator
**Time**: 5 min  
**Files**:
- `src/feedops/pipeline/generator.py`

**Functions**:
```python
async def generate_candidates(
    parent_sku: ParentSKU,
    llm: LLMProvider,
    num_candidates: int = 1
) -> list[Candidate]:
    """Generate optimized title/description candidates."""
```

---

### Task 3.4: Create Claim Verifier
**Time**: 5 min  
**Files**:
- `src/feedops/pipeline/verifier.py`

**Functions**:
```python
def verify_claims(
    candidate: Candidate,
    parent_sku: ParentSKU
) -> tuple[Candidate, list[str]]:
    """Verify each claim against source data. Return updated candidate and errors."""
```

**Logic**:
- For each claim, check `source_field` exists in ParentSKU
- Compare `source_value` to actual value
- Mark claim as verified or rejected
- Recalculate factual_accuracy score

---

### Task 3.5: Create Quality Scorer
**Time**: 4 min  
**Files**:
- `src/feedops/pipeline/scorer.py`

**Functions**:
```python
def score_candidate(candidate: Candidate) -> Score:
    """Calculate verified quality score using rubric."""

def check_approval(score: Score) -> tuple[str, str]:
    """Return ('approved'|'revise'|'reject', reason)."""
```

---

### Task 3.6: Create Report Generator
**Time**: 4 min  
**Files**:
- `src/feedops/pipeline/reporter.py`

**Functions**:
```python
def generate_sku_report(
    parent_sku: ParentSKU,
    candidate: Candidate,
    verification_errors: list[str]
) -> str:
    """Generate markdown report for SKU optimization."""

def generate_patch_preview(
    parent_sku: ParentSKU,
    candidate: Candidate
) -> dict:
    """Generate Merchant Center patch preview JSON."""
```

---

## Phase 4: CLI & Orchestration (Tasks 19-22)

### Task 4.1: Create Main Pipeline Orchestrator
**Time**: 5 min  
**Files**:
- `src/feedops/pipeline/optimize.py`

**Functions**:
```python
async def optimize_parent_sku(
    master_sku: str,
    catalog_path: Path,
    dry_run: bool = True
) -> OptimizationResult:
    """
    End-to-end optimization pipeline:
    1. Load catalog
    2. Extract ParentSKU
    3. Build evidence table
    4. Generate candidates
    5. Verify claims
    6. Score quality
    7. Generate reports
    8. Save to DB
    """
```

---

### Task 4.2: Create CLI Entry Point
**Time**: 5 min  
**Files**:
- `src/feedops/cli/__init__.py`
- `src/feedops/cli/main.py`

**Commands**:
```bash
feedops healthcheck          # Verify all connections
feedops optimize --parent-sku <SKU> --dry-run
feedops list-skus            # List all MasterSKUs in catalog
feedops show-sku <SKU>       # Show current data for SKU
```

**Verification**: `feedops --help` shows all commands

---

### Task 4.3: Create Healthcheck Command
**Time**: 5 min  
**Files**:
- `src/feedops/cli/healthcheck.py`

**Checks**:
1. Catalog CSV exists and loads
2. Environment variables present (names only)
3. OpenAI API responds (simple completion)
4. Gemini API responds (if configured)
5. Shopify API responds (fetch 1 product)
6. SQLite DB accessible

**Output**: Markdown report to `reports/healthcheck.md`

---

### Task 4.4: Create Optimize Command
**Time**: 4 min  
**Files**:
- `src/feedops/cli/optimize.py`

**Features**:
- `--parent-sku` required argument
- `--dry-run` flag (default True for safety)
- `--output-dir` for reports/exports
- Rich console output with progress

---

## Phase 5: Testing & Documentation (Tasks 23-25)

### Task 5.1: Create Unit Tests
**Time**: 5 min  
**Files**:
- `tests/__init__.py`
- `tests/test_models.py`
- `tests/test_loaders.py`
- `tests/test_verifier.py`

**Coverage targets**:
- Model validation
- CSV loading with duplicate columns
- Claim verification logic
- Score calculation

---

### Task 5.2: Create Integration Test with Sample Data
**Time**: 4 min  
**Files**:
- `tests/test_integration.py`

**Test**:
```python
def test_optimize_sample_sku():
    """Run full pipeline on sample data."""
```

---

### Task 5.3: Update Documentation
**Time**: 5 min  
**Files**:
- `docs/05-data-model.md` - Data contracts and field mapping
- `docs/06-sanity-checks.md` - Healthcheck and dry-run commands
- Update `docs/01-workflow.md` with identifier mapping section

---

## Verification Checklist

After all tasks complete:

- [ ] `pip install -e .` succeeds
- [ ] `feedops healthcheck` passes all checks
- [ ] `feedops list-skus | head -10` shows SKUs from catalog
- [ ] `feedops optimize --parent-sku 1031/18 --dry-run` completes
- [ ] Report generated at `reports/sku-1031-18.md`
- [ ] Patch preview at `exports/merchant-center-patch-1031-18.json`
- [ ] All claims in output verified against catalog
- [ ] Quality score ≥80% for test SKU
- [ ] `pytest tests/` passes

---

## What Remains After MVP

Before enabling write-mode (actual Merchant Center updates):

1. **Rate Limiting**: Implement per-API rate limits
2. **Safe Patching**: Content API PATCH with confirmation
3. **Rollback**: Automatic rollback on disapproval
4. **Monitoring**: Alert on quality score drops
5. **Batch Mode**: Process multiple SKUs with circuit breaker
6. **Supabase Migration**: Move from SQLite to cloud DB

---

## Execution Order

Recommended execution sequence:

```
Phase 1: Tasks 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6
Phase 2: Tasks 2.1 → 2.2 → 2.3 → 2.4 → (2.5, 2.6 parallel)
Phase 3: Tasks 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6
Phase 4: Tasks 4.1 → 4.2 → (4.3, 4.4 parallel)
Phase 5: Tasks 5.1 → 5.2 → 5.3
```

Total estimated time: ~90 minutes of focused implementation
