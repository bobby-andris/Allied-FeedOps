# Allied FeedOps

FeedOps is an AI-powered system that automatically improves product titles and descriptions for e-commerce feeds. It takes product data from a CSV catalog and generates optimized content for Google Shopping, Microsoft Shopping, and Shopify.

## What It Does

When you sell products online, the quality of your product titles and descriptions directly affects:

- How often your products appear in search results
- Whether customers click on your listings
- How much you pay for ads (better content = lower cost per click)

FeedOps reads your product catalog, analyzes each product's data, and generates improved titles and descriptions that follow best practices for each platform. Every claim in the generated content is verified against your actual product data to prevent errors.

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Product CSV    │ ──► │  FeedOps        │ ──► │  Optimized      │
│  (your data)    │     │  (AI + rules)   │     │  Content        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │  Quality Report │
                        │  (with scores)  │
                        └─────────────────┘
```

### Data Flow

FeedOps uses a multi-source data architecture:

1. **Primary Source: API + Cache (default)**
   - **DB cache** (`data/feedops.db`) → **Shopify GraphQL** → **Google Merchant Center**
   - Cache-first for speed; API refresh when stale or forced
   - Merchant Center adds feed diagnostics and labels

2. **CSV Fallback** (`data/catalog/Product Catalog.csv`)
   - Used only when APIs are unavailable
   - Still supported for backward compatibility

3. **Database Storage** (SQLite, `data/feedops.db`)
   - **Logging**: Tracks all optimization runs with quality scores and approval status
   - **History**: Stores content versions and keyword intent snapshots
   - **Caching**: Stores Shopify + Merchant Center responses for reuse
   - Database is both cache and audit log (not the customer-facing feed)

### Optimization Pipeline

The system follows a 7-step pipeline:

1. **Catalog Loading**: Extract product data from CSV and build ParentSKU model
2. **Candidate Generation**: AI generates multiple title/description candidates using principles-based prompting (not rigid templates)
3. **Selection**: Best candidate selected using platform-weighted scoring (Google/Bing/Shopify)
4. **Claims Verification**: Every claim verified against source product data
5. **Lifestyle Images** (optional): AI-generated lifestyle images using product reference photos
6. **Report/Patch Generation**: Markdown reports and platform-specific JSON patches created
7. **Database Logging**: Run logged with quality scores, approval status, and metadata

Key features:

- **Principles-based prompting**: Flexible guidelines instead of rigid templates
- **Problem-first content hooks**: Descriptions open with customer problems/needs, not generic benefits
- **Token-overlap keyword validation**: Natural keyword integration validated with ≥50% token match (not exact substring matching)

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/your-org/Allied-FeedOps.git
cd Allied-FeedOps

# Create virtual environment and install
uv venv
uv pip install -e ".[dev]"
```

### 2. Configure

Create a `.env` file with your API keys:

```bash
# Required: At least one LLM provider
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=your-gemini-key-here

# Optional: Shopify and Google Merchant Center
SHOPIFY_STORE_URL=yourstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxx
GMC_MERCHANT_ID=123456789
GMC_API_KEY=your-gmc-key

# Optional: candidate selection tuning
FEEDOPS_NUM_CANDIDATES=3
FEEDOPS_CANDIDATE_WEIGHTS=google=0.7,bing=0.15,shopify=0.15
```

### 3. Add Your Catalog

Place your product catalog CSV at:

```
data/catalog/Product Catalog.csv
```

Or specify a custom path when running commands.

### 4. Run

#### Quick Test: Single SKU

```bash
# Check everything is configured
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main healthcheck

# Preview optimization (dry run - no files saved)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --dry-run --candidates 1

# Generate and save optimization (no-dry-run)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --no-dry-run --candidates 1

# List available SKUs
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main list-skus
```

#### Test Pilot SKUs

The system includes pilot SKUs for testing. Key examples:

- `TD-22` - Towel bar (high quality score: 93.33%)
- `WP-1TB/16` - Waverly Place collection
- `CL-55` - Cabinet hardware
- `HTL-3` - Hardware collection
- `SQ-20`, `FT-16`, `MA-26`, `DT-32` - Additional test products

**Test all pilot SKUs:**

```bash
# Loop through key pilot SKUs
for sku in TD-22 "WP-1TB/16" CL-55 HTL-3; do
  echo "Optimizing $sku..."
  PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
    --parent-sku "$sku" \
    --no-dry-run \
    --candidates 1
done
```

