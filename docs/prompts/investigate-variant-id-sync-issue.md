# Investigation Prompt: Variant ID Sync Issue Across Data Pipeline

## Problem Summary

**Critical data sync issue discovered**: Only 3 out of 100 Google Ads products match our `variant_index` database (0.3% match rate).

- **97 products in Google Ads don't exist in our database**
- **997 products in our database don't exist in Google Ads**
- This prevents baseline performance capture for ~99% of SKUs

## System Architecture (Source of Truth Chain)

```
Shopify (products/variants)
    ↓
[Custom Feed Process] ← WE WRITE THIS
    ↓
Google Merchant Center (GMC)
    ↓
Google Ads (uses GMC products)
    ↓
variant_index table (should match GMC)
```

**Key Facts**:
- GMC does NOT auto-sync from Shopify - we have a custom feed process
- The variant_index table should reflect what's in the GMC feed
- Google Ads can only see products that are in GMC
- Our baseline capture queries variant_index to get offer IDs, then queries Google Ads

## Evidence of Mismatch

### Example: DMF-2/2X

**Product ID**: 4539975336068 (matches across all systems)

**Variant IDs in variant_index** (25 variants):
- shopify_us_4539975336068_32103132364932 (ABR finish)
- shopify_us_4539975336068_32103132397700 (ABZ finish)
- shopify_us_4539975336068_32103132430468 (BBR finish)
- ... (22 more)

**Variant ID in Google Ads** (with 768 impressions):
- shopify_us_4539975336068_**32103134298244** ← **This variant doesn't exist in our database!**

### Full Statistics

Tested first 1000 offer IDs from variant_index:
- ✅ 3 matches with Google Ads (0.3%)
- ❌ 97 Google Ads products not in database
- ⚠️ 997 database products not in Google Ads

## Investigation Tasks

Use agent-based thinking to investigate each component in parallel:

### Task 1: Investigate Shopify Data

**Goal**: Verify what variant IDs currently exist in Shopify for sample products

**Approach**:
1. Use Shopify Admin API / GraphQL to query product 4539975336068 (DMF-2/2X)
2. Get all current variant IDs for this product
3. Compare to variant_index table
4. Check 5-10 other sample products
5. Determine: Are our database variant IDs old/stale or are they current?

**Key Question**: Did products get recreated in Shopify with new variant IDs?

**Tools**: Shopify API, possibly via MCP or direct GraphQL

### Task 2: Investigate Google Merchant Center Feed

**Goal**: Understand what offer IDs are currently in the GMC feed

**Approach**:
1. Use Merchant API MCP to query `product_view` table
2. Get offer_id values for products (especially DMF-2/2X)
3. Check if GMC has variant ID 32103134298244 (the one Google Ads uses)
4. Query for a sample of products to see format/patterns
5. Determine: Is GMC the source of the mismatch or is it correct?

**Key Question**: Does GMC have the same variant IDs that Google Ads is using?

**Tools**:
- `mcp__merchant-api-devdocs__query_mapi_docs` - For API documentation
- Merchant API queries via product_view

**Example Query**:
```sql
SELECT offer_id, title
FROM product_view
WHERE offer_id LIKE 'shopify_us_4539975336068_%'
LIMIT 10
```

### Task 3: Find the Custom Feed Process

**Goal**: Locate and understand our custom GMC feed generation process

**Approach**:
1. Search codebase for GMC feed generation:
   - Look for "merchant center", "product feed", "gmc", "google shopping feed"
   - Check for Google Sheets integration (common for GMC feeds)
   - Look for CSV/XML feed generation
   - Check for FTP upload or API calls to GMC

2. Find where variant_index gets populated:
   - Search for INSERT/UPDATE queries to variant_index
   - Check for Shopify API calls that fetch variant data
   - Look for data import/sync scripts

3. Understand the flow:
   - Does variant_index generate the feed? Or does the feed populate variant_index?
   - When was variant_index last updated?
   - Is there a sync process that's supposed to run regularly?

**Key Questions**:
- Where is the code that writes to GMC?
- Where does variant_index data come from?
- Are they supposed to be in sync?

**Tools**: Glob, Grep, Read (search codebase)

**Search patterns**:
```bash
# Search for GMC/feed-related code
grep -r "merchant.center\|google.shopping\|product.feed" src/
grep -r "variant_index" src/ --include="*.py" --include="*.ts"
grep -r "gmc_offer_id" src/

# Look for Google Sheets publishing (common for GMC feeds)
grep -r "google.sheets\|spreadsheet" src/ | grep -i "publish\|feed"
```

