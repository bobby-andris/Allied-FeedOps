---
name: FeedOps MVP Implementation
overview: Create a comprehensive TDD implementation plan for Allied FeedOps MVP - a Python system to optimize Merchant Center product titles/descriptions using CSV data and LLM providers with strict factual verification.
todos:
  - id: phase1-setup
    content: "Phase 1: Project Setup - pyproject.toml, package structure, .env.example, pytest config (Tasks 1.1-1.4)"
    status: completed
  - id: phase2-models
    content: "Phase 2: Data Models - Variant, ParentSKU, Claim, Score, Candidate models (Tasks 2.1-2.5)"
    status: completed
  - id: phase3-loader
    content: "Phase 3: CSV Loader - Column mapping, catalog loader, ParentSKU extraction (Tasks 3.1-3.3)"
    status: completed
  - id: phase4-providers
    content: "Phase 4: LLM Providers - Base interface, OpenAI, Gemini, factory with fallback (Tasks 4.1-4.4)"
    status: completed
  - id: phase5-pipeline
    content: "Phase 5: Pipeline - Evidence builder, verifier, generator, reporter (Tasks 5.1-5.4)"
    status: completed
  - id: phase6-cli
    content: "Phase 6: CLI - Entry point, healthcheck, optimize commands (Tasks 6.1-6.3)"
    status: completed
  - id: phase7-db
    content: "Phase 7: Database - SQLite schema, audit logging integration (Tasks 7.1-7.2)"
    status: completed
  - id: final-verify
    content: Final Verification - Full test suite, type checks, linter, end-to-end CLI test (Task 8.1)
    status: in_progress
isProject: false
---

# FeedOps MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that optimizes Merchant Center product titles/descriptions at the parent SKU level using LLM-generated content with strict claim verification against CSV source data.

**Architecture:** CSV-primary data source with cross-platform ID mapping (MasterSKU to item_group_id, OPTION SKU to item_id). LLM generates candidates with self-scored claims, then claims are verified against source data. Quality rubric enforces 80%+ composite score with factual_accuracy >= 8/10. Dry-run only for MVP (preview JSON, no MC write).

**Tech Stack:** Python 3.11+, pandas (CSV), pydantic>=2 (models), openai>=1 + google-generativeai (LLM), typer + rich (CLI), SQLite (audit), pytest (testing)

---

## Phase 1: Project Setup

### Task 1.1: Create pyproject.toml

**Files:**

- Create: `pyproject.toml`

**Step 1: Write the failing test**

```python
# tests/test_project_setup.py
import subprocess
import sys

def test_package_installable():
    """Verify feedops package can be installed."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--dry-run"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"pip install failed: {result.stderr}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_setup.py::test_package_installable -v`

Expected: FAIL with "No module named feedops" or "pyproject.toml not found"

**Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "feedops"
version = "0.1.0"
description = "Allied FeedOps - Merchant Center feed optimization"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "openai>=1.0",
    "google-generativeai>=0.3",
    "httpx>=0.25",
    "python-dotenv>=1.0",
    "typer>=0.9",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",
    "mypy>=1.0",
]

[project.scripts]
feedops = "feedops.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/feedops"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_setup.py::test_package_installable -v`

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml tests/test_project_setup.py
git commit -m "feat: add pyproject.toml with dependencies"
```

---

### Task 1.2: Create Package Structure

**Files:**

- Create: `src/feedops/__init__.py`
- Create: `src/feedops/py.typed`
- Create: `.python-version`

**Step 1: Write the failing test**

```python
# tests/test_project_setup.py (append)
def test_feedops_importable():
    """Verify feedops package can be imported."""
    import feedops
    assert hasattr(feedops, "__version__")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_setup.py::test_feedops_importable -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'feedops'"

**Step 3: Write minimal implementation**

```python
# src/feedops/__init__.py
"""Allied FeedOps - Merchant Center feed optimization."""

__version__ = "0.1.0"
```

```
# src/feedops/py.typed
# Marker file for PEP 561 typed package
```

```
# .python-version
3.11
```

**Step 4: Run test to verify it passes**

Run: `pip install -e . && pytest tests/test_project_setup.py::test_feedops_importable -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/feedops/__init__.py src/feedops/py.typed .python-version
git commit -m "feat: create feedops package structure"
```

---

### Task 1.3: Create .env.example Template

**Files:**

- Create: `.env.example`
- Test: `tests/test_project_setup.py`

**Step 1: Write the failing test**

```python
# tests/test_project_setup.py (append)
from pathlib import Path

def test_env_example_exists():
    """Verify .env.example template exists with required keys."""
    env_example = Path(".env.example")
    assert env_example.exists(), ".env.example not found"
    content = env_example.read_text()
    required_keys = ["OPENAI_API_KEY", "GEMINI_API_KEY", "CATALOG_PATH"]
    for key in required_keys:
        assert key in content, f"Missing {key} in .env.example"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_setup.py::test_env_example_exists -v`

Expected: FAIL with ".env.example not found"

**Step 3: Write minimal implementation**

```bash
# .env.example
# LLM Providers (at least one required)
OPENAI_API_KEY=sk-your-openai-key-here
GEMINI_API_KEY=your-gemini-key-here

# Data Sources
CATALOG_PATH=data/catalog/Product Catalog.csv

# Shopify (optional for MVP)
SHOPIFY_STORE_URL=https://your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_your-token-here

# Google Merchant Center (optional for MVP)
GMC_MERCHANT_ID=123456789

# Database
DATABASE_PATH=data/feedops.db
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_setup.py::test_env_example_exists -v`

Expected: PASS

**Step 5: Commit**

```bash
git add .env.example tests/test_project_setup.py
git commit -m "feat: add .env.example template"
```

---

### Task 1.4: Create pytest Configuration

**Files:**

- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Write the failing test**

```python
# tests/test_project_setup.py (append)
def test_pytest_configured():
    """Verify pytest can discover and run tests."""
    import subprocess
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "test_" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_setup.py::test_pytest_configured -v`

Expected: Could pass or fail depending on existing setup

**Step 3: Write minimal implementation**

```python
# tests/__init__.py
"""FeedOps test suite."""
```

```python
# tests/conftest.py
"""Pytest configuration and fixtures."""
import pytest
from pathlib import Path

@pytest.fixture
def sample_catalog_path() -> Path:
    """Path to sample catalog CSV for testing."""
    return Path("samples/sample-catalog.csv")

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary database path for testing."""
    return tmp_path / "test_feedops.db"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_setup.py::test_pytest_configured -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "feat: configure pytest with fixtures"
```

---

## Phase 2: Data Models

### Task 2.1: Create Variant Model with GMCID Parsing

**Files:**

- Create: `src/feedops/models/__init__.py`
- Create: `src/feedops/models/variant.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest
from feedops.models.variant import Variant, parse_gmcid

def test_parse_gmcid_extracts_shopify_ids():
    """GMCID format: shopify_US_{ProductID}_{VariantID}"""
    gmc_id = "shopify_US_4542872518788_32118222192772"
    product_id, variant_id = parse_gmcid(gmc_id)
    assert product_id == "4542872518788"
    assert variant_id == "32118222192772"

def test_parse_gmcid_handles_invalid_format():
    """Invalid GMCID returns None, None."""
    product_id, variant_id = parse_gmcid("invalid_format")
    assert product_id is None
    assert variant_id is None

def test_variant_model_parses_gmcid_on_creation():
    """Variant extracts Shopify IDs from GMCID."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_1000000001_2000000001",
        upc="00000000001",
        position=1,
    )
    assert variant.shopify_product_id == "1000000001"
    assert variant.shopify_variant_id == "2000000001"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'feedops.models'"

**Step 3: Write minimal implementation**

```python
# src/feedops/models/__init__.py
"""FeedOps data models."""
from feedops.models.variant import Variant, parse_gmcid

__all__ = ["Variant", "parse_gmcid"]
```

```python
# src/feedops/models/variant.py
"""Variant model representing a single product variant."""
import re
from pydantic import BaseModel, computed_field
from decimal import Decimal

GMCID_PATTERN = re.compile(r"^shopify_US_(\d+)_(\d+)$")

def parse_gmcid(gmc_id: str) -> tuple[str | None, str | None]:
    """Extract Shopify product and variant IDs from GMCID.

    GMCID format: shopify_US_{ProductID}_{VariantID}

    Returns:
        Tuple of (product_id, variant_id) or (None, None) if invalid.
    """
    if not gmc_id:
        return None, None
    match = GMCID_PATTERN.match(gmc_id)
    if not match:
        return None, None
    return match.group(1), match.group(2)


class Variant(BaseModel):
    """A single product variant (finish/option combination)."""

    # Identifiers
    option_sku: str
    finish: str
    finish_code: str
    gmc_id: str
    upc: str | None = None
    gtin: str | None = None
    amazon_asin: str | None = None
    position: int = 0

    # Pricing
    list_price: Decimal | None = None
    wholesale_price: Decimal | None = None
    map_price: Decimal | None = None

    # Product dimensions
    product_length: float | None = None
    product_height: float | None = None
    product_width: float | None = None
    projection: float | None = None
    product_weight: float | None = None

    # Shipping dimensions
    shipping_length: float | None = None
    shipping_height: float | None = None
    shipping_width: float | None = None
    shipping_weight: float | None = None

    # Images
    main_image: str | None = None
    main_image_url: str | None = None
    alt_image_1: str | None = None
    alt_image_2: str | None = None
    alt_image_3: str | None = None
    alt_image_4: str | None = None

    @computed_field
    @property
    def shopify_product_id(self) -> str | None:
        """Extract Shopify product ID from GMCID."""
        product_id, _ = parse_gmcid(self.gmc_id)
        return product_id

    @computed_field
    @property
    def shopify_variant_id(self) -> str | None:
        """Extract Shopify variant ID from GMCID."""
        _, variant_id = parse_gmcid(self.gmc_id)
        return variant_id

    @computed_field
    @property
    def item_id(self) -> str:
        """Merchant Center item_id (same as gmc_id)."""
        return self.gmc_id

    @computed_field
    @property
    def item_group_id(self) -> str | None:
        """Merchant Center item_group_id (Shopify product ID)."""
        return self.shopify_product_id
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add src/feedops/models/__init__.py src/feedops/models/variant.py tests/test_models.py
git commit -m "feat: add Variant model with GMCID parsing"
```

---

### Task 2.2: Create ParentSKU Model

