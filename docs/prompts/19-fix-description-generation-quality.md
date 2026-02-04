# Task: Fix Description Generation Quality for Google & Bing

## Objective

Fix the poor quality descriptions being generated for Google and Bing Shopping feeds by enriching the product data passed to the LLM prompt. The current dashboard regeneration passes minimal data, resulting in robotic, generic descriptions that don't match the quality of Shopify descriptions from the Python pipeline.

## Problem Statement

**Current descriptions are robotic and missing context:**
```
"Finished in Antique Brass, shower basket, 18.75 in L x 2.25 in H x 4.13 in W, solid brass wall mount oval combination shower caddy..."
```

**Root cause identified:**
The dashboard's `/api/regenerate` route passes only 5 basic fields to the LLM:
- `master_sku`
- `product_title` (often falls back to just the SKU number!)
- `product_category`
- `finish`, `finish_code`
- `dimensions`

**What's MISSING from the dashboard regeneration:**
1. ❌ **Current description/baseline** - LLM doesn't know what exists
2. ❌ **Product images** - Python pipeline passes images, dashboard doesn't
3. ❌ **Full product catalog data** - materials, features, bullets, warranty
4. ❌ **Collection info** - for coordination messaging
5. ❌ **Evidence table** - the rich context the Python pipeline builds
6. ❌ **Keyword placement plan** - SEO-driven keyword strategy
7. ❌ **Design/style context** - modern vs traditional, competitive edge

**Why Shopify descriptions are better:**
The Python pipeline (`src/feedops/pipeline/generator.py`) builds comprehensive context:
- `build_evidence_table()` - rich product data from catalog
- `build_keyword_placement_plan()` - SEO strategy
- `fetch_image()` - passes product image to LLM with vision
- Full `ParentSKU` model with variants, bullets, features

## Critical: Platform-Specific Content Architecture

Refer to Prompt 14 for full context on platform differences:

| Platform | Content Level | Key Consideration |
|----------|---------------|-------------------|
| **Google Shopping** | Variant (per finish) | Each finish has its own title/description |
| **Bing Shopping** | Variant (per finish) | Same as Google - variant level |
| **Shopify** | Master SKU | All finishes share one page |

For Google/Bing regeneration, we need:
1. Variant-specific finish integration
2. The current variant's GMC offer ID
3. Finish-specific keyword patterns (from Prompt 14 search insights)

## Investigation Steps

### Step 1: Use Playwright MCP to Inspect Current Prompts

Navigate to the dashboard and inspect the prompts being used:

```typescript
// In the SKU review page, expand "Prompt used" section
// Inspect both System Prompt and User Prompt
// Document what's actually being passed to the LLM
```

**Expected finding:** The user prompt shows minimal product data like:
```
PRODUCT DATA:
{
  "master_sku": "1051",
  "product_title": "1051",  // Falls back to SKU number!
  "product_category": "Bathroom Hardware",
  "finish": "Polished Chrome",
  "dimensions": "18 inch"
}
```

### Step 2: Compare Python Pipeline Prompts

Examine what the Python pipeline passes:

```python
# src/feedops/pipeline/generator.py - build_split_prompt()
# src/feedops/pipeline/prompts.py - USER_PROMPT_TEMPLATE

# The Python pipeline builds:
# 1. Evidence table with all product attributes
# 2. Keyword placement plan
# 3. Category guidance
# 4. Product image (via fetch_image)
```

### Step 3: Identify Product Data Sources

| Data Source | What's Available | Currently Used? |
|-------------|------------------|-----------------|
| `variant_index` table | Basic SKU mapping, dimensions, finish | ✅ Partially |
| **`data/Acatalog.csv`** | **GOLDMINE: Full product specs, narrative copy, 6 bullets, images, PDFs** | ❌ No |
| `generated_content` table | Baseline/current content | ❌ No |
| **Shopify Admin API** | Product images, metafields, variants, inventory | ❌ No |
| **Google Merchant Center** | Current feed data, offer IDs, approval status | ❌ No |
| Python `ParentSKU` model | Complete product data | ❌ Not accessible |

## Available Data Sources (USE ALL OF THESE)