**Batch optimization** (if you have many SKUs):

```bash
# Process multiple SKUs from a list
cat sku_list.txt | while read sku; do
  PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
    --parent-sku "$sku" \
    --no-dry-run \
    --candidates 1
done
```

## Understanding the Output

After running an optimization, outputs are written to the default directory:
**`dashboard_data/lifestyle-eval-candidate/`**

### Reports

**Location:** `dashboard_data/lifestyle-eval-candidate/reports/sku-{SKU}-{timestamp}.md`

Markdown reports include:

- **Original vs optimized content** - Side-by-side comparison
- **Quality scores** - 6-dimension breakdown (0-100%) with composite score
- **Claim verification results** - Every claim traced to source data
- **Approval status** - APPROVED/REVISE/REJECTED with reasoning
- **Keyword placement analysis** - Token-overlap validation results
- **Engagement detection** - Opening hook analysis (31 cues detected)

### JSON Patches

Platform-specific patches are written to:

- `dashboard_data/lifestyle-eval-candidate/google-patch-{SKU}.json`
- `dashboard_data/lifestyle-eval-candidate/bing-patch-{SKU}.json`
- `dashboard_data/lifestyle-eval-candidate/shopify-patch-{SKU}.json`

**Variant-specific patches** (for products with multiple variants):

- `dashboard_data/lifestyle-eval-candidate/variants/{SKU}/{platform}-{SKU}-{VARIANT}.json`

Example (Google):

```json
{
  "offerId": "shopify_US_123_456",
  "title": "24-Inch Wall Mount Towel Bar Solid Brass | Polished Chrome | Allied Brass",
  "short_title": "24-Inch Towel Bar",
  "description": "Your optimized description here...",
  "channel": "online"
}
```

### Reviewing Outputs

**Streamlit Dashboard:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main review-dashboard
```

Or directly:

```bash
streamlit run streamlit_app.py
```

The dashboard provides:

- Three-way comparison (Original / Baseline / Candidate)
- Quality score visualization
- Product images and lifestyle images (if generated)
- Filtering by category, collection, and score changes

## Quality Scoring

Every piece of generated content is scored on 6 dimensions:

| Dimension         | What It Measures                        |
| ----------------- | --------------------------------------- |
| Specificity       | Concrete specs vs vague claims          |
| Benefit Coverage  | Customer benefits in first 150 chars    |
| Keyword Inclusion | Brand + product type + size placement   |
| Format Adherence  | Character limits and structure          |
| Brand Voice       | Premium tone without hype               |
| Factual Accuracy  | All claims verified against source data |

### Enhanced Scoring Features

**Opening Engagement Detection:**

- System detects 31 engagement cues in description openings
- Includes problem-first patterns ("need", "tired of", "looking for", "struggling")
- Includes action verbs ("protect", "organize", "transform", "ensure")
- Validates that first 150 characters contain compelling hooks

**Token-Overlap Keyword Validation:**

- Keywords validated using ≥50% token overlap (not exact substring matching)
- Allows natural keyword integration while ensuring search relevance
- Example: "24-inch towel bar" matches "24 inch wall mount towel bar" via token overlap

**Typical Scores:**

- Approved content typically scores **86-93%** composite
- Pilot SKU TD-22 achieves **93.33%** (exemplary)
- Most approved content falls in **86-88%** range

**Thresholds:**

- 80%+ = Approved for publication
- 70-79% = Needs minor revision
- <70% = Requires major revision

## Project Structure

```
Allied-FeedOps/
├── src/feedops/           # Main application code
│   ├── cli/               # Command-line interface
│   ├── models/            # Data models (Pydantic)
│   ├── pipeline/          # Optimization pipeline
│   │   ├── optimize.py    # Main 7-step pipeline
│   │   ├── prompts.py     # Principles-based prompting
│   │   ├── lifestyle_images.py  # AI image generation
│   │   └── keyword_placement.py # Token-overlap validation
│   ├── providers/         # LLM providers (OpenAI, Gemini)
│   ├── loaders/           # CSV catalog loading
│   ├── integrations/      # API integrations
│   │   ├── shopify_catalog.py    # Shopify GraphQL
│   │   ├── merchant_center.py   # Google Merchant Center
│   │   └── google_ads.py          # Keyword data
│   ├── db/                # Database schema and operations
│   │   └── schema.py      # SQLite tables for logging/history
│   └── quality/           # Quality scoring and dashboard
├── tests/                 # Test suite
├── docs/                  # Documentation
├── samples/               # Sample data for testing
├── dashboard_data/        # Generated outputs
│   └── lifestyle-eval-candidate/  # Default output directory
│       ├── reports/        # Markdown quality reports
│       ├── *.json         # Platform patch files
│       └── variants/      # Variant-specific patches
├── data/                  # Product catalog and database (gitignored)
│   ├── catalog/           # CSV catalog files
│   └── feedops.db         # SQLite database
├── AGENTS.md              # Optimization rules and scoring rubric
├── pyproject.toml         # Python dependencies
└── .env                   # API keys (gitignored, never commit!)
```

## Key Files

| File                    | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `AGENTS.md`             | The core rules for title/description optimization |
| `pyproject.toml`        | Dependencies and package configuration            |
| `.env.example`          | Template for required environment variables       |
| `docs/testing-guide.md` | Detailed guide for testing with real SKUs         |

## Commands

### Core Commands

| Command                     | Description                                       |
| --------------------------- | ------------------------------------------------- |
| `healthcheck`               | Verify configuration and connectivity             |
| `optimize --parent-sku SKU` | Generate optimized content for a product          |
| `list-skus`                 | Show available SKUs in your catalog               |
| `sync-catalog`              | Sync Shopify catalog and Merchant Center metadata |
| `refresh-cache`             | Refresh cached Shopify/GMC data for a SKU         |
| `review-dashboard`          | Launch Streamlit review dashboard                 |

### Command Examples

**Single product optimization (dry run preview):**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "TD-22" \
  --dry-run \
  --candidates 3
```