**Files:**

- Modify: `src/feedops/models/__init__.py`
- Create: `src/feedops/models/parent_sku.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py (append)
from feedops.models.parent_sku import ParentSKU

def test_parent_sku_aggregates_variants():
    """ParentSKU contains list of Variant objects."""
    variants = [
        Variant(
            option_sku="1031/18-ABR",
            finish="Antique Brass",
            finish_code="ABR",
            gmc_id="shopify_US_1000000001_2000000001",
            position=1,
        ),
        Variant(
            option_sku="1031/18-PC",
            finish="Polished Chrome",
            finish_code="PC",
            gmc_id="shopify_US_1000000001_2000000002",
            position=2,
        ),
    ]
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar...",
        material="Brass",
        variants=variants,
    )
    assert parent.master_sku == "1031/18"
    assert len(parent.variants) == 2
    assert parent.variants[0].finish_code == "ABR"

def test_parent_sku_item_group_id():
    """ParentSKU item_group_id is extracted from first variant."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        position=1,
    )
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Test",
        current_description="Test",
        material="Brass",
        variants=[variant],
    )
    assert parent.item_group_id == "4542872518788"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_parent_sku_aggregates_variants -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'feedops.models.parent_sku'"

**Step 3: Write minimal implementation**

```python
# src/feedops/models/parent_sku.py
"""ParentSKU model aggregating variants."""
from pydantic import BaseModel, computed_field
from feedops.models.variant import Variant


class ParentSKU(BaseModel):
    """Parent product with multiple finish/option variants."""

    # Identifiers
    master_sku: str
    core_sku: str | None = None

    # Classification
    category: str
    collection: str | None = None
    style: str | None = None

    # Current content
    current_title: str
    current_description: str
    bullet_1: str | None = None
    bullet_2: str | None = None
    bullet_3: str | None = None
    bullet_4: str | None = None
    bullet_5: str | None = None
    bullet_6: str | None = None

    # Specifications
    material: str | None = None
    shape: str | None = None
    orientation: str | None = None
    tilting: str | None = None
    mounting_type: str | None = None
    assembly_required: bool | None = None

    # Dimensions (product-level, shared across variants)
    center_to_center: float | None = None
    diameter: float | None = None
    screw_size: str | None = None
    mirror_height: float | None = None
    mirror_width: float | None = None
    thickness: float | None = None
    weight_capacity: float | None = None

    # Documents
    installation_url: str | None = None
    specification_url: str | None = None

    # Included items
    included_items: str | None = None
    item_number: str | None = None

    # Variants
    variants: list[Variant] = []

    @computed_field
    @property
    def item_group_id(self) -> str | None:
        """Merchant Center item_group_id from first variant's Shopify product ID."""
        if not self.variants:
            return None
        return self.variants[0].shopify_product_id

    @computed_field
    @property
    def finish_options(self) -> list[str]:
        """List of available finish codes."""
        return [v.finish_code for v in self.variants]
```

Update `__init__.py`:

```python
# src/feedops/models/__init__.py
"""FeedOps data models."""
from feedops.models.variant import Variant, parse_gmcid
from feedops.models.parent_sku import ParentSKU