### 1. PRIMARY: Allied Brass Product Catalog CSV (CRITICAL)

**File:** `data/Acatalog.csv` (75,773 rows of rich product data)

This CSV contains EVERYTHING needed for quality descriptions:

| Column | Description | Use For |
|--------|-------------|---------|
| `MASTER SKU` | Master SKU identifier | Joining data |
| `OPTION SKU` | Variant SKU (with finish code) | Variant identification |
| `GMCID` | Google Merchant Center offer ID | `shopify_US_{product}_{variant}` |
| `Finish Name`, `Code` | Full finish name and code | Finish context |
| `Category` | Product category | Category guidance |
| `Allied Brass Collection` | Collection name | Coordination messaging |
| `Title` | Current product title | Baseline reference |
| `Narraive Copy` | **FULL DESCRIPTION** | Baseline description! |
| `Bullet 1-6` | Six feature bullets | Feature extraction |
| `Length`, `Height`, `Width`, `Projection`, `Weight` | Dimensions | Specs |
| `Main URL` | High-res product image URL | Vision input |
| `Alternative 1-4` | Additional image URLs | Context |
| `Installation` | Installation PDF URL | Trust signal |
| `Specification` | Spec sheet PDF URL | Trust signal |
| `Material`, `Style`, `Shape`, `Mounting type` | Product attributes | Description context |
| `Included` | What's in the box | Feature |

**Action:** Load this CSV into Supabase as `product_catalog` table.

### 2. Shopify Admin API (via MCP)

**IMPORTANT:** Use the `shopify-dev-mcp` server to look up Shopify Admin API documentation for:
- Fetching product data: `products/{id}.json`
- Getting variant details: `variants/{id}.json`
- Retrieving metafields: `products/{id}/metafields.json`
- Fetching product images: `products/{id}/images.json`

```
Use the shopify-dev-mcp tools:
- introspect_graphql_schema - Understand available queries
- learn_shopify_api - Look up REST/GraphQL endpoints
- search_docs_chunks - Search Shopify documentation
- fetch_full_docs - Get complete documentation pages
```

This is useful for:
- Getting current live product data
- Fetching high-resolution images
- Accessing metafields not in CSV
- Verifying data accuracy

### 3. Google Merchant Center Data

The GMC feed contains:
- Current approved titles/descriptions
- Offer approval status
- Feed diagnostics
- Product performance signals

Access via:
- Google Ads MCP for performance data
- GMC API for feed status (if configured)
- `variant_index.gmc_offer_id` for mapping

## Solution: Enrich Product Data for Dashboard Regeneration

### Approach 1: Build Evidence Table in Dashboard (Recommended)

Port the Python pipeline's evidence table logic to TypeScript:

#### Files to Create/Modify

- `dashboard/src/lib/evidence/index.ts` - Evidence table builder
- `dashboard/src/lib/evidence/product-catalog.ts` - Product catalog loader
- `dashboard/src/lib/evidence/keyword-plan.ts` - Keyword placement builder
- `dashboard/src/app/api/regenerate/route.ts` - Update to use evidence

#### Database Schema Enhancement

**Migration file:** `supabase/migrations/010_product_catalog.sql`

