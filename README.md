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

1. **Input**: Your product catalog CSV with SKUs, titles, descriptions, specifications
2. **Processing**: AI generates optimized content following platform-specific rules
3. **Verification**: Every claim is checked against your source data
4. **Output**: New title/description + quality report + JSON patch for your feed

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

```bash
# Check everything is configured
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main healthcheck

# Optimize a product
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "101" --dry-run \
  --candidates 3 --candidate-weights "google=0.7,bing=0.15,shopify=0.15"

# List available SKUs
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main list-skus
```

## Understanding the Output

After running an optimization, you get a report and platform-specific patches:

### Report (`reports/sku-{SKU}-*.md`)

A markdown report showing:
- Original vs optimized content
- Quality scores (0-100%)
- Claim verification results
- Approval status (APPROVED/REVISE/REJECTED)

### JSON Patches

Platform-specific patches are written to:
- `exports/google-patch-{SKU}.json`
- `exports/bing-patch-{SKU}.json`
- `exports/shopify-patch-{SKU}.json`

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

## Quality Scoring

Every piece of generated content is scored on 6 dimensions:

| Dimension | What It Measures |
|-----------|------------------|
| Specificity | Concrete specs vs vague claims |
| Benefit Coverage | Customer benefits in first 150 chars |
| Keyword Inclusion | Brand + product type + size placement |
| Format Adherence | Character limits and structure |
| Brand Voice | Premium tone without hype |
| Factual Accuracy | All claims verified against source data |

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
│   ├── providers/         # LLM providers (OpenAI, Gemini)
│   └── loaders/           # CSV catalog loading
├── tests/                 # Test suite (48 tests)
├── docs/                  # Documentation
│   └── testing-guide.md   # How to test with real SKUs
├── samples/               # Sample data for testing
├── reports/               # Generated reports (gitignored)
├── exports/               # JSON patches (gitignored)
├── data/                  # Product catalog (gitignored)
├── AGENTS.md              # Optimization rules and scoring rubric
├── pyproject.toml         # Python dependencies
└── .env                   # API keys (gitignored, never commit!)
```

## Key Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | The core rules for title/description optimization |
| `pyproject.toml` | Dependencies and package configuration |
| `.env.example` | Template for required environment variables |
| `docs/testing-guide.md` | Detailed guide for testing with real SKUs |

## Commands

| Command | Description |
|---------|-------------|
| `healthcheck` | Verify configuration and connectivity |
| `optimize --parent-sku SKU` | Generate optimized content for a product |
| `list-skus` | Show available SKUs in your catalog |

All commands support `--help` for more options.

## Development

### Running Tests

```bash
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
```

All tests should pass.

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