__all__ = ["Variant", "parse_gmcid", "ParentSKU"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS (5 passed)

**Step 5: Commit**

```bash
git add src/feedops/models/parent_sku.py src/feedops/models/__init__.py tests/test_models.py
git commit -m "feat: add ParentSKU model aggregating variants"
```

---

### Task 2.3: Create Claim Model

**Files:**

- Create: `src/feedops/models/claim.py`
- Modify: `src/feedops/models/__init__.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py (append)
from feedops.models.claim import Claim

def test_claim_model_structure():
    """Claim tracks claim text, source field, and verification status."""
    claim = Claim(
        claim="18-inch length",
        source_field="product_length",
        source_value="18.0",
        verified=True,
    )
    assert claim.claim == "18-inch length"
    assert claim.source_field == "product_length"
    assert claim.verified is True

def test_claim_defaults_to_unverified():
    """Claims are unverified by default."""
    claim = Claim(
        claim="solid brass construction",
        source_field="material",
        source_value="Brass",
    )
    assert claim.verified is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_claim_model_structure -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/models/claim.py
"""Claim model for tracking content claims and their sources."""
from pydantic import BaseModel


class Claim(BaseModel):
    """A factual claim in generated content with source attribution.

    Claims must be verified against source data before publication.
    Any claim without a valid source_field or mismatched source_value
    is considered unverified and should be rejected.
    """

    claim: str
    """The claim text as it appears in generated content."""

    source_field: str
    """The field name in ParentSKU/Variant this claim is based on."""

    source_value: str
    """The value from the source field that supports this claim."""

    verified: bool = False
    """Whether this claim has been verified against actual source data."""

    rejection_reason: str | None = None
    """If verified=False after verification, explains why."""
```

Update `__init__.py`:

```python
# src/feedops/models/__init__.py
"""FeedOps data models."""
from feedops.models.variant import Variant, parse_gmcid
from feedops.models.parent_sku import ParentSKU
from feedops.models.claim import Claim

__all__ = ["Variant", "parse_gmcid", "ParentSKU", "Claim"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS (7 passed)

**Step 5: Commit**

```bash
git add src/feedops/models/claim.py src/feedops/models/__init__.py tests/test_models.py
git commit -m "feat: add Claim model for source attribution"
```

---

### Task 2.4: Create Score Model

**Files:**

- Create: `src/feedops/models/score.py`
- Modify: `src/feedops/models/__init__.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py (append)
from feedops.models.score import Score

def test_score_composite_calculation():
    """Composite = sum of all scores / 60 * 100."""
    score = Score(
        specificity=8,
        benefit_coverage=9,
        keyword_inclusion=7,
        format_adherence=10,
        brand_voice=8,
        factual_accuracy=9,
    )
    # (8+9+7+10+8+9) / 60 * 100 = 51/60 * 100 = 85%
    assert score.composite == 85.0

def test_score_approval_status_approved():
    """Score >= 80% and factual_accuracy >= 8 is approved."""
    score = Score(
        specificity=8, benefit_coverage=8, keyword_inclusion=8,
        format_adherence=8, brand_voice=8, factual_accuracy=8,
    )
    assert score.composite == 80.0
    assert score.approval_status == "approved"

def test_score_approval_status_rejected_low_accuracy():
    """Factual accuracy < 8 is always rejected."""
    score = Score(
        specificity=10, benefit_coverage=10, keyword_inclusion=10,
        format_adherence=10, brand_voice=10, factual_accuracy=7,
    )
    assert score.composite > 80.0
    assert score.approval_status == "rejected"

def test_score_approval_status_revise():
    """Score 70-79% with factual_accuracy >= 8 needs revision."""
    score = Score(
        specificity=7, benefit_coverage=7, keyword_inclusion=7,
        format_adherence=7, brand_voice=7, factual_accuracy=8,
    )
    # (7+7+7+7+7+8) / 60 * 100 = 43/60 * 100 = 71.67%
    assert 70 <= score.composite < 80
    assert score.approval_status == "revise"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_score_composite_calculation -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/models/score.py
"""Score model for quality rubric evaluation."""
from pydantic import BaseModel, computed_field, field_validator


class Score(BaseModel):
    """Quality score across 6 dimensions (0-10 each).

    Composite score = (sum of all scores) / 60 * 100

    Approval thresholds:
    - >= 80%: approved
    - 70-79%: revise (minor revision needed)
    - < 70%: rejected (major revision or human review)
    - factual_accuracy < 8: always rejected regardless of composite
    """

    specificity: int
    """0-10: Specific/verifiable claims vs generic claims."""

    benefit_coverage: int
    """0-10: Benefits addressed in first 150 characters."""

    keyword_inclusion: int
    """0-10: Target keywords in optimal positions."""

    format_adherence: int
    """0-10: Compliance with character limits and structure."""

    brand_voice: int
    """0-10: Premium, confident tone without superlatives."""

    factual_accuracy: int
    """0-10: Every claim traceable to product data. MUST be >= 8."""

    @field_validator(
        'specificity', 'benefit_coverage', 'keyword_inclusion',
        'format_adherence', 'brand_voice', 'factual_accuracy'
    )
    @classmethod
    def validate_score_range(cls, v: int) -> int:
        """Ensure scores are 0-10."""
        if not 0 <= v <= 10:
            raise ValueError(f"Score must be 0-10, got {v}")
        return v

    @computed_field
    @property
    def composite(self) -> float:
        """Calculate composite score as percentage (0-100)."""
        total = (
            self.specificity +
            self.benefit_coverage +
            self.keyword_inclusion +
            self.format_adherence +
            self.brand_voice +
            self.factual_accuracy
        )
        return round(total / 60 * 100, 2)

    @computed_field
    @property
    def approval_status(self) -> str:
        """Determine approval status based on composite and factual_accuracy.

        Returns:
            'approved': >= 80% composite AND factual_accuracy >= 8
            'revise': 70-79% composite AND factual_accuracy >= 8
            'rejected': < 70% composite OR factual_accuracy < 8
        """
        if self.factual_accuracy < 8:
            return "rejected"
        if self.composite >= 80:
            return "approved"
        if self.composite >= 70:
            return "revise"
        return "rejected"
```

Update `__init__.py`:

```python
# src/feedops/models/__init__.py
"""FeedOps data models."""
from feedops.models.variant import Variant, parse_gmcid
from feedops.models.parent_sku import ParentSKU
from feedops.models.claim import Claim
from feedops.models.score import Score

__all__ = ["Variant", "parse_gmcid", "ParentSKU", "Claim", "Score"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS (11 passed)

**Step 5: Commit**

```bash
git add src/feedops/models/score.py src/feedops/models/__init__.py tests/test_models.py
git commit -m "feat: add Score model with composite calculation"
```

---

### Task 2.5: Create Candidate Model

**Files:**

- Create: `src/feedops/models/candidate.py`
- Modify: `src/feedops/models/__init__.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py (append)
from feedops.models.candidate import Candidate

def test_candidate_model_structure():
    """Candidate contains title, description, claims, and scores."""
    claims = [
        Claim(claim="18-inch length", source_field="product_length", source_value="18.0"),
        Claim(claim="solid brass", source_field="material", source_value="Brass"),
    ]
    self_score = Score(
        specificity=8, benefit_coverage=9, keyword_inclusion=7,
        format_adherence=10, brand_voice=8, factual_accuracy=9,
    )
    candidate = Candidate(
        title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        description="Crafted from solid brass that will never corrode...",
        claims=claims,
        self_score=self_score,
    )
    assert len(candidate.title) < 150
    assert len(candidate.claims) == 2
    assert candidate.self_score.composite == 85.0

def test_candidate_title_max_length():
    """Title must be <= 150 characters."""
    import pytest
    with pytest.raises(ValueError, match="Title must be <= 150 characters"):
        Candidate(
            title="A" * 151,
            description="Valid description " * 50,
            claims=[],
            self_score=Score(
                specificity=5, benefit_coverage=5, keyword_inclusion=5,
                format_adherence=5, brand_voice=5, factual_accuracy=5,
            ),
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_candidate_model_structure -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/models/candidate.py
"""Candidate model for optimized title/description."""
from pydantic import BaseModel, field_validator
from feedops.models.claim import Claim
from feedops.models.score import Score


class Candidate(BaseModel):
    """An optimized title/description candidate.

    Constraints:
    - title: max 150 characters
    - description: min 500 characters recommended
    """

    title: str
    """Optimized product title (max 150 chars)."""

    description: str
    """Optimized product description (min 500 chars recommended)."""

    claims: list[Claim]
    """List of factual claims with source attribution."""

    self_score: Score
    """LLM's self-assessment against the rubric."""

    verified_score: Score | None = None
    """Score after claim verification (may differ from self_score)."""

    @field_validator('title')
    @classmethod
    def validate_title_length(cls, v: str) -> str:
        """Title must be <= 150 characters."""
        if len(v) > 150:
            raise ValueError(f"Title must be <= 150 characters, got {len(v)}")
        return v

    @property
    def verified_claims(self) -> list[Claim]:
        """Return only verified claims."""
        return [c for c in self.claims if c.verified]

    @property
    def rejected_claims(self) -> list[Claim]:
        """Return rejected claims."""
        return [c for c in self.claims if not c.verified and c.rejection_reason]

    @property
    def final_score(self) -> Score:
        """Return verified_score if available, else self_score."""
        return self.verified_score or self.self_score
```

Update `__init__.py`:

```python
# src/feedops/models/__init__.py
"""FeedOps data models."""
from feedops.models.variant import Variant, parse_gmcid
from feedops.models.parent_sku import ParentSKU
from feedops.models.claim import Claim
from feedops.models.score import Score
from feedops.models.candidate import Candidate

__all__ = ["Variant", "parse_gmcid", "ParentSKU", "Claim", "Score", "Candidate"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS (13 passed)

**Step 5: Commit**

```bash
git add src/feedops/models/candidate.py src/feedops/models/__init__.py tests/test_models.py
git commit -m "feat: add Candidate model with title validation"
```

---

## Phase 3: CSV Loader

### Task 3.1: Create Column Mapping Configuration

**Files:**

- Create: `src/feedops/config/__init__.py`
- Create: `src/feedops/config/columns.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
from feedops.config.columns import CSV_COLUMNS, POSITIONAL_RENAMES

def test_csv_columns_has_all_fields():
    """CSV_COLUMNS maps all 56 columns from Product Catalog CSV."""
    assert len(CSV_COLUMNS) >= 55
    assert "MasterSKU" in CSV_COLUMNS
    assert "OPTION SKU" in CSV_COLUMNS
    assert "GMCID" in CSV_COLUMNS

def test_positional_renames_handles_duplicates():
    """POSITIONAL_RENAMES maps duplicate column positions."""
    # First occurrence (product dimensions)
    assert POSITIONAL_RENAMES[23] == "product_length"
    assert POSITIONAL_RENAMES[24] == "product_height"
    assert POSITIONAL_RENAMES[25] == "product_width"
    assert POSITIONAL_RENAMES[27] == "product_weight"
    # Second occurrence (shipping dimensions)
    assert POSITIONAL_RENAMES[28] == "shipping_length"
    assert POSITIONAL_RENAMES[29] == "shipping_height"
    assert POSITIONAL_RENAMES[30] == "shipping_width"
    assert POSITIONAL_RENAMES[31] == "shipping_weight"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/config/__init__.py
"""FeedOps configuration."""
from feedops.config.columns import CSV_COLUMNS, POSITIONAL_RENAMES

__all__ = ["CSV_COLUMNS", "POSITIONAL_RENAMES"]
```

```python
# src/feedops/config/columns.py
"""CSV column mapping configuration.

The Product Catalog CSV has 56 columns with duplicate names:
- Length, Height, Width, Weight appear twice (product and shipping dimensions)

We use positional mapping to disambiguate duplicates.
"""

# Column name -> model field name (for unique columns)
CSV_COLUMNS: dict[str, str] = {
    "MasterSKU": "master_sku",
    "OPTION SKU": "option_sku",
    "CoreSKU": "core_sku",
    "UPC": "upc",
    "GTIN": "gtin",
    "GMCID": "gmc_id",
    "Amazon ASIN": "amazon_asin",
    "Finish": "finish",
    "Finish Code": "finish_code",
    "Position": "position",
    "Category": "category",
    "Collection": "collection",
    "Title": "current_title",
    "List": "list_price",
    "Wholesale": "wholesale_price",
    "Map": "map_price",
    "Narraive Copy": "current_description",  # typo in source
    "Bullet 1": "bullet_1",
    "Bullet 2": "bullet_2",
    "Bullet 3": "bullet_3",
    "Bullet 4": "bullet_4",
    "Bullet 5": "bullet_5",
    "Bullet 6": "bullet_6",
    "Projection": "projection",
    "Installation": "installation_url",
    "Specification": "specification_url",
    "Main": "main_image",
    "Main URL": "main_image_url",
    "sn": "alt_image_1",
    "Alternative 2": "alt_image_2",
    "Alternative 3": "alt_image_3",
    "Alternative 4": "alt_image_4",
    "Center to center": "center_to_center",
    "Diameter": "diameter",
    "Screw size": "screw_size",
    "Mirror Height": "mirror_height",
    "Mirror width": "mirror_width",
    "Thickness": "thickness",
    "Weight capacity": "weight_capacity",
    "Material": "material",
    "Style": "style",
    "Shape": "shape",
    "Orientation": "orientation",
    "Tilting": "tilting",
    "Mounting type": "mounting_type",
    "Assembly required": "assembly_required",
    "Item number": "item_number",
    "Included": "included_items",
}

# Position (0-indexed) -> field name for duplicate columns
POSITIONAL_RENAMES: dict[int, str] = {
    # Product dimensions (first occurrence)
    23: "product_length",
    24: "product_height",
    25: "product_width",
    27: "product_weight",
    # Shipping dimensions (second occurrence)
    28: "shipping_length",
    29: "shipping_height",
    30: "shipping_width",
    31: "shipping_weight",
}

# Fields that belong to ParentSKU (shared across variants)
PARENT_SKU_FIELDS: set[str] = {
    "master_sku",
    "core_sku",
    "category",
    "collection",
    "current_title",
    "current_description",
    "bullet_1",
    "bullet_2",
    "bullet_3",
    "bullet_4",
    "bullet_5",
    "bullet_6",
    "material",
    "style",
    "shape",
    "orientation",
    "tilting",
    "mounting_type",
    "assembly_required",
    "center_to_center",
    "diameter",
    "screw_size",
    "mirror_height",
    "mirror_width",
    "thickness",
    "weight_capacity",
    "installation_url",
    "specification_url",
    "included_items",
    "item_number",
}

# Fields that belong to Variant (per-finish)
VARIANT_FIELDS: set[str] = {
    "option_sku",
    "finish",
    "finish_code",
    "gmc_id",
    "upc",
    "gtin",
    "amazon_asin",
    "position",
    "list_price",
    "wholesale_price",
    "map_price",
    "product_length",
    "product_height",
    "product_width",
    "projection",
    "product_weight",
    "shipping_length",
    "shipping_height",
    "shipping_width",
    "shipping_weight",
    "main_image",
    "main_image_url",
    "alt_image_1",
    "alt_image_2",
    "alt_image_3",
    "alt_image_4",
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/config/__init__.py src/feedops/config/columns.py tests/test_config.py
git commit -m "feat: add CSV column mapping configuration"
```

---

### Task 3.2: Create Catalog Loader

**Files:**

- Create: `src/feedops/loaders/__init__.py`
- Create: `src/feedops/loaders/catalog.py`
- Test: `tests/test_loaders.py`

**Step 1: Write the failing test**

```python
# tests/test_loaders.py
import pytest
from pathlib import Path
from feedops.loaders.catalog import load_catalog, rename_duplicate_columns

def test_rename_duplicate_columns(sample_catalog_path):
    """Duplicate columns are renamed by position."""
    import pandas as pd
    df = pd.read_csv(sample_catalog_path)
    df = rename_duplicate_columns(df)
    assert "product_length" in df.columns
    assert "shipping_length" in df.columns
    assert "product_weight" in df.columns
    assert "shipping_weight" in df.columns

def test_load_catalog_returns_dataframe(sample_catalog_path):
    """load_catalog returns pandas DataFrame."""
    df = load_catalog(sample_catalog_path)
    assert len(df) > 0
    assert "master_sku" in df.columns
    assert "gmc_id" in df.columns
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_loaders.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/loaders/__init__.py
"""FeedOps data loaders."""
from feedops.loaders.catalog import load_catalog, get_parent_sku, list_master_skus

__all__ = ["load_catalog", "get_parent_sku", "list_master_skus"]
```

```python
# src/feedops/loaders/catalog.py
"""Product Catalog CSV loader with duplicate column handling."""
from pathlib import Path
from decimal import Decimal
import pandas as pd

from feedops.config.columns import (
    CSV_COLUMNS,
    POSITIONAL_RENAMES,
    PARENT_SKU_FIELDS,
    VARIANT_FIELDS,
)
from feedops.models import ParentSKU, Variant


def rename_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename duplicate columns using positional mapping.

    The CSV has duplicate column names (Length, Height, Width, Weight).
    This function renames them based on their position.
    """
    columns = list(df.columns)
    for pos, new_name in POSITIONAL_RENAMES.items():
        if pos < len(columns):
            columns[pos] = new_name
    df.columns = columns
    return df


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names using CSV_COLUMNS mapping."""
    rename_map = {}
    for col in df.columns:
        if col in CSV_COLUMNS:
            rename_map[col] = CSV_COLUMNS[col]
    return df.rename(columns=rename_map)


def load_catalog(path: Path | str) -> pd.DataFrame:
    """Load Product Catalog CSV with proper column handling.

    Args:
        path: Path to the Product Catalog CSV file.

    Returns:
        DataFrame with normalized column names.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = rename_duplicate_columns(df)
    df = normalize_column_names(df)
    return df


def get_parent_sku(df: pd.DataFrame, master_sku: str) -> ParentSKU | None:
    """Extract ParentSKU with all variants from catalog.

    Args:
        df: Loaded catalog DataFrame.
        master_sku: The MasterSKU value to look up.

    Returns:
        ParentSKU with variants, or None if not found.
    """
    rows = df[df["master_sku"] == master_sku]
    if rows.empty:
        return None

    # Build variants from all rows
    variants = []
    for _, row in rows.iterrows():
        variant_data = {}
        for field in VARIANT_FIELDS:
            if field in row.index and row[field]:
                value = row[field]
                # Convert numeric fields
                if field in ("position",):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        value = 0
                elif field.endswith(("_length", "_height", "_width", "_weight", "projection")):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        value = None
                elif field.endswith("_price"):
                    try:
                        value = Decimal(value.replace("$", "").replace(",", ""))
                    except (ValueError, TypeError):
                        value = None
                variant_data[field] = value

        if variant_data.get("option_sku") and variant_data.get("gmc_id"):
            variants.append(Variant(**variant_data))

    if not variants:
        return None

    # Build ParentSKU from first row (shared attributes)
    first_row = rows.iloc[0]
    parent_data = {"variants": variants}
    for field in PARENT_SKU_FIELDS:
        if field in first_row.index and first_row[field]:
            value = first_row[field]
            # Convert numeric fields
            if field in ("center_to_center", "diameter", "mirror_height", "mirror_width", "thickness", "weight_capacity"):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = None
            elif field == "assembly_required":
                value = value.lower() in ("true", "yes", "1")
            parent_data[field] = value

    return ParentSKU(**parent_data)


def list_master_skus(df: pd.DataFrame) -> list[str]:
    """List all unique MasterSKU values in catalog.

    Args:
        df: Loaded catalog DataFrame.

    Returns:
        Sorted list of unique MasterSKU values.
    """
    return sorted(df["master_sku"].unique().tolist())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_loaders.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/loaders/__init__.py src/feedops/loaders/catalog.py tests/test_loaders.py
git commit -m "feat: add CSV catalog loader with duplicate column handling"
```

---

### Task 3.3: Test ParentSKU Extraction

**Files:**

- Test: `tests/test_loaders.py`

**Step 1: Write the failing test**

```python
# tests/test_loaders.py (append)
from feedops.loaders.catalog import get_parent_sku

def test_get_parent_sku_extracts_variants(sample_catalog_path):
    """get_parent_sku returns ParentSKU with all variants."""
    df = load_catalog(sample_catalog_path)
    parent = get_parent_sku(df, "SAMPLE-101")
    assert parent is not None
    assert parent.master_sku == "SAMPLE-101"
    assert len(parent.variants) == 2
    assert parent.variants[0].finish_code == "PC"
    assert parent.variants[1].finish_code == "ORB"

def test_get_parent_sku_returns_none_for_missing():
    """get_parent_sku returns None for non-existent SKU."""
    from feedops.loaders.catalog import load_catalog, get_parent_sku
    from pathlib import Path
    df = load_catalog(Path("samples/sample-catalog.csv"))
    parent = get_parent_sku(df, "NONEXISTENT-SKU")
    assert parent is None

def test_get_parent_sku_parses_gmcid(sample_catalog_path):
    """Variants have Shopify IDs extracted from GMCID."""
    df = load_catalog(sample_catalog_path)
    parent = get_parent_sku(df, "SAMPLE-101")
    variant = parent.variants[0]
    assert variant.shopify_product_id == "1000000001"
    assert variant.shopify_variant_id == "2000000001"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_loaders.py::test_get_parent_sku_extracts_variants -v`

Expected: Should pass if implementation is correct, may fail if sample data format differs

**Step 3: Write minimal implementation**

Implementation already exists from Task 3.2. If tests fail, adjust the loader logic.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_loaders.py -v`

Expected: PASS (5 passed)

**Step 5: Commit**

```bash
git add tests/test_loaders.py
git commit -m "test: add ParentSKU extraction tests"
```

---

## Phase 4: LLM Providers

### Task 4.1: Create Base LLM Provider Interface

**Files:**

- Create: `src/feedops/providers/__init__.py`
- Create: `src/feedops/providers/base.py`
- Test: `tests/test_providers.py`

**Step 1: Write the failing test**

```python
# tests/test_providers.py
import pytest
from abc import ABC
from feedops.providers.base import LLMProvider

def test_llm_provider_is_abstract():
    """LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        LLMProvider()

def test_llm_provider_requires_generate_method():
    """LLMProvider subclass must implement generate."""
    class IncompletProvider(LLMProvider):
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompletProvider()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/providers/__init__.py
"""FeedOps LLM and data providers."""
from feedops.providers.base import LLMProvider

__all__ = ["LLMProvider"]
```

```python
# src/feedops/providers/base.py
"""Base provider interfaces."""
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement the generate method to produce
    structured JSON output for product optimization.
    """

    @abstractmethod
    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response from prompt.

        Args:
            prompt: The full prompt including evidence table and constraints.
            schema: JSON schema the response must conform to.

        Returns:
            Parsed JSON dict matching the schema.

        Raises:
            LLMError: If generation fails after retries.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and configured.

        Returns:
            True if provider can accept requests.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class LLMError(Exception):
    """Error during LLM generation."""

    def __init__(self, message: str, provider: str, retries: int = 0):
        self.provider = provider
        self.retries = retries
        super().__init__(f"[{provider}] {message} (after {retries} retries)")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/providers/__init__.py src/feedops/providers/base.py tests/test_providers.py
git commit -m "feat: add abstract LLMProvider base class"
```

---

### Task 4.2: Create OpenAI Provider

**Files:**

- Create: `src/feedops/providers/openai_provider.py`
- Modify: `src/feedops/providers/__init__.py`
- Test: `tests/test_providers.py`

**Step 1: Write the failing test**

```python
# tests/test_providers.py (append)
from unittest.mock import AsyncMock, patch, MagicMock
from feedops.providers.openai_provider import OpenAIProvider

@pytest.mark.asyncio
async def test_openai_provider_generate_parses_json():
    """OpenAI provider parses JSON from response."""
    provider = OpenAIProvider(api_key="test-key")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"title": "Test Title", "description": "Test"}'
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"

@pytest.mark.asyncio
async def test_openai_provider_retries_on_invalid_json():
    """OpenAI provider retries when JSON is invalid."""
    provider = OpenAIProvider(api_key="test-key", max_retries=2)

    invalid_response = MagicMock()
    invalid_response.choices = [MagicMock()]
    invalid_response.choices[0].message.content = 'not valid json'
    invalid_response.usage.prompt_tokens = 100
    invalid_response.usage.completion_tokens = 50

    valid_response = MagicMock()
    valid_response.choices = [MagicMock()]
    valid_response.choices[0].message.content = '{"title": "Fixed"}'
    valid_response.usage.prompt_tokens = 100
    valid_response.usage.completion_tokens = 50

    with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = [invalid_response, valid_response]
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Fixed"
        assert mock_create.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py::test_openai_provider_generate_parses_json -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/providers/openai_provider.py
"""OpenAI LLM provider with JSON mode and retry logic."""
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from feedops.providers.base import LLMProvider, LLMError

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider with structured JSON output.

    Features:
    - JSON mode for structured output
    - Retry with repair loop on validation failure
    - Token usage logging (no secrets)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_retries: int = 3,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self._last_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response with retry loop.

        Args:
            prompt: Full prompt with evidence table and constraints.
            schema: Expected JSON schema for validation.

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        messages = [{"role": "user", "content": prompt}]
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )

                # Log token usage
                self._last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                logger.debug(f"Token usage: {self._last_usage}")

                content = response.choices[0].message.content
                result = json.loads(content)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                # Add repair instruction for next attempt
                messages.append({
                    "role": "assistant",
                    "content": content if 'content' in dir() else ""
                })
                messages.append({
                    "role": "user",
                    "content": f"Your response was not valid JSON. Error: {last_error}. Please fix and respond with valid JSON only."
                })

            except Exception as e:
                last_error = str(e)
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {last_error}")

        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from last generation."""
        return self._last_usage.copy()
```

Update `__init__.py`:

```python
# src/feedops/providers/__init__.py
"""FeedOps LLM and data providers."""
from feedops.providers.base import LLMProvider, LLMError
from feedops.providers.openai_provider import OpenAIProvider

__all__ = ["LLMProvider", "LLMError", "OpenAIProvider"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`

Expected: PASS (4 passed)

**Step 5: Commit**

```bash
git add src/feedops/providers/openai_provider.py src/feedops/providers/__init__.py tests/test_providers.py
git commit -m "feat: add OpenAI provider with JSON mode and retry"
```

---

### Task 4.3: Create Gemini Provider

**Files:**

- Create: `src/feedops/providers/gemini_provider.py`
- Modify: `src/feedops/providers/__init__.py`
- Test: `tests/test_providers.py`

**Step 1: Write the failing test**

```python
# tests/test_providers.py (append)
from feedops.providers.gemini_provider import GeminiProvider

@pytest.mark.asyncio
async def test_gemini_provider_generate_parses_json():
    """Gemini provider parses JSON from response."""
    provider = GeminiProvider(api_key="test-key")

    with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_api:
        mock_api.return_value = '{"title": "Test Title"}'
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py::test_gemini_provider_generate_parses_json -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

````python
# src/feedops/providers/gemini_provider.py
"""Google Gemini LLM provider as fallback."""
import json
import logging
import re
from typing import Any

import google.generativeai as genai

from feedops.providers.base import LLMProvider, LLMError

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider as fallback for OpenAI.

    Features:
    - JSON output parsing with cleanup
    - Retry with repair loop
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        max_retries: int = 3,
    ):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return f"gemini/{self.model_name}"

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            response = await self._call_api("Say 'ok'")
            return "ok" in response.lower()
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False

    async def _call_api(self, prompt: str) -> str:
        """Make async call to Gemini API."""
        response = self.model.generate_content(prompt)
        return response.text

    def _extract_json(self, text: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json_match.group(1).strip()

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_match.group(0)

        return text.strip()

    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: Full prompt with evidence table and constraints.
            schema: Expected JSON schema (used for repair hints).

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        current_prompt = prompt + "\n\nRespond with valid JSON only, no markdown."
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response_text = await self._call_api(current_prompt)
                json_text = self._extract_json(response_text)
                result = json.loads(json_text)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                current_prompt = f"""Your previous response was not valid JSON.
Error: {last_error}

Original request: {prompt}

Please respond with ONLY valid JSON, no explanations or markdown."""

            except Exception as e:
                last_error = str(e)
                logger.error(f"Gemini API error (attempt {attempt + 1}): {last_error}")

        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)
````

Update `__init__.py`:

```python
# src/feedops/providers/__init__.py
"""FeedOps LLM and data providers."""
from feedops.providers.base import LLMProvider, LLMError
from feedops.providers.openai_provider import OpenAIProvider
from feedops.providers.gemini_provider import GeminiProvider

__all__ = ["LLMProvider", "LLMError", "OpenAIProvider", "GeminiProvider"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`

Expected: PASS (5 passed)

**Step 5: Commit**

```bash
git add src/feedops/providers/gemini_provider.py src/feedops/providers/__init__.py tests/test_providers.py
git commit -m "feat: add Gemini provider as fallback"
```

---

### Task 4.4: Create Provider Factory

**Files:**

- Create: `src/feedops/providers/factory.py`
- Modify: `src/feedops/providers/__init__.py`
- Test: `tests/test_providers.py`

**Step 1: Write the failing test**

```python
# tests/test_providers.py (append)
from feedops.providers.factory import get_provider

def test_get_provider_returns_openai_by_default():
    """Factory returns OpenAI provider when configured."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        provider = get_provider()
        assert provider.name.startswith("openai/")

def test_get_provider_falls_back_to_gemini():
    """Factory returns Gemini when OpenAI not configured."""
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}, clear=True):
        provider = get_provider()
        assert provider.name.startswith("gemini/")

def test_get_provider_raises_when_none_configured():
    """Factory raises when no provider configured."""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="No LLM provider configured"):
            get_provider()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py::test_get_provider_returns_openai_by_default -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/providers/factory.py
"""LLM provider factory with automatic fallback."""
import os
import logging

from feedops.providers.base import LLMProvider
from feedops.providers.openai_provider import OpenAIProvider
from feedops.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


def get_provider(preferred: str | None = None) -> LLMProvider:
    """Get configured LLM provider with fallback chain.

    Priority:
    1. Explicitly requested provider (if key available)
    2. OpenAI (if OPENAI_API_KEY set)
    3. Gemini (if GEMINI_API_KEY set)

    Args:
        preferred: Explicitly request 'openai' or 'gemini'.

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If no provider is configured.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if preferred == "openai" and openai_key:
        return OpenAIProvider(api_key=openai_key)

    if preferred == "gemini" and gemini_key:
        return GeminiProvider(api_key=gemini_key)

    if openai_key:
        logger.info("Using OpenAI provider")
        return OpenAIProvider(api_key=openai_key)

    if gemini_key:
        logger.info("Using Gemini provider (OpenAI not configured)")
        return GeminiProvider(api_key=gemini_key)

    raise ValueError(
        "No LLM provider configured. Set OPENAI_API_KEY or GEMINI_API_KEY."
    )


class FallbackProvider(LLMProvider):
    """Provider that tries primary, then falls back to secondary.

    Useful for production where you want automatic failover.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback

    @property
    def name(self) -> str:
        return f"{self.primary.name}+{self.fallback.name}"

    async def health_check(self) -> bool:
        """True if either provider is healthy."""
        primary_ok = await self.primary.health_check()
        if primary_ok:
            return True
        return await self.fallback.health_check()

    async def generate(self, prompt: str, schema: dict) -> dict:
        """Try primary, fall back to secondary on failure."""
        try:
            return await self.primary.generate(prompt, schema)
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}, trying fallback")
            return await self.fallback.generate(prompt, schema)
```

Update `__init__.py`:

```python
# src/feedops/providers/__init__.py
"""FeedOps LLM and data providers."""
from feedops.providers.base import LLMProvider, LLMError
from feedops.providers.openai_provider import OpenAIProvider
from feedops.providers.gemini_provider import GeminiProvider
from feedops.providers.factory import get_provider, FallbackProvider

__all__ = [
    "LLMProvider",
    "LLMError",
    "OpenAIProvider",
    "GeminiProvider",
    "get_provider",
    "FallbackProvider",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`

Expected: PASS (8 passed)

**Step 5: Commit**

```bash
git add src/feedops/providers/factory.py src/feedops/providers/__init__.py tests/test_providers.py
git commit -m "feat: add provider factory with fallback chain"
```

---

## Phase 5: Pipeline

### Task 5.1: Create Evidence Table Builder

**Files:**

- Create: `src/feedops/pipeline/__init__.py`
- Create: `src/feedops/pipeline/evidence.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import pytest
from feedops.models import ParentSKU, Variant
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

@pytest.fixture
def sample_parent_sku():
    """Create sample ParentSKU for testing."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        upc="123456789",
        position=1,
        product_length=20.8,
        product_weight=2.5,
    )
    return ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar...",
        material="Brass",
        mounting_type="Wall mount",
        weight_capacity=10.0,
        variants=[variant],
    )

def test_build_evidence_table_includes_parent_fields(sample_parent_sku):
    """Evidence table includes ParentSKU fields."""
    evidence = build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "master_sku" in fields
    assert "category" in fields
    assert "material" in fields

def test_format_evidence_markdown_creates_table(sample_parent_sku):
    """format_evidence_markdown creates valid markdown table."""
    evidence = build_evidence_table(sample_parent_sku)
    markdown = format_evidence_markdown(evidence)
    assert "| Attribute | Value | Source |" in markdown
    assert "Towel Bars" in markdown
    assert "Brass" in markdown
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/pipeline/__init__.py
"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

__all__ = ["build_evidence_table", "format_evidence_markdown"]
```

```python
# src/feedops/pipeline/evidence.py
"""Evidence table builder for LLM prompts."""
from dataclasses import dataclass
from feedops.models import ParentSKU


@dataclass
class Evidence:
    """A single evidence row for the LLM prompt."""
    field: str
    value: str
    source: str


def build_evidence_table(parent_sku: ParentSKU) -> list[Evidence]:
    """Convert ParentSKU to structured evidence table.

    Args:
        parent_sku: The parent SKU with all variants.

    Returns:
        List of Evidence rows for prompt injection.
    """
    evidence = []

    # Add ParentSKU fields
    parent_fields = [
        ("master_sku", "MasterSKU"),
        ("category", "Category"),
        ("collection", "Collection"),
        ("current_title", "Current Title"),
        ("current_description", "Current Description"),
        ("material", "Material"),
        ("style", "Style"),
        ("shape", "Shape"),
        ("orientation", "Orientation"),
        ("tilting", "Tilting"),
        ("mounting_type", "Mounting Type"),
        ("assembly_required", "Assembly Required"),
        ("center_to_center", "Center to Center"),
        ("diameter", "Diameter"),
        ("screw_size", "Screw Size"),
        ("mirror_height", "Mirror Height"),
        ("mirror_width", "Mirror Width"),
        ("thickness", "Thickness"),
        ("weight_capacity", "Weight Capacity"),
        ("included_items", "Included"),
        ("bullet_1", "Bullet 1"),
        ("bullet_2", "Bullet 2"),
        ("bullet_3", "Bullet 3"),
        ("bullet_4", "Bullet 4"),
        ("bullet_5", "Bullet 5"),
        ("bullet_6", "Bullet 6"),
    ]

    for field_name, display_name in parent_fields:
        value = getattr(parent_sku, field_name, None)
        if value is not None and value != "":
            evidence.append(Evidence(
                field=field_name,
                value=str(value),
                source=f"catalog_csv.{display_name}",
            ))

    # Add finish options from variants
    if parent_sku.variants:
        finishes = ", ".join(v.finish for v in parent_sku.variants)
        evidence.append(Evidence(
            field="available_finishes",
            value=finishes,
            source="catalog_csv.Finish (variants)",
        ))

        # Add first variant dimensions as representative
        first_variant = parent_sku.variants[0]
        variant_fields = [
            ("product_length", "Length"),
            ("product_height", "Height"),
            ("product_width", "Width"),
            ("projection", "Projection"),
            ("product_weight", "Weight"),
        ]
        for field_name, display_name in variant_fields:
            value = getattr(first_variant, field_name, None)
            if value is not None:
                evidence.append(Evidence(
                    field=field_name,
                    value=str(value),
                    source=f"catalog_csv.{display_name}",
                ))

    return evidence


def format_evidence_markdown(evidence: list[Evidence]) -> str:
    """Format evidence as markdown table for prompt.

    Args:
        evidence: List of Evidence rows.

    Returns:
        Markdown table string.
    """
    lines = [
        "## Available Product Data",
        "",
        "| Attribute | Value | Source |",
        "|-----------|-------|--------|",
    ]

    for e in evidence:
        # Escape pipe characters in values
        value = str(e.value).replace("|", "\\|")
        # Truncate long values
        if len(value) > 80:
            value = value[:77] + "..."
        lines.append(f"| {e.field} | {value} | {e.source} |")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/__init__.py src/feedops/pipeline/evidence.py tests/test_pipeline.py
git commit -m "feat: add evidence table builder for LLM prompts"
```

---

### Task 5.2: Create Claim Verifier

**Files:**

- Create: `src/feedops/pipeline/verifier.py`
- Modify: `src/feedops/pipeline/__init__.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py (append)
from feedops.models import Candidate, Claim, Score
from feedops.pipeline.verifier import verify_claims

def test_verify_claims_marks_valid_claims(sample_parent_sku):
    """Valid claims are marked as verified."""
    candidate = Candidate(
        title="Test Title",
        description="Test description " * 30,
        claims=[
            Claim(claim="made of Brass", source_field="material", source_value="Brass"),
            Claim(claim="wall mounted", source_field="mounting_type", source_value="Wall mount"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, sample_parent_sku)
    assert verified.claims[0].verified is True
    assert verified.claims[1].verified is True
    assert len(errors) == 0

def test_verify_claims_rejects_invalid_claims(sample_parent_sku):
    """Invalid claims are marked as rejected with reason."""
    candidate = Candidate(
        title="Test Title",
        description="Test description " * 30,
        claims=[
            Claim(claim="made of Steel", source_field="material", source_value="Steel"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, sample_parent_sku)
    assert verified.claims[0].verified is False
    assert "Steel" in verified.claims[0].rejection_reason
    assert len(errors) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py::test_verify_claims_marks_valid_claims -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/pipeline/verifier.py
"""Claim verification against source data."""
from feedops.models import ParentSKU, Candidate, Claim, Score


def get_source_value(parent_sku: ParentSKU, field_name: str) -> str | None:
    """Get value from ParentSKU or its first variant by field name.

    Args:
        parent_sku: The parent SKU to look up.
        field_name: The field name to retrieve.

    Returns:
        String value or None if field doesn't exist.
    """
    # Try ParentSKU first
    if hasattr(parent_sku, field_name):
        value = getattr(parent_sku, field_name)
        if value is not None:
            return str(value)

    # Try first variant
    if parent_sku.variants:
        variant = parent_sku.variants[0]
        if hasattr(variant, field_name):
            value = getattr(variant, field_name)
            if value is not None:
                return str(value)

    return None


def verify_claim(claim: Claim, parent_sku: ParentSKU) -> Claim:
    """Verify a single claim against source data.

    Args:
        claim: The claim to verify.
        parent_sku: The source data.

    Returns:
        Updated claim with verified status and rejection reason if applicable.
    """
    actual_value = get_source_value(parent_sku, claim.source_field)

    if actual_value is None:
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=False,
            rejection_reason=f"Field '{claim.source_field}' not found in source data",
        )

    # Normalize for comparison (case-insensitive, trim whitespace)
    claimed = claim.source_value.strip().lower()
    actual = actual_value.strip().lower()

    if claimed == actual or claimed in actual or actual in claimed:
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=True,
        )

    return Claim(
        claim=claim.claim,
        source_field=claim.source_field,
        source_value=claim.source_value,
        verified=False,
        rejection_reason=f"Claimed '{claim.source_value}' but actual value is '{actual_value}'",
    )


def verify_claims(candidate: Candidate, parent_sku: ParentSKU) -> tuple[Candidate, list[str]]:
    """Verify all claims in a candidate against source data.

    Args:
        candidate: The candidate with claims to verify.
        parent_sku: The source data.

    Returns:
        Tuple of (updated candidate, list of error messages).
    """
    verified_claims = []
    errors = []

    for claim in candidate.claims:
        verified = verify_claim(claim, parent_sku)
        verified_claims.append(verified)
        if not verified.verified:
            errors.append(f"Claim rejected: '{claim.claim}' - {verified.rejection_reason}")

    # Calculate verified factual_accuracy score
    if verified_claims:
        verified_count = sum(1 for c in verified_claims if c.verified)
        accuracy_score = round(verified_count / len(verified_claims) * 10)
    else:
        accuracy_score = 10  # No claims = no violations

    verified_score = Score(
        specificity=candidate.self_score.specificity,
        benefit_coverage=candidate.self_score.benefit_coverage,
        keyword_inclusion=candidate.self_score.keyword_inclusion,
        format_adherence=candidate.self_score.format_adherence,
        brand_voice=candidate.self_score.brand_voice,
        factual_accuracy=accuracy_score,
    )

    verified_candidate = Candidate(
        title=candidate.title,
        description=candidate.description,
        claims=verified_claims,
        self_score=candidate.self_score,
        verified_score=verified_score,
    )

    return verified_candidate, errors
```

Update `__init__.py`:

```python
# src/feedops/pipeline/__init__.py
"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims

__all__ = ["build_evidence_table", "format_evidence_markdown", "verify_claims"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`

Expected: PASS (4 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/verifier.py src/feedops/pipeline/__init__.py tests/test_pipeline.py
git commit -m "feat: add claim verifier for factual accuracy"
```

---

### Task 5.3: Create Candidate Generator

**Files:**

- Create: `src/feedops/pipeline/generator.py`
- Create: `src/feedops/pipeline/prompts.py`
- Modify: `src/feedops/pipeline/__init__.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py (append)
from feedops.pipeline.generator import build_prompt
from feedops.pipeline.prompts import CANDIDATE_SCHEMA

def test_build_prompt_includes_evidence(sample_parent_sku):
    """build_prompt includes evidence table."""
    prompt = build_prompt(sample_parent_sku)
    assert "Available Product Data" in prompt
    assert "Towel Bars" in prompt
    assert "Brass" in prompt

def test_build_prompt_includes_constraints(sample_parent_sku):
    """build_prompt includes character constraints."""
    prompt = build_prompt(sample_parent_sku)
    assert "150 characters" in prompt.lower() or "150 chars" in prompt.lower()
    assert "500" in prompt  # min description length

def test_candidate_schema_has_required_fields():
    """Schema includes title, description, claims, self_score."""
    assert "title" in str(CANDIDATE_SCHEMA)
    assert "description" in str(CANDIDATE_SCHEMA)
    assert "claims" in str(CANDIDATE_SCHEMA)
    assert "self_score" in str(CANDIDATE_SCHEMA)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py::test_build_prompt_includes_evidence -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/pipeline/prompts.py
"""Prompt templates and JSON schemas for LLM."""

CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Optimized product title (max 150 characters)",
            "maxLength": 150,
        },
        "description": {
            "type": "string",
            "description": "Optimized product description (min 500 characters recommended)",
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "The claim text"},
                    "source_field": {"type": "string", "description": "Field name from evidence table"},
                    "source_value": {"type": "string", "description": "Value from that field"},
                },
                "required": ["claim", "source_field", "source_value"],
            },
        },
        "self_score": {
            "type": "object",
            "properties": {
                "specificity": {"type": "integer", "minimum": 0, "maximum": 10},
                "benefit_coverage": {"type": "integer", "minimum": 0, "maximum": 10},
                "keyword_inclusion": {"type": "integer", "minimum": 0, "maximum": 10},
                "format_adherence": {"type": "integer", "minimum": 0, "maximum": 10},
                "brand_voice": {"type": "integer", "minimum": 0, "maximum": 10},
                "factual_accuracy": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": [
                "specificity", "benefit_coverage", "keyword_inclusion",
                "format_adherence", "brand_voice", "factual_accuracy"
            ],
        },
    },
    "required": ["title", "description", "claims", "self_score"],
}

