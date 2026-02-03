# Task: Implement Publishing API Integration

## Objective

Create API routes that enable publishing approved content to Google Merchant Center, Shopify, and Bing from the Next.js dashboard.

## Current State

- Python publishing code exists in `src/feedops/integrations/`
- Dashboard can track batches and approvals
- Environment variables for all platforms are configured in Vercel

## Architecture Decision

Two options:

1. **Recommended**: Create Next.js API routes that replicate the Python logic
2. **Alternative**: Create a separate Python API service and call it from Next.js

This prompt assumes Option 1 (pure Next.js implementation).

## Files to Create

1. `dashboard/src/app/api/publish/google/route.ts` - GMC publishing
2. `dashboard/src/app/api/publish/shopify/route.ts` - Shopify publishing
3. `dashboard/src/app/api/publish/bing/route.ts` - Bing publishing
4. `dashboard/src/lib/publishing/google-sheets.ts` - Google Sheets SDK wrapper
5. `dashboard/src/lib/publishing/shopify.ts` - Shopify GraphQL client
6. `dashboard/src/lib/publishing/types.ts` - Shared types

## Requirements

### 1. Google Merchant Center Publishing (`/api/publish/google`)

GMC uses a Google Sheets supplemental feed. The workflow:

1. Read current feed from Google Sheet
2. Find row matching the SKU's offer IDs
3. Update `structured_title` and `structured_description` columns
4. Optionally update `lifestyle_image_link`

**Environment Variables**:

```
GMC_API_KEY=AIzaSyDMJugTkt_2wYfcJAUvh2tlbWYKZQFNOTc
GMC_MERCHANT_ID=136699027
GOOGLE_SHEETS_SPREADSHEET_ID=1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg
GOOGLE_SERVICE_ACCOUNT_KEY=<base64 encoded>
```

**API Request**:

```typescript
POST /api/publish/google
{
  master_sku: string,
  title: string,
  description: string,
  image_url?: string,
  environment: 'staging' | 'production'
}
```

**Implementation Notes**:

- Use `googleapis` npm package
- Decode `GOOGLE_SERVICE_ACCOUNT_KEY` from base64
- Authenticate with service account
- Use Sheets API v4 to read/update

### 2. Shopify Publishing (`/api/publish/shopify`)

Update product metafields and SEO fields via GraphQL Admin API.

**Environment Variables**:

```
SHOPIFY_STORE_URL=alliedbrass.myshopify.com
SHOPIFY_ACCESS_TOKEN=<your-shopify-access-token>
```

**API Request**:

```typescript
POST /api/publish/shopify
{
  master_sku: string,
  shopify_product_id: string, // From variant_index table
  title: string,
  description: string,
  seo_title?: string,
  seo_description?: string,
  environment: 'staging' | 'production'
}
```

**GraphQL Mutation**:

```graphql
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      descriptionHtml
      seo {
        title
        description
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

### 3. Bing Merchant Center Publishing (`/api/publish/bing`)

Bing uses Content API. Lower priority than Google/Shopify.

**Note**: May require additional credentials not yet in .env.vercel

### 4. Orchestration Route (`/api/publish/batch`)

Coordinate publishing a batch across platforms:

```typescript
POST /api/publish/batch
{
  batch_id: string,
  platforms: ['google', 'shopify', 'bing'],
  environment: 'staging' | 'production'
}
```

Workflow:

1. Get all SKUs in batch from `batch_sku_assignments`
2. Get content for each SKU from `generated_content`
3. Get offer IDs from `variant_index`
4. Call platform-specific publish routes
5. Log results to `publish_events`
6. Update `batch_sku_assignments` status
7. Update batch status

### 5. Error Handling

- Wrap all publish operations in try/catch
- Log failures to `publish_events` with error details
- Continue processing other SKUs if one fails
- Return detailed results showing success/failure per SKU

## Reference Files

- `src/feedops/integrations/google_sheets.py` - Python implementation
- `src/feedops/integrations/shopify.py` - Python Shopify client
- `src/feedops/publish.py` - Publishing orchestration

## Success Criteria

1. Can publish a single SKU to Google Merchant Center
2. Can publish a single SKU to Shopify
3. Batch publishing works for multiple SKUs
4. All publish events are logged to Supabase
5. Errors are handled gracefully
6. Works on Vercel deployment

## Security Notes

- Never expose API keys in client-side code
- All publishing routes should be protected (require auth)
- Consider rate limiting for publish operations
- Staging environment should use test/staging destinations if available