```sql
-- Product Catalog Table
-- Loaded from data/Acatalog.csv - contains ALL product data needed for quality descriptions
-- This is the PRIMARY source for regeneration context

CREATE TABLE IF NOT EXISTS product_catalog (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Identification (from CSV)
  master_sku text NOT NULL,
  option_sku text NOT NULL UNIQUE, -- Variant SKU with finish code
  core_sku text,
  upc text,
  gtin text,
  gmc_offer_id text, -- GMCID column: shopify_US_{product}_{variant}
  amazon_asin text,

  -- Finish information
  finish_name text,
  finish_code text,
  finish_position integer, -- Display order

  -- Product classification
  category text,
  collection_name text, -- "Allied Brass Collection" column

  -- Current content (IMPORTANT: baseline for improvement)
  current_title text, -- "Title" column
  narrative_copy text, -- "Narraive Copy" column - FULL DESCRIPTION!

  -- Feature bullets (6 columns in CSV)
  bullet_1 text,
  bullet_2 text,
  bullet_3 text,
  bullet_4 text,
  bullet_5 text,
  bullet_6 text,

  -- Dimensions (product)
  length numeric,
  height numeric,
  width numeric,
  projection numeric,
  weight numeric,

  -- Dimensions (box/shipping)
  box_length numeric,
  box_height numeric,
  box_width numeric,
  box_weight numeric,

  -- Documentation URLs
  installation_pdf_url text,
  specification_pdf_url text,

  -- Image URLs
  main_image_filename text,
  main_image_url text,
  alt_image_1_url text,
  alt_image_2_url text,
  alt_image_3_url text,
  alt_image_4_url text,

  -- Product specifications
  center_to_center text,
  diameter text,
  screw_size text,
  mirror_height text,
  mirror_width text,
  thickness text,
  weight_capacity text,

  -- Product attributes
  material text,
  style text,
  shape text,
  orientation text,
  tilting text,
  mounting_type text,
  assembly_required boolean DEFAULT false,

  -- Pricing (optional - may not want to store)
  list_price numeric,
  wholesale_price numeric,
  map_price numeric,

  -- What's included
  included_items text,
  item_number text,

  -- Shopify IDs (extracted from GMCID)
  shopify_product_id text GENERATED ALWAYS AS (
    CASE
      WHEN gmc_offer_id LIKE 'shopify_US_%'
      THEN split_part(gmc_offer_id, '_', 3)
      ELSE NULL
    END
  ) STORED,
  shopify_variant_id text GENERATED ALWAYS AS (
    CASE
      WHEN gmc_offer_id LIKE 'shopify_US_%'
      THEN split_part(gmc_offer_id, '_', 4)
      ELSE NULL
    END
  ) STORED,

  -- Timestamps
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX idx_product_catalog_master_sku ON product_catalog(master_sku);
CREATE INDEX idx_product_catalog_option_sku ON product_catalog(option_sku);
CREATE INDEX idx_product_catalog_gmc ON product_catalog(gmc_offer_id);
CREATE INDEX idx_product_catalog_category ON product_catalog(category);
CREATE INDEX idx_product_catalog_collection ON product_catalog(collection_name);
CREATE INDEX idx_product_catalog_finish ON product_catalog(finish_code);
CREATE INDEX idx_product_catalog_shopify ON product_catalog(shopify_product_id);

-- RLS
ALTER TABLE product_catalog ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON product_catalog FOR ALL USING (true);

-- Update timestamp trigger
DROP TRIGGER IF EXISTS update_product_catalog_updated_at ON product_catalog;
CREATE TRIGGER update_product_catalog_updated_at
    BEFORE UPDATE ON product_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

#### CSV Import Script

Create a script to load the CSV into Supabase:

```typescript
// scripts/import-product-catalog.ts

import { parse } from 'csv-parse/sync'
import { createClient } from '@supabase/supabase-js'
import * as fs from 'fs'

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