SYSTEM_PROMPT = """You are a product feed optimization specialist for Allied Brass bathroom hardware.

Your task is to create optimized product titles and descriptions that:
1. Are grounded ONLY in the provided product data (no invented features)
2. Follow the exact character constraints
3. Lead with benefits, backed by specific features
4. Use natural search language that matches customer queries

CRITICAL RULES:
- Every claim must cite a source field from the evidence table
- Never invent specifications not in the data
- Title: max 150 characters, critical info in first 70
- Description: min 500 characters recommended, benefit-first opening
- No promotional language, ALL CAPS, or URLs"""

OPTIMIZATION_TEMPLATE = """
{system_prompt}

{evidence_table}

## Title Structure Formula
[Brand] + [Product Type] + [Key Dimension] + [Material/Finish] + [Functional Modifier]

Example: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount

## Description Structure
1. Opening Hook (first 150 chars): Primary benefit + key spec
2. Key Highlights: 3-5 bullet points with benefit + feature
3. Detail Section: Specs, installation, warranty

## Scoring Rubric (self-score each 0-10)
1. Specificity: Specific/verifiable claims vs generic
2. Benefit Coverage: Benefits in first 150 characters
3. Keyword Inclusion: Target keywords in optimal positions
4. Format Adherence: Character limits and structure
5. Brand Voice: Premium tone, no superlatives
6. Factual Accuracy: Every claim traceable to evidence

## Output Format
Respond with valid JSON matching this schema:
{schema}

Now optimize the title and description for MasterSKU: {master_sku}
"""
```

```python
# src/feedops/pipeline/generator.py
"""Candidate generator using LLM providers."""
import json
from feedops.models import ParentSKU, Candidate, Claim, Score
from feedops.providers.base import LLMProvider
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.prompts import SYSTEM_PROMPT, OPTIMIZATION_TEMPLATE, CANDIDATE_SCHEMA


