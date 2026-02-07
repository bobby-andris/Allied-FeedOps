# Lifestyle Image Storage Workflow

## Overview

Lifestyle images go through three stages:
1. **Generation** → Supabase Storage (temporary, for review)
2. **Approval** → Supabase Storage (still temporary, awaiting publish)
3. **Publish** → Shopify CDN (permanent, same as product hero images)

## Architecture

### Current (Temporary)
```
AI Generation → Supabase Storage → Review/Approve → Publish to Shopify
                ├─ Public URL: https://qezuszwufortkiutlhym.supabase.co/storage/v1/object/public/lifestyle-images/{filename}
                └─ Used during review workflow
```

### After Publishing (Permanent)
```
Shopify CDN → Product Pages & GMC Feed
├─ URL: https://cdn.shopify.com/s/files/1/.../{filename}
└─ Same CDN as product hero images
```

## Usage

### 1. Upload During Image Generation

```typescript
import { uploadLifestyleImage } from '@/lib/storage/upload-lifestyle-image'

// When generating lifestyle images
const imageBuffer = await generateImage(prompt)
const filename = `${masterSku}_var${index}_${timestamp}.png`
const publicUrl = await uploadLifestyleImage(imageBuffer, filename)

// Store in database
await supabase
  .from('generated_images')
  .insert({
    master_sku: masterSku,
    image_url: publicUrl,  // Supabase Storage URL
    // ...other fields
  })
```

### 2. Publish to Shopify

When user clicks "Publish" and images are approved:

```typescript
import { migrateToShopifyCdn, deleteFromStorage } from '@/lib/storage/upload-lifestyle-image'

// 1. Upload to Shopify via GraphQL
const mutation = `
  mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
    productCreateMedia(productId: $productId, media: $media) {
      media {
        ... on MediaImage {
          id
          image {
            url
          }
        }
      }
    }
  }
`

const shopifyResult = await shopify.graphql(mutation, {
  productId: product.id,
  media: [{
    originalSource: supabaseStorageUrl,
    mediaContentType: 'IMAGE'
  }]
})

// 2. Get Shopify CDN URL from response
const shopifyImageUrl = shopifyResult.data.productCreateMedia.media[0].image.url

// 3. Update database to point to Shopify CDN
await migrateToShopifyCdn(imageId, shopifyImageUrl)

// 4. Clean up Supabase Storage (optional, to save space)
await deleteFromStorage(filename)
```

### 3. Display Images in UI

Images work automatically - just use the `image_url` from the database:

```tsx
// In React components
<img src={image.image_url} alt={image.master_sku} />

// Works for both:
// - Supabase Storage URLs (during review)
// - Shopify CDN URLs (after publish)
```

## Database Schema

```sql
-- generated_images table
CREATE TABLE generated_images (
  id uuid PRIMARY KEY,
  master_sku text NOT NULL,
  image_url text,  -- Starts as Supabase Storage, becomes Shopify CDN
  approval_status text,  -- 'pending' | 'approved' | 'rejected'
  gmc_pushed_at timestamptz,  -- NULL = not published, timestamp = published
  -- ...other fields
);
```

## Migration Commands

### Migrate Existing Images from File Paths

If you have images stored as local file paths in the database:

```bash
# Run migration script
npx tsx scripts/migrate-images-to-storage.ts
```

### Restore Archived Images

If images were archived:

```bash
# Restore from git archive
git show archive/full-snapshot-2026-02-03:dashboard_data/lifestyle-eval-candidate/images/ > /tmp/archived-images

# Then run migration script
npx tsx scripts/migrate-images-to-storage.ts
```

## Storage Bucket Configuration

- **Bucket Name**: `lifestyle-images`
- **Visibility**: Public
- **Size Limit**: 10MB per file
- **Allowed Types**: `image/jpeg`, `image/png`, `image/webp`
- **Location**: Supabase project `qezuszwufortkiutlhym`

## Future: Shopify Publishing Implementation

See `docs/prompts/23-publishing-enhancements.md` for:
- Shopify `productCreateMedia` GraphQL mutation
- Lifestyle image publishing workflow
- GMC feed integration with Shopify URLs

## Questions?

- **Why temporary storage?** Supabase Storage is fast for review workflow, but Shopify CDN is the canonical source for published products.
- **When to clean up?** After successful Shopify publish and URL migration. Keep for 30 days as backup.
- **What about GMC?** GMC feed should always use Shopify CDN URLs (same as product hero images).