### Task 4: Analyze the 97 Orphan Products

**Goal**: Understand the products in Google Ads that don't exist in our database

**Approach**:
1. Run the diagnostic script to get all Google Ads products:
   ```bash
   source .venv/bin/activate
   PYTHONPATH=./src python3 scripts/test_google_ads_raw.py
   ```

2. Extract the 97 orphan offer IDs

3. Analyze patterns:
   - What are the product IDs (middle number)?
   - Do these product IDs exist in variant_index with different variant IDs?
   - Are they new products? Specific collections?
   - When did they appear in Google Ads?

4. Cross-reference with Shopify:
   - Do these products exist in Shopify currently?
   - Were they recently created?

**Key Question**: Are these genuinely new products, or are they existing products with new variant IDs?

### Task 5: Audit variant_index Table

**Goal**: Understand the data quality and history of variant_index

**Approach**:
1. Check schema for metadata:
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'variant_index'
   ORDER BY ordinal_position;
   ```

2. Get data statistics:
   ```sql
   SELECT
       COUNT(*) as total_rows,
       COUNT(DISTINCT master_sku) as unique_skus,
       COUNT(DISTINCT gmc_offer_id) as unique_offers,
       MIN(created_at) as oldest_record,
       MAX(created_at) as newest_record
   FROM variant_index
   WHERE gmc_offer_id IS NOT NULL;
   ```

3. Check for duplicates or data issues

4. Look for any sync/update logs

**Key Questions**:
- When was this data last updated?
- Is there a created_at/updated_at timestamp?
- Is the data stale?

**Tools**: Supabase MCP (`mcp__supabase__execute_sql`)

### Task 6: Design the Fix

**Goal**: After gathering all evidence, design the proper sync architecture

**Wait for tasks 1-5 to complete, then:**

1. Map out the actual current flow (based on findings)
2. Identify where the sync broke
3. Design the correct flow for future
4. Create migration plan to fix current mismatch
5. Propose monitoring/alerts to prevent future drift

**Deliverables**:
- Architecture diagram of current vs desired state
- Root cause analysis
- Step-by-step migration plan
- Code changes needed
- Verification tests

## Success Criteria

✅ Understand the complete data flow from Shopify → GMC → Google Ads → Database
✅ Identify where the variant ID mismatch originates
✅ Locate the custom feed generation code
✅ Determine if variant_index should drive the feed or vice versa
✅ Design a fix that brings match rate from 0.3% to >95%
✅ Propose sync process to keep systems aligned going forward

## Files to Investigate

**Python Backend**:
- `src/feedops/integrations/` - May contain GMC feed generation
- `src/feedops/api/` - API endpoints
- `src/feedops/db/` - Database operations

**Dashboard**:
- `dashboard/src/lib/publishing/` - Publishing logic (Google Sheets integration found here)
- `dashboard/src/app/api/publish/` - Publishing API routes

**Database**:
- `variant_index` table - The problematic table
- `generated_content` table - References master_sku
- Any migration scripts or seed data

**Scripts**:
- Look for any sync scripts in `scripts/` or `src/feedops/scripts/`

## Context from Previous Investigation

1. **Case mismatch fixed**: Changed all offer IDs from `shopify_US_` to `shopify_us_` (lowercase) - 72,023 rows updated
2. **Campaign type fix**: Added `campaign.advertising_channel_type` to queries to include Performance Max
3. **Diagnostic tools created**:
   - `scripts/test_google_ads_raw.py` - Query Google Ads directly
   - `/performance/diagnose-query` - API endpoint to test queries
   - `/performance/diagnose-products` - API endpoint to see what's in Google Ads

4. **Known working products** (3 that match):
   - shopify_us_4531833766020_32063606718596
   - shopify_us_4531786186884_32063469453444
   - shopify_us_4531838877828_32063630049412

## Approach

**Use multi-agent investigation**:
1. Spawn 4-5 agents in parallel for tasks 1-5
2. Each agent investigates their component independently
3. Synthesize findings
4. Design holistic fix

**Agent coordination**:
- Use TaskCreate to create investigation tasks
- Use Task tool with `subagent_type: "Explore"` for codebase searches
- Use Task tool with `subagent_type: "general-purpose"` for API investigations
- Agents report findings, lead synthesizes

## Starting Point

Create a team and spawn agents to investigate each component in parallel. The key is understanding:
1. Where do variant IDs come from?
2. Where do they go?
3. Where did the sync break?