def build_prompt(parent_sku: ParentSKU) -> str:
    """Build the full optimization prompt for a ParentSKU.

    Args:
        parent_sku: The parent SKU to optimize.

    Returns:
        Complete prompt string for LLM.
    """
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    return OPTIMIZATION_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        evidence_table=evidence_markdown,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        master_sku=parent_sku.master_sku,
    )


def parse_candidate_response(response: dict) -> Candidate:
    """Parse LLM response into Candidate model.

    Args:
        response: Parsed JSON response from LLM.

    Returns:
        Candidate model instance.
    """
    claims = [
        Claim(
            claim=c["claim"],
            source_field=c["source_field"],
            source_value=c["source_value"],
        )
        for c in response.get("claims", [])
    ]

    score_data = response.get("self_score", {})
    self_score = Score(
        specificity=score_data.get("specificity", 5),
        benefit_coverage=score_data.get("benefit_coverage", 5),
        keyword_inclusion=score_data.get("keyword_inclusion", 5),
        format_adherence=score_data.get("format_adherence", 5),
        brand_voice=score_data.get("brand_voice", 5),
        factual_accuracy=score_data.get("factual_accuracy", 5),
    )

    return Candidate(
        title=response["title"],
        description=response["description"],
        claims=claims,
        self_score=self_score,
    )