async function importProductCatalog() {
  const csvPath = 'data/Acatalog.csv'
  const csv = fs.readFileSync(csvPath, 'utf-8')
  const records = parse(csv, { columns: true, skip_empty_lines: true })

  console.log(`Importing ${records.length} products...`)

  // Batch insert for performance
  const batchSize = 500
  for (let i = 0; i < records.length; i += batchSize) {
    const batch = records.slice(i, i + batchSize).map((row: any) => ({
      master_sku: row['MASTER SKU'],
      option_sku: row['OPTION SKU'],
      core_sku: row['CoreSKU'],
      upc: row['UPC'],
      gtin: row['GTIN'],
      gmc_offer_id: row['GMCID'],
      amazon_asin: row['Amazon ASIN'],
      finish_name: row['Finish Name'],
      finish_code: row['Code'],
      finish_position: parseInt(row['Position']) || null,
      category: row['Category'],
      collection_name: row['Allied Brass Collection'],
      current_title: row['Title'],
      narrative_copy: row['Narraive Copy'], // Note: typo in CSV column name
      bullet_1: row['Bullet 1'],
      bullet_2: row['Bullet 2'],
      bullet_3: row['Bullet 3'],
      bullet_4: row['Bullet 4'],
      bullet_5: row['Bullet 5'],
      bullet_6: row['Bullet 6'],
      length: parseFloat(row['Length']) || null,
      height: parseFloat(row['Height']) || null,
      width: parseFloat(row['Width']) || null,
      projection: parseFloat(row['Projection']) || null,
      weight: parseFloat(row['Weight']) || null,
      installation_pdf_url: row['Installation'],
      specification_pdf_url: row['Specification'],
      main_image_filename: row['Main'],
      main_image_url: row['Main URL'],
      alt_image_1_url: row['Alternative 1'],
      alt_image_2_url: row['Alternative 2'],
      alt_image_3_url: row['Alternative 3'],
      alt_image_4_url: row['Alternative 4'],
      material: row['Material'],
      style: row['Style'],
      shape: row['Shape'],
      orientation: row['Orientation'],
      tilting: row['Tilting'],
      mounting_type: row['Mounting type'],
      assembly_required: row['Assembly required']?.toLowerCase() === 'true',
      weight_capacity: row['Weight capacity'],
      included_items: row['Included'],
      item_number: row['Item number'],
    }))

    const { error } = await supabase
      .from('product_catalog')
      .upsert(batch, { onConflict: 'option_sku' })

    if (error) {
      console.error(`Error at batch ${i}:`, error)
    } else {
      console.log(`Imported ${Math.min(i + batchSize, records.length)}/${records.length}`)
    }
  }

  console.log('Import complete!')
}

importProductCatalog()
```

#### Evidence Table Builder (TypeScript)

```typescript
// dashboard/src/lib/evidence/index.ts

export interface EvidenceTable {
  // Core identification
  master_sku: string
  product_title: string
  product_category: string

  // Current content (for context)
  current_google_title: string | null
  current_google_description: string | null
  current_bing_title: string | null
  current_bing_description: string | null
  current_shopify_description: string | null

  // Variant-specific (for Google/Bing)
  finish: string | null
  finish_code: string | null
  finish_category: string | null  // 'warm metallic', 'cool metallic', 'matte'
  finish_character: string | null  // 'mirror-like sheen', 'aged patina'

  // Product details
  dimensions: string | null
  materials: string | null
  mount_type: string | null
  weight_capacity: string | null

  // Features and benefits
  bullets: string[]
  features: Record<string, string>
  warranty_info: string | null

  // Collection/design context
  collection_name: string | null
  collection_context: string | null
  design_style: string | null
  competitive_edge: string | null
  room_context: 'bathroom' | 'kitchen'

  // Image URL for vision
  main_image_url: string | null

  // SEO/Keywords
  target_keywords: string[]
  keyword_intent: string | null
}

