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
| `Product Catalog.csv` | Full product specs, features, materials | ❌ No |
| `generated_content` table | Baseline/current content | ❌ No |
| Shopify API | Product images, metafields | ❌ No |
| Python `ParentSKU` model | Complete product data | ❌ Not accessible |

## Solution: Enrich Product Data for Dashboard Regeneration

### Approach 1: Build Evidence Table in Dashboard (Recommended)

Port the Python pipeline's evidence table logic to TypeScript:

#### Files to Create/Modify

- `dashboard/src/lib/evidence/index.ts` - Evidence table builder
- `dashboard/src/lib/evidence/product-catalog.ts` - Product catalog loader
- `dashboard/src/lib/evidence/keyword-plan.ts` - Keyword placement builder
- `dashboard/src/app/api/regenerate/route.ts` - Update to use evidence

#### Database Schema Enhancement

```sql
-- Add rich product data storage
CREATE TABLE product_catalog (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL UNIQUE,
  current_title text,
  current_description text,
  main_image_url text,
  additional_images text[], -- Array of image URLs
  bullets text[], -- Product bullet points
  features jsonb, -- Structured features
  materials text,
  warranty_info text,
  collection_name text,
  collection_context text,
  design_style text,
  competitive_edge text,
  room_context text, -- 'bathroom' or 'kitchen'
  specifications jsonb, -- Detailed specs
  category text,
  subcategory text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_product_catalog_sku ON product_catalog(master_sku);
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
  finish?: string
): Promise<EvidenceTable> {
  // 1. Fetch from product_catalog table
  // 2. Fetch current content from generated_content
  // 3. Fetch finish metadata if variant
  // 4. Build keyword list from search_queries (Prompt 14)
  // Return comprehensive evidence
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
