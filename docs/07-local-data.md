# Local Data Setup

This document describes how to set up local data files required for FeedOps operations. **These files are gitignored and must never be committed.**

---

## Directory Structure

```
Allied-FeedOps/
├── data/                          # Gitignored - local data only
│   ├── catalog/
│   │   └── Product Catalog.csv    # Master product catalog export
│   └── exports/                   # Temporary exports (auto-created)
├── samples/                       # Allowed in git - anonymized examples
│   └── sample-catalog.csv         # 5-10 row anonymized sample
├── reports/                       # Gitignored - generated reports
│   └── sku-<MasterSKU>.md
└── exports/                       # Gitignored - Merchant Center patches
    └── merchant-center-patch-<SKU>.json
```

---

## Required Files

### 1. Product Catalog CSV

**Location**: `data/catalog/Product Catalog.csv`

**Source**: Export from Shopify Admin or internal inventory system

**Required columns** (minimum):

| Column | Description | Example |
|--------|-------------|---------|
| `MasterSKU` | Parent SKU identifier | `AB-TOWEL-24` |
| `OptionSKU` | Variant SKU | `AB-TOWEL-24-PC` |
| `Title` | Current product title | `Allied Brass Towel Bar 24` |
| `Description` | Current description | `24 inch towel bar...` |
| `Brand` | Brand name | `Allied Brass` |
| `ProductType` | Category | `Towel Bar` |
| `Material` | Primary material | `Solid Brass` |
| `Finish` | Finish/color | `Polished Chrome` |
| `Dimensions` | Size specifications | `24" x 2.5" x 3"` |
| `Collection` | Collection name (optional) | `Waverly Place` |

**Recommended additional columns**:
- `Handle` (Shopify handle)
- `WeightCapacity` (for grab bars)
- `Certifications` (ADA, UL, etc.)
- `Warranty`
- `MountType`
- `IncludedItems`
- `ShopifyProductID`
- `ShopifyVariantID`

---

## Environment Variables

**Location**: `.env` (project root)

Create a `.env` file with the following variables. **Never commit this file.**

```bash
# --- Required: LLM Provider (at least one) ---
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
# or
GEMINI_API_KEY=...

# --- Shopify (for direct API access) ---
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...

# --- Google Merchant Center ---
GOOGLE_MERCHANT_ID=123456789
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
# or use OAuth credentials
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# --- Google Analytics ---
GA4_PROPERTY_ID=properties/123456789

# --- Google Ads ---
GOOGLE_ADS_CUSTOMER_ID=123-456-7890
GOOGLE_ADS_DEVELOPER_TOKEN=...

# --- Supabase (optional, for persistence) ---
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
```

### Checking Environment

Run the healthcheck to verify configuration:

```bash
# Once CLI is implemented:
feedops healthcheck
```

---

## Running Locally

### Prerequisites

1. Node.js 20+ (for TypeScript implementation)
2. pnpm or npm
3. Access to at least one LLM provider API
4. Product catalog CSV in place

### Setup Steps

```bash
# 1. Clone repository
git clone <repo-url>
cd Allied-FeedOps

# 2. Install dependencies (once implemented)
pnpm install

# 3. Create data directory and place catalog
mkdir -p data/catalog
# Copy your Product Catalog.csv to data/catalog/

# 4. Create .env file with your credentials
cp .env.example .env  # If example exists
# Edit .env with your actual credentials

# 5. Verify setup
pnpm run healthcheck
```

### Single SKU Dry-Run

```bash
# Once CLI is implemented:
feedops optimize --parent-sku AB-TOWEL-24 --dry-run
```

This will:
1. Load product data from catalog CSV
2. Fetch any available performance data via MCPs
3. Generate optimized candidates using LLM
4. Verify all claims against source data
5. Output report to `reports/sku-AB-TOWEL-24.md`
6. Output preview patch to `exports/merchant-center-patch-AB-TOWEL-24.json`

**No data is pushed** in dry-run mode.

---

## Creating Anonymized Samples

If you need sample data for testing or documentation:

```bash
# Create samples directory
mkdir -p samples

# Create a sample with 5-10 rows, anonymizing any real product data:
# - Replace actual SKUs with generic placeholders
# - Use generic product names
# - Keep column structure intact
```

Sample file format (anonymized):

```csv
MasterSKU,OptionSKU,Title,Brand,ProductType,Material,Finish,Dimensions
SAMPLE-001,SAMPLE-001-A,Sample Towel Bar 24,Sample Brand,Towel Bar,Solid Brass,Chrome,"24"" x 2.5"""
SAMPLE-001,SAMPLE-001-B,Sample Towel Bar 24,Sample Brand,Towel Bar,Solid Brass,Bronze,"24"" x 2.5"""
```

---

## Troubleshooting

### "Catalog file not found"
Ensure `data/catalog/Product Catalog.csv` exists and has the correct column headers.

### "Missing required column"
Check that your CSV has all required columns listed above.

### "LLM API error"
Verify your API key in `.env` and check you have sufficient credits.

### "MCP connection failed"
Ensure MCP servers are configured in Cursor settings and credentials are valid.

---

## Security Reminders

1. **Never commit `.env` or any file containing credentials**
2. **Never commit the full product catalog** - use anonymized samples only
3. **Never print full API keys in logs** - only reference by variable name
4. **Reports may contain product data** - keep gitignored
5. **Export patches are previews** - require explicit approval before pushing