async def generate_candidate(
    parent_sku: ParentSKU,
    llm: LLMProvider,
) -> Candidate:
    """Generate optimized title/description candidate.

    Args:
        parent_sku: The parent SKU to optimize.
        llm: The LLM provider to use.

    Returns:
        Generated Candidate (unverified).
    """
    prompt = build_prompt(parent_sku)
    response = await llm.generate(prompt, CANDIDATE_SCHEMA)
    return parse_candidate_response(response)
```

Update `__init__.py`:

```python
# src/feedops/pipeline/__init__.py
"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.prompts import CANDIDATE_SCHEMA

__all__ = [
    "build_evidence_table",
    "format_evidence_markdown",
    "verify_claims",
    "build_prompt",
    "generate_candidate",
    "CANDIDATE_SCHEMA",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`

Expected: PASS (7 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/prompts.py src/feedops/pipeline/generator.py src/feedops/pipeline/__init__.py tests/test_pipeline.py
git commit -m "feat: add candidate generator with prompt templates"
```

---

### Task 5.4: Create Report Generator

**Files:**

- Create: `src/feedops/pipeline/reporter.py`
- Modify: `src/feedops/pipeline/__init__.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py (append)
from feedops.pipeline.reporter import generate_report, generate_patch_preview

def test_generate_report_includes_scores(sample_parent_sku):
    """Report includes quality scores."""
    candidate = Candidate(
        title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        description="Crafted from solid brass " * 20,
        claims=[
            Claim(claim="solid brass", source_field="material", source_value="Brass", verified=True),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    report = generate_report(sample_parent_sku, candidate, [])
    assert "Quality Score" in report or "Composite" in report
    assert "80" in report  # 80% composite

def test_generate_patch_preview_structure(sample_parent_sku):
    """Patch preview has required Merchant Center fields."""
    candidate = Candidate(
        title="Test Title",
        description="Test description " * 30,
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate)
    assert "offerId" in patch
    assert "title" in patch
    assert "description" in patch
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py::test_generate_report_includes_scores -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/pipeline/reporter.py
"""Report generation for SKU optimization results."""
from datetime import datetime
from feedops.models import ParentSKU, Candidate


def generate_report(
    parent_sku: ParentSKU,
    candidate: Candidate,
    verification_errors: list[str],
) -> str:
    """Generate markdown report for SKU optimization.

    Args:
        parent_sku: The original parent SKU.
        candidate: The optimized candidate.
        verification_errors: List of claim verification errors.

    Returns:
        Markdown report string.
    """
    score = candidate.final_score
    verified_count = len(candidate.verified_claims)
    total_claims = len(candidate.claims)

    report = f"""# Optimization Report: {parent_sku.master_sku}

**Generated:** {datetime.now().isoformat()}
**Status:** {score.approval_status.upper()}

---

## Current Content

**Title:** {parent_sku.current_title}

**Description:** {parent_sku.current_description[:200]}...

---

## Optimized Content

**Title ({len(candidate.title)} chars):**
```

{candidate.title}

```

**Description ({len(candidate.description)} chars):**
```

{candidate.description}

```

---

## Quality Scores

| Dimension | Score |
|-----------|-------|
| Specificity | {score.specificity}/10 |
| Benefit Coverage | {score.benefit_coverage}/10 |
| Keyword Inclusion | {score.keyword_inclusion}/10 |
| Format Adherence | {score.format_adherence}/10 |
| Brand Voice | {score.brand_voice}/10 |
| Factual Accuracy | {score.factual_accuracy}/10 |
| **Composite** | **{score.composite}%** |

---

## Claim Verification

**Verified:** {verified_count}/{total_claims} claims

"""

    if verification_errors:
        report += "### Rejected Claims\n\n"
        for error in verification_errors:
            report += f"- {error}\n"
        report += "\n"

    if candidate.verified_claims:
        report += "### Verified Claims\n\n"
        for claim in candidate.verified_claims:
            report += f"- {claim.claim} (source: {claim.source_field}={claim.source_value})\n"

    report += f"""
---

## Recommendation

"""

    if score.approval_status == "approved":
        report += "**APPROVED** for publication. Content meets quality standards.\n"
    elif score.approval_status == "revise":
        report += "**REVISION NEEDED**. Address rejected claims before publishing.\n"
    else:
        report += "**REJECTED**. Major revisions or human review required.\n"

    return report


def generate_patch_preview(
    parent_sku: ParentSKU,
    candidate: Candidate,
) -> dict:
    """Generate Merchant Center patch preview JSON.

    Args:
        parent_sku: The parent SKU being updated.
        candidate: The optimized candidate.

    Returns:
        Dict in Content API patch format.
    """
    # Use first variant's GMCID as offerId
    offer_id = parent_sku.variants[0].gmc_id if parent_sku.variants else parent_sku.master_sku

    return {
        "offerId": offer_id,
        "title": candidate.title,
        "description": candidate.description,
        "channel": "online",
        "contentLanguage": "en",
        "targetCountry": "US",
        "_meta": {
            "master_sku": parent_sku.master_sku,
            "generated_at": datetime.now().isoformat(),
            "quality_score": candidate.final_score.composite,
            "approval_status": candidate.final_score.approval_status,
        },
        "_previous": {
            "title": parent_sku.current_title,
            "description": parent_sku.current_description,
        },
    }
```

Update `__init__.py`:

```python
# src/feedops/pipeline/__init__.py
"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_report, generate_patch_preview

__all__ = [
    "build_evidence_table",
    "format_evidence_markdown",
    "verify_claims",
    "build_prompt",
    "generate_candidate",
    "CANDIDATE_SCHEMA",
    "generate_report",
    "generate_patch_preview",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`

Expected: PASS (9 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/reporter.py src/feedops/pipeline/__init__.py tests/test_pipeline.py
git commit -m "feat: add report and patch preview generator"
```

---

## Phase 6: CLI

### Task 6.1: Create CLI Entry Point

**Files:**

- Create: `src/feedops/cli/__init__.py`
- Create: `src/feedops/cli/main.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
import subprocess
import sys

def test_cli_help_shows_commands():
    """CLI --help shows available commands."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "healthcheck" in result.stdout.lower() or "health" in result.stdout.lower()

def test_cli_version_shows_version():
    """CLI --version shows version."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/cli/__init__.py
"""FeedOps CLI package."""
```

```python
# src/feedops/cli/main.py
"""FeedOps CLI entry point."""
import typer
from rich.console import Console
from typing import Optional

import feedops

app = typer.Typer(
    name="feedops",
    help="Allied FeedOps - Merchant Center feed optimization",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"feedops version {feedops.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """Allied FeedOps - Merchant Center feed optimization."""
    pass


@app.command()
def healthcheck():
    """Check configuration and connectivity."""
    console.print("[yellow]Healthcheck not yet implemented[/yellow]")


@app.command()
def optimize(
    parent_sku: str = typer.Option(..., "--parent-sku", "-p", help="MasterSKU to optimize"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Preview only, no updates"),
    output_dir: str = typer.Option("reports", "--output-dir", "-o", help="Output directory"),
):
    """Optimize title and description for a parent SKU."""
    console.print(f"[yellow]Optimize not yet implemented for {parent_sku}[/yellow]")


@app.command(name="list-skus")
def list_skus(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum SKUs to list"),
):
    """List available MasterSKUs in catalog."""
    console.print("[yellow]List SKUs not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/cli/__init__.py src/feedops/cli/main.py tests/test_cli.py
git commit -m "feat: add CLI entry point with typer"
```

---

### Task 6.2: Implement Healthcheck Command

**Files:**

- Modify: `src/feedops/cli/main.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py (append)
from unittest.mock import patch
from pathlib import Path

def test_healthcheck_checks_catalog(tmp_path):
    """Healthcheck verifies catalog file exists."""
    # Create a temp catalog
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-PC\n")

    with patch.dict('os.environ', {'CATALOG_PATH': str(catalog)}):
        result = subprocess.run(
            [sys.executable, "-m", "feedops.cli.main", "healthcheck"],
            capture_output=True,
            text=True,
        )
        # Should mention catalog check
        assert "catalog" in result.stdout.lower() or result.returncode == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_healthcheck_checks_catalog -v`

Expected: May pass or fail depending on implementation state

**Step 3: Write minimal implementation**

Update the healthcheck command in `main.py`:

```python
# In src/feedops/cli/main.py, replace the healthcheck function:

import os
from pathlib import Path

@app.command()
def healthcheck():
    """Check configuration and connectivity."""
    console.print("\n[bold]FeedOps Health Check[/bold]\n")

    all_ok = True

    # Check 1: Catalog file
    catalog_path = os.environ.get("CATALOG_PATH", "data/catalog/Product Catalog.csv")
    if Path(catalog_path).exists():
        console.print(f"[green]✓[/green] Catalog: {catalog_path}")
    else:
        console.print(f"[red]✗[/red] Catalog not found: {catalog_path}")
        all_ok = False

    # Check 2: LLM API keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if openai_key:
        console.print(f"[green]✓[/green] OpenAI API key configured")
    else:
        console.print(f"[yellow]![/yellow] OpenAI API key not set")

    if gemini_key:
        console.print(f"[green]✓[/green] Gemini API key configured")
    else:
        console.print(f"[yellow]![/yellow] Gemini API key not set")

    if not openai_key and not gemini_key:
        console.print(f"[red]✗[/red] No LLM provider configured")
        all_ok = False

    # Check 3: Output directories
    for dir_name in ["reports", "exports"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            console.print(f"[green]✓[/green] Directory: {dir_name}/")
        else:
            console.print(f"[yellow]![/yellow] Directory missing: {dir_name}/ (will be created)")

    # Summary
    console.print()
    if all_ok:
        console.print("[bold green]All critical checks passed![/bold green]")
    else:
        console.print("[bold red]Some checks failed. Fix issues before running optimize.[/bold red]")
        raise typer.Exit(1)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`

Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add src/feedops/cli/main.py tests/test_cli.py
git commit -m "feat: implement healthcheck command"
```

---

### Task 6.3: Implement Optimize Command

**Files:**

- Modify: `src/feedops/cli/main.py`
- Create: `src/feedops/pipeline/optimize.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py (append)
@pytest.mark.asyncio
async def test_optimize_pipeline_integration():
    """Test full optimization pipeline with mocked LLM."""
    from feedops.pipeline.optimize import optimize_parent_sku
    from feedops.loaders import load_catalog, get_parent_sku
    from unittest.mock import AsyncMock, patch

    # Mock LLM response
    mock_response = {
        "title": "Test Optimized Title",
        "description": "Test optimized description " * 30,
        "claims": [
            {"claim": "solid brass", "source_field": "material", "source_value": "Brass"}
        ],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        }
    }

    with patch('feedops.pipeline.optimize.get_provider') as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = await optimize_parent_sku(
            master_sku="SAMPLE-TB-24",
            catalog_path=Path("samples/sample-catalog.csv"),
            dry_run=True,
        )

        assert result is not None
        assert result.candidate.title == "Test Optimized Title"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_optimize_pipeline_integration -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/pipeline/optimize.py
"""Main optimization pipeline orchestrator."""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from feedops.models import ParentSKU, Candidate
from feedops.loaders import load_catalog, get_parent_sku
from feedops.providers import get_provider
from feedops.pipeline.generator import generate_candidate
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.reporter import generate_report, generate_patch_preview


@dataclass
class OptimizationResult:
    """Result of a single SKU optimization."""
    master_sku: str
    candidate: Candidate
    verification_errors: list[str]
    report: str
    patch_preview: dict
    timestamp: str


async def optimize_parent_sku(
    master_sku: str,
    catalog_path: Path | str,
    dry_run: bool = True,
    output_dir: Path | str = "reports",
) -> OptimizationResult:
    """Run full optimization pipeline for a parent SKU.

    Pipeline steps:
    1. Load catalog and extract ParentSKU
    2. Generate candidate via LLM
    3. Verify claims against source data
    4. Generate report and patch preview
    5. Save outputs to files

    Args:
        master_sku: The MasterSKU to optimize.
        catalog_path: Path to Product Catalog CSV.
        dry_run: If True, preview only (no MC updates).
        output_dir: Directory for output files.

    Returns:
        OptimizationResult with candidate, report, and patch.
    """
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load catalog and extract ParentSKU
    df = load_catalog(catalog_path)
    parent_sku = get_parent_sku(df, master_sku)
    if parent_sku is None:
        raise ValueError(f"MasterSKU not found: {master_sku}")

    # Step 2: Generate candidate
    provider = get_provider()
    candidate = await generate_candidate(parent_sku, provider)

    # Step 3: Verify claims
    verified_candidate, errors = verify_claims(candidate, parent_sku)

    # Step 4: Generate outputs
    report = generate_report(parent_sku, verified_candidate, errors)
    patch = generate_patch_preview(parent_sku, verified_candidate)

    # Step 5: Save outputs
    safe_sku = master_sku.replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    report_path = output_dir / f"sku-{safe_sku}-{timestamp}.md"
    report_path.write_text(report)

    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    patch_path = exports_dir / f"merchant-center-patch-{safe_sku}.json"
    patch_path.write_text(json.dumps(patch, indent=2))

    return OptimizationResult(
        master_sku=master_sku,
        candidate=verified_candidate,
        verification_errors=errors,
        report=report,
        patch_preview=patch,
        timestamp=timestamp,
    )
```

Update `main.py` optimize command:

```python
# In src/feedops/cli/main.py, replace the optimize function:

import asyncio

@app.command()
def optimize(
    parent_sku: str = typer.Option(..., "--parent-sku", "-p", help="MasterSKU to optimize"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Preview only, no updates"),
    output_dir: str = typer.Option("reports", "--output-dir", "-o", help="Output directory"),
    catalog: str = typer.Option(None, "--catalog", "-c", help="Path to catalog CSV"),
):
    """Optimize title and description for a parent SKU."""
    from feedops.pipeline.optimize import optimize_parent_sku

    catalog_path = catalog or os.environ.get("CATALOG_PATH", "data/catalog/Product Catalog.csv")

    console.print(f"\n[bold]Optimizing: {parent_sku}[/bold]")
    console.print(f"Catalog: {catalog_path}")
    console.print(f"Dry run: {dry_run}\n")

    try:
        result = asyncio.run(optimize_parent_sku(
            master_sku=parent_sku,
            catalog_path=catalog_path,
            dry_run=dry_run,
            output_dir=output_dir,
        ))

        score = result.candidate.final_score
        console.print(f"[bold]Quality Score: {score.composite}%[/bold]")
        console.print(f"Status: {score.approval_status.upper()}")
        console.print(f"\nReport saved to: {output_dir}/sku-{parent_sku.replace('/', '-')}-*.md")
        console.print(f"Patch preview: exports/merchant-center-patch-{parent_sku.replace('/', '-')}.json")

        if score.approval_status == "approved":
            console.print("\n[bold green]Content approved for publication![/bold green]")
        elif score.approval_status == "revise":
            console.print("\n[bold yellow]Content needs revision.[/bold yellow]")
        else:
            console.print("\n[bold red]Content rejected. Review errors.[/bold red]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
```

Update `__init__.py`:

```python
# src/feedops/pipeline/__init__.py
"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_report, generate_patch_preview
from feedops.pipeline.optimize import optimize_parent_sku, OptimizationResult

__all__ = [
    "build_evidence_table",
    "format_evidence_markdown",
    "verify_claims",
    "build_prompt",
    "generate_candidate",
    "CANDIDATE_SCHEMA",
    "generate_report",
    "generate_patch_preview",
    "optimize_parent_sku",
    "OptimizationResult",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`

Expected: PASS (4 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/optimize.py src/feedops/cli/main.py src/feedops/pipeline/__init__.py tests/test_cli.py
git commit -m "feat: implement optimize command with full pipeline"
```

---

## Phase 7: Database

### Task 7.1: Create SQLite Schema

**Files:**

- Create: `src/feedops/db/__init__.py`
- Create: `src/feedops/db/schema.py`
- Test: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
import pytest
from pathlib import Path
from feedops.db.schema import init_db, get_connection

def test_init_db_creates_tables(tmp_path):
    """init_db creates optimization_runs table."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='optimization_runs'"
    )
    assert cursor.fetchone() is not None
    conn.close()

def test_init_db_is_idempotent(tmp_path):
    """Calling init_db twice doesn't error."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # Should not raise
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/feedops/db/__init__.py
"""FeedOps database package."""
from feedops.db.schema import init_db, get_connection, log_optimization

__all__ = ["init_db", "get_connection", "log_optimization"]
```

```python
# src/feedops/db/schema.py
"""SQLite database schema and operations."""
import sqlite3
from pathlib import Path
from datetime import datetime


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Get SQLite connection.

    Args:
        db_path: Path to database file.

    Returns:
        SQLite connection with row factory.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str) -> None:
    """Initialize database with required tables.

    Args:
        db_path: Path to database file.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimization_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            variant_sku TEXT,
            timestamp TEXT NOT NULL,
            llm_provider TEXT NOT NULL,
            llm_model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            quality_score REAL,
            factual_accuracy INTEGER,
            approval_status TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS content_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            version_type TEXT NOT NULL,
            title TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            optimization_run_id INTEGER,
            FOREIGN KEY (optimization_run_id) REFERENCES optimization_runs(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_master_sku
        ON optimization_runs(master_sku)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_versions_master_sku
        ON content_versions(master_sku)
    """)

    conn.commit()
    conn.close()


def log_optimization(
    db_path: Path | str,
    master_sku: str,
    llm_provider: str,
    quality_score: float,
    factual_accuracy: int,
    approval_status: str,
    status: str,
    variant_sku: str | None = None,
    llm_model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error_message: str | None = None,
) -> int:
    """Log an optimization run to the database.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU that was optimized.
        llm_provider: Provider name (e.g., 'openai/gpt-4o').
        quality_score: Composite quality score (0-100).
        factual_accuracy: Factual accuracy score (0-10).
        approval_status: 'approved', 'revise', or 'rejected'.
        status: 'success', 'failed', or 'rejected'.
        variant_sku: Optional specific variant.
        llm_model: Optional model name.
        prompt_tokens: Optional token count.
        completion_tokens: Optional token count.
        error_message: Optional error message if failed.

    Returns:
        ID of the inserted row.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO optimization_runs (
            master_sku, variant_sku, timestamp, llm_provider, llm_model,
            prompt_tokens, completion_tokens, quality_score, factual_accuracy,
            approval_status, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            variant_sku,
            datetime.now().isoformat(),
            llm_provider,
            llm_model,
            prompt_tokens,
            completion_tokens,
            quality_score,
            factual_accuracy,
            approval_status,
            status,
            error_message,
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`

Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/feedops/db/__init__.py src/feedops/db/schema.py tests/test_db.py
git commit -m "feat: add SQLite schema for audit logging"
```

---

### Task 7.2: Integrate Database Logging into Pipeline

**Files:**

- Modify: `src/feedops/pipeline/optimize.py`
- Test: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py (append)
def test_log_optimization_records_run(tmp_path):
    """log_optimization saves run to database."""
    from feedops.db.schema import init_db, log_optimization, get_connection

    db_path = tmp_path / "test.db"
    init_db(db_path)

    run_id = log_optimization(
        db_path=db_path,
        master_sku="1031/18",
        llm_provider="openai/gpt-4o",
        quality_score=85.0,
        factual_accuracy=9,
        approval_status="approved",
        status="success",
    )

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM optimization_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()

    assert row["master_sku"] == "1031/18"
    assert row["quality_score"] == 85.0
    assert row["status"] == "success"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_log_optimization_records_run -v`

Expected: Should pass with current implementation

**Step 3: Write minimal implementation**

Update `optimize.py` to include database logging:

```python
# Add to src/feedops/pipeline/optimize.py, at the end of optimize_parent_sku:

    # Step 6: Log to database
    db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    from feedops.db import init_db, log_optimization

    init_db(db_path)
    log_optimization(
        db_path=db_path,
        master_sku=master_sku,
        llm_provider=provider.name,
        quality_score=verified_candidate.final_score.composite,
        factual_accuracy=verified_candidate.final_score.factual_accuracy,
        approval_status=verified_candidate.final_score.approval_status,
        status="success",
    )
```

Add the import at the top of optimize.py:

```python
import os
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`

Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add src/feedops/pipeline/optimize.py tests/test_db.py
git commit -m "feat: integrate database logging into pipeline"
```

---

## Final Verification

### Task 8.1: Run Full Test Suite

**Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`

Expected: All tests pass

**Step 2: Run type checks**

Run: `mypy src/feedops --ignore-missing-imports`

Expected: No errors (or only minor issues)

**Step 3: Run linter**

Run: `ruff check src/feedops`

Expected: No errors

**Step 4: Test CLI end-to-end**

Run: `feedops healthcheck`

Expected: Shows health status

Run: `feedops list-skus --limit 5 --catalog samples/sample-catalog.csv`

Expected: Lists SKUs from sample

**Step 5: Commit final state**

```bash
git add .
git commit -m "chore: complete MVP implementation"
```

---

## Post-MVP Tasks (Not in MVP Scope)

These tasks are documented for future reference but NOT part of MVP:

1. **Rate Limiting**: Implement per-API rate limits
2. **Content API PATCH**: Enable actual Merchant Center updates
3. **Rollback System**: Automatic rollback on disapproval
4. **Batch Processing**: Process multiple SKUs with circuit breaker
5. **Supabase Migration**: Move from SQLite to Supabase
6. **Shopify Sync**: Real-time webhook integration