export async function buildEvidenceTable(
  masterSku: string,
  platform: 'google' | 'bing' | 'shopify',
  finishCode?: string
): Promise<EvidenceTable> {
  const supabase = await createClient()

  // 1. Fetch from product_catalog table (loaded from Acatalog.csv)
  let catalogQuery = supabase
    .from('product_catalog')
    .select('*')
    .eq('master_sku', masterSku)

  // For Google/Bing, get specific variant; for Shopify, get any row (master-level)
  if (platform !== 'shopify' && finishCode) {
    catalogQuery = catalogQuery.eq('finish_code', finishCode)
  }

  const { data: catalogData } = await catalogQuery.limit(1).single()

  // 2. Fetch current generated content (if exists)
  const { data: generatedContent } = await supabase
    .from('generated_content')
    .select('*')
    .eq('master_sku', masterSku)
    .eq('platform', platform)

  const currentTitle = generatedContent?.find(c => c.content_type === 'title')
  const currentDesc = generatedContent?.find(c => c.content_type === 'description')

  // 3. Fetch search query keywords (from Prompt 14, if available)
  const { data: searchQueries } = await supabase
    .from('search_queries')
    .select('query_text, impressions')
    .eq('master_sku', masterSku)
    .order('impressions', { ascending: false })
    .limit(10)

  // 4. Build bullets array from CSV columns
  const bullets = [
    catalogData?.bullet_1,
    catalogData?.bullet_2,
    catalogData?.bullet_3,
    catalogData?.bullet_4,
    catalogData?.bullet_5,
    catalogData?.bullet_6,
  ].filter(Boolean) as string[]

  // 5. Determine room context from category
  const roomContext = catalogData?.category?.toLowerCase().includes('kitchen')
    ? 'kitchen' as const
    : 'bathroom' as const

  // 6. Build dimensions string
  const dimensions = catalogData
    ? `${catalogData.length || ''}L x ${catalogData.height || ''}H x ${catalogData.width || ''}W`
    : null

  // 7. Get finish metadata
  const finishMeta = getFinishMetadata(catalogData?.finish_name || '')

  return {
    master_sku: masterSku,
    product_title: catalogData?.current_title || masterSku,
    product_category: catalogData?.category || 'Bathroom Hardware',

    // Current content - IMPORTANT for context
    current_google_title: currentTitle?.candidate_content || null,
    current_google_description: currentDesc?.candidate_content || null,
    current_bing_title: null, // TODO: fetch if separate
    current_bing_description: null,
    current_shopify_description: catalogData?.narrative_copy || null, // From CSV!

    // Variant info
    finish: catalogData?.finish_name || null,
    finish_code: catalogData?.finish_code || null,
    finish_category: finishMeta.category,
    finish_character: finishMeta.character,

    // Product details from CSV
    dimensions,
    materials: catalogData?.material || 'Solid Brass',
    mount_type: catalogData?.mounting_type || null,
    weight_capacity: catalogData?.weight_capacity || null,

    // Features from CSV bullets
    bullets,
    features: {
      style: catalogData?.style || '',
      shape: catalogData?.shape || '',
      assembly: catalogData?.assembly_required ? 'Required' : 'Not required',
      included: catalogData?.included_items || '',
    },
    warranty_info: 'Limited Lifetime Warranty', // Standard for Allied Brass

    // Collection/design context
    collection_name: catalogData?.collection_name || null,
    collection_context: catalogData?.collection_name
      ? `Part of the ${catalogData.collection_name} collection for coordinated design`
      : null,
    design_style: catalogData?.style || 'versatile',
    competitive_edge: 'Solid brass construction outlasts die-cast zinc alternatives',
    room_context: roomContext,

    // Image URL for vision - HIGH RES from CSV!
    main_image_url: catalogData?.main_image_url || null,

    // Keywords from search queries (Prompt 14)
    target_keywords: searchQueries?.map(q => q.query_text) || [],
    keyword_intent: null,
  }
}

export function formatEvidenceMarkdown(evidence: EvidenceTable): string {
  // Format evidence table as markdown for LLM consumption
  return `
=== EVIDENCE TABLE ===
Master SKU: ${evidence.master_sku}
Product: ${evidence.product_title}
Category: ${evidence.product_category}

CURRENT CONTENT (for context - improve on this):
- Google Title: ${evidence.current_google_title || 'N/A'}
- Google Description: ${evidence.current_google_description || 'N/A'}

PRODUCT SPECIFICATIONS:
- Dimensions: ${evidence.dimensions || 'N/A'}
- Materials: ${evidence.materials || 'N/A'}
- Mount Type: ${evidence.mount_type || 'N/A'}
${evidence.weight_capacity ? `- Weight Capacity: ${evidence.weight_capacity}` : ''}

FEATURES:
${evidence.bullets.map(b => `- ${b}`).join('\n')}

${evidence.collection_name ? `COLLECTION: ${evidence.collection_name}
${evidence.collection_context || ''}` : ''}

${evidence.warranty_info ? `WARRANTY: ${evidence.warranty_info}` : ''}

DESIGN CONTEXT:
- Style: ${evidence.design_style || 'versatile'}
- Competitive Edge: ${evidence.competitive_edge || 'Solid brass construction'}
- Room: ${evidence.room_context}

TARGET KEYWORDS (from actual search queries):
${evidence.target_keywords.slice(0, 5).join(', ')}
`
}
```

### Approach 2: Call Python Pipeline API (Alternative)

If Cloud Run is deployed (Prompt 09), call the Python pipeline's regeneration endpoint which already has the evidence table logic.

```typescript
// dashboard/src/app/api/regenerate/route.ts