**Force refresh (bypass cache):**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "TD-22" \
  --force-refresh \
  --dry-run
```

**Skip auto-sync check:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "TD-22" \
  --no-sync \
  --dry-run
```

**Manual cache refresh:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main refresh-cache \
  --sku "TD-22" \
  --source shopify
```

**Single product (generate and save):**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "TD-22" \
  --no-dry-run \
  --candidates 3 \
  --candidate-weights "google=0.7,bing=0.15,shopify=0.15"
```

**Custom catalog path:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "TD-22" \
  --catalog "path/to/custom-catalog.csv" \
  --no-dry-run
```

**Sync catalog from Shopify:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main sync-catalog \
  --source shopify \
  --force
```

**Launch review dashboard:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main review-dashboard \
  --candidate dashboard_data/lifestyle-eval-candidate \
  --baseline dashboard_data/baseline
```

All commands support `--help` for more options.

## Development

### Running Tests

```bash
# Run all tests
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v

# Run specific test file
PYTHONPATH=./src .venv/bin/python -m pytest tests/test_pipeline.py -v

# Run with coverage
PYTHONPATH=./src .venv/bin/python -m pytest tests/ --cov=src/feedops -v
```

All tests should pass.

### Testing with Real SKUs

See `docs/testing-guide.md` for detailed instructions on testing with real product data.

### Adding New Features

1. Write tests first in `tests/`
2. Implement in `src/feedops/`
3. Update documentation if needed
4. Run full test suite before committing

### LLM Providers

FeedOps supports two LLM providers:

- **OpenAI GPT-5.2** (default, recommended)
- **Google Gemini 3 Flash Preview** (fallback)

Configure both in `.env` for automatic failover.

### Lifestyle Images (Optional)

The system can generate AI-powered lifestyle images using Google Gemini Imagen:

```bash
# Enable in .env
LIFESTYLE_IMAGES_ENABLED=true
LIFESTYLE_IMAGES_NUM_VARIATIONS=3
LIFESTYLE_IMAGES_OUTPUT_DIR=data/lifestyle_images
```

Lifestyle images are generated during Step 4 of the pipeline and displayed in the Streamlit dashboard.

## Documentation

- [Testing Guide](docs/testing-guide.md) - How to test with real SKUs
- [Quality Rubric](docs/03-quality-rubric.md) - Detailed scoring methodology
- [Platform Guidelines](docs/04-platform-guidelines.md) - Google/Bing/Shopify specifics

## Security Notes

- Never commit `.env` files or API keys
- The `data/` folder is gitignored (may contain PII)
- Reports may contain product data - review before sharing

## License

Proprietary - Allied Brass