// Option: Call Cloud Run instead of OpenAI directly
const response = await fetch(`${CLOUD_RUN_URL}/regenerate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    master_sku,
    platform,
    finish,
    feedback: feedback?.user_feedback,
  }),
})
```

## Updated Regenerate API

```typescript
// dashboard/src/app/api/regenerate/route.ts (updated)

import { buildEvidenceTable, formatEvidenceMarkdown } from '@/lib/evidence'
import { buildKeywordPlacementPlan } from '@/lib/evidence/keyword-plan'
import { getFinishMetadata } from '@/lib/evidence/finish-metadata'

// ... existing code ...

export async function POST(request: NextRequest) {
  // ... validation ...

  // Build comprehensive evidence table (NEW)
  const evidence = await buildEvidenceTable(master_sku, platform, feedback?.finish)
  const evidenceMarkdown = formatEvidenceMarkdown(evidence)
  const keywordPlan = await buildKeywordPlacementPlan(master_sku, evidence)

  // Fetch product image for vision (NEW)
  let productImage: string | null = null
  if (evidence.main_image_url) {
    productImage = await fetchImageAsBase64(evidence.main_image_url)
  }

  // Build enhanced user prompt (UPDATED)
  let userPrompt: string
  if (mode === 'simple') {
    userPrompt = buildEnhancedPrompt(content_type, platform, evidence, keywordPlan)
  } else {
    userPrompt = buildEnhancedFeedbackPrompt(
      content_type,
      platform,
      evidence,
      keywordPlan,
      feedback!.current_content,
      feedback!.user_feedback
    )
  }

  // Call OpenAI with image (UPDATED)
  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
  ]

  if (productImage) {
    messages.push({
      role: 'user',
      content: [
        { type: 'text', text: userPrompt },
        { type: 'image_url', image_url: { url: productImage } },
      ],
    })
  } else {
    messages.push({ role: 'user', content: userPrompt })
  }

  const completion = await getOpenAIClient().chat.completions.create({
    model: MODEL,
    messages,
    temperature: 0.7,
    ...tokenParams,
  })

  // ... rest of handler ...
}
```

## Finish Metadata for Variant Generation

```typescript
// dashboard/src/lib/evidence/finish-metadata.ts

export const FINISH_METADATA: Record<string, {
  category: 'warm_metallic' | 'cool_metallic' | 'matte' | 'specialty'
  character: string
  style_affinities: string[]
}> = {
  'Polished Chrome': {
    category: 'cool_metallic',
    character: 'mirror-like sheen that reflects light brilliantly',
    style_affinities: ['modern', 'contemporary', 'minimalist'],
  },
  'Antique Brass': {
    category: 'warm_metallic',
    character: 'softened, aged golden patina with vintage charm',
    style_affinities: ['traditional', 'vintage', 'transitional'],
  },
  'Matte Black': {
    category: 'matte',
    character: 'bold, non-reflective finish with modern edge',
    style_affinities: ['modern', 'industrial', 'contemporary'],
  },
  'Satin Nickel': {
    category: 'cool_metallic',
    character: 'soft, brushed finish that hides fingerprints',
    style_affinities: ['transitional', 'modern', 'versatile'],
  },
  // ... all 28 finishes
}

export function getFinishMetadata(finishName: string) {
  return FINISH_METADATA[finishName] || {
    category: 'metallic',
    character: 'quality finish',
    style_affinities: ['versatile'],
  }
}
```

## Variant-Aware Prompt Building

```typescript
// dashboard/src/lib/evidence/prompt-builder.ts

export function buildEnhancedPrompt(
  contentType: 'title' | 'description',
  platform: 'google' | 'bing' | 'shopify',
  evidence: EvidenceTable,
  keywordPlan: KeywordPlan
): string {
  const platformContext = getPlatformContext(platform, contentType)

  // For Google/Bing, add variant-specific context
  const variantContext = platform !== 'shopify' && evidence.finish
    ? buildVariantContext(evidence.finish, evidence.finish_category, evidence.finish_character)
    : ''

  return `Generate a ${contentType} for this product.

${platformContext}

=== EVIDENCE TABLE ===
${formatEvidenceMarkdown(evidence)}

=== KEYWORD PLACEMENT PLAN ===
${formatKeywordPlan(keywordPlan)}

${variantContext}

Remember:
- Write for a human who's about to spend $80 and wants to feel good about it
- Every factual claim must be traceable to the evidence table
- Weave keywords naturally, don't list them
${platform !== 'shopify' ? `- This is a VARIANT listing for ${evidence.finish} - integrate the finish naturally` : ''}

Respond with ONLY the ${contentType} text, no additional explanation.`
}

function buildVariantContext(finish: string, category: string | null, character: string | null): string {
  return `
=== VARIANT CONTEXT ===
This content is for the ${finish} variant specifically.

FINISH DETAILS:
- Name: ${finish}
- Category: ${category || 'metallic'}
- Character: ${character || 'quality finish'}

INTEGRATION REQUIREMENTS:
- Weave "${finish}" naturally into the FIRST SENTENCE
- Do NOT use "Available in ${finish}. ${finish} features..." pattern
- The finish should feel like a selling point, not an awkward addition

GOOD: "This 18-inch towel bar in ${finish} coordinates with modern bathroom fixtures."
BAD: "Available in ${finish}. ${finish} delivers..."
`
}
```

## Data Population Strategy

### Option A: Sync from Product Catalog CSV

```typescript
// dashboard/src/lib/evidence/catalog-sync.ts

import { parse } from 'csv-parse/sync'
import { createAdminClient } from '@/lib/supabase/admin'

export async function syncProductCatalog(csvPath: string) {
  const csv = await fs.readFile(csvPath, 'utf-8')
  const records = parse(csv, { columns: true })

  const supabase = createAdminClient()

  for (const row of records) {
    await supabase.from('product_catalog').upsert({
      master_sku: row['Master SKU'],
      current_title: row['Title'],
      current_description: row['Description'],
      main_image_url: row['Image URL'],
      bullets: parseBullets(row['Bullets']),
      materials: row['Material'],
      warranty_info: row['Warranty'],
      collection_name: row['Collection'],
      category: row['Category'],
      // ... map all fields
    })
  }
}
```

### Option B: Fetch from Shopify API

```typescript
// dashboard/src/lib/evidence/shopify-sync.ts

export async function fetchProductFromShopify(shopifyProductId: string) {
  const response = await shopifyClient.query({
    data: `{
      product(id: "gid://shopify/Product/${shopifyProductId}") {
        title
        descriptionHtml
        images(first: 5) { edges { node { url } } }
        metafields(first: 20) { edges { node { key value } } }
        collections(first: 3) { edges { node { title } } }
      }
    }`
  })

  return transformToProductCatalog(response)
}
```

## Success Criteria

1. [ ] Product catalog table populated with rich product data
2. [ ] Evidence table builder implemented in TypeScript
3. [ ] Regenerate API passes comprehensive context to LLM
4. [ ] Product images passed to LLM (vision enabled)
5. [ ] Current content passed as context for improvement
6. [ ] Variant-specific finish context for Google/Bing
7. [ ] Keyword placement plan from actual search queries
8. [ ] Generated descriptions match Python pipeline quality
9. [ ] "Prompt used" section shows rich evidence table

## Testing Checklist

Use Playwright MCP to verify:

1. [ ] Navigate to `/review/1051` (Paper Towel Holders)
2. [ ] Click "Regenerate" on Google description
3. [ ] Expand "Prompt used" section
4. [ ] Verify evidence table includes:
   - Current title (not just SKU number)
   - Current description
   - Product specs (dimensions, materials)
   - Features/bullets
   - Collection context
   - Target keywords
5. [ ] Compare generated description to Shopify quality
6. [ ] Test with different finishes (Polished Chrome, Antique Brass, Matte Black)

## Migration Path

1. **Phase 1**: Populate `product_catalog` table from CSV
2. **Phase 2**: Implement evidence table builder
3. **Phase 3**: Update regenerate API to use evidence
4. **Phase 4**: Add image vision support
5. **Phase 5**: Integrate search query keywords (from Prompt 14)

## Related Prompts

- **Prompt 14**: Search Query Insights - provides target keywords
- **Prompt 17**: Description Quality Analyzer - validates output quality
- **Prompt 09**: GCP Cloud Run - alternative: call Python pipeline directly
