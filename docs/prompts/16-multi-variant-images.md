# Task: Implement Multi-Variant Lifestyle Image Generation

## Objective

Generate lifestyle images for ALL finish variants of each product, not just the primary variant. Push images to Shopify variant media and update the GMC supplemental feed with variant-specific lifestyle_image_link.

## Problem Statement

Currently we only generate lifestyle images for the primary variant. This creates cognitive dissonance:
- Customer searches for "Antique Brass towel bar"
- They see a Polished Chrome lifestyle image
- Image doesn't match their search intent
- Lower click-through and conversion rates

Allied Brass has 28 finish options. Each finish variant should show a lifestyle image in that finish.

## Solution Overview

Generate finish-specific lifestyle images that:
1. Identify all finish variants for each master SKU
2. Generate lifestyle images showing each finish in context
3. Apply consistent IPTC metadata across all variants
4. Push images to Shopify variant media via GraphQL
5. Update GMC supplemental feed with variant-specific lifestyle_image_link

## Prerequisites

- Gemini Imagen API access (existing: `src/feedops/pipeline/lifestyle_images.py`)
- Shopify Admin API access with media permissions
- GCS bucket for image storage
- Variant index mapping (finish codes to GMC IDs)

## Files to Create/Modify

### Dashboard Components
- `dashboard/src/app/(dashboard)/images/page.tsx` - Image management page
- `dashboard/src/app/api/images/route.ts` - Image listing API
- `dashboard/src/app/api/images/generate-variants/route.ts` - Trigger variant generation
- `dashboard/src/components/images/VariantImageGrid.tsx` - Display variant images
- `dashboard/src/components/images/GenerationProgress.tsx` - Track generation progress

### Python Pipeline
- `src/feedops/pipeline/variant_lifestyle_images.py` - Multi-variant generation
- `src/feedops/integrations/shopify_media_upload.py` - Shopify media upload

### Database
- `supabase/migrations/012_variant_images.sql`

## Database Schema

```sql
-- Track generated images per variant
CREATE TABLE variant_images (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  finish text NOT NULL,
  finish_code text,
  gmc_offer_id text,
  shopify_variant_id text,
  image_type text DEFAULT 'lifestyle', -- 'lifestyle', 'product', 'detail'
  prompt text,
  gcs_url text, -- gs://bucket/path/to/image.jpg
  cdn_url text, -- Public URL for GMC feed
  shopify_media_id text, -- Shopify media ID after upload
  quality_score numeric,
  status text DEFAULT 'pending', -- 'pending', 'generating', 'ready', 'failed', 'published'
  error_message text,
  created_at timestamptz DEFAULT now(),
  published_at timestamptz,
  UNIQUE(master_sku, finish, image_type)
);

-- Generation job tracking
CREATE TABLE image_generation_jobs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  total_variants integer NOT NULL,
  completed_variants integer DEFAULT 0,
  failed_variants integer DEFAULT 0,
  status text DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed'
  error_message text,
  created_at timestamptz DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz
);

-- Indexes
CREATE INDEX idx_variant_images_sku ON variant_images(master_sku);
CREATE INDEX idx_variant_images_status ON variant_images(status);
CREATE INDEX idx_image_generation_jobs_status ON image_generation_jobs(status);
```

## Python Implementation

### variant_lifestyle_images.py

```python
# src/feedops/pipeline/variant_lifestyle_images.py

import os
import json
from typing import List, Dict, Optional
from google.cloud import storage
from vertexai.preview.vision_models import ImageGenerationModel
from feedops.db import get_supabase_client
from feedops.pipeline.lifestyle_images import (
    generate_lifestyle_image,
    add_iptc_metadata,
    score_image
)

# Allied Brass finish mapping
FINISH_DESCRIPTIONS = {
    'PC': 'Polished Chrome',
    'SN': 'Satin Nickel',
    'AB': 'Antique Brass',
    'PB': 'Polished Brass',
    'BBR': 'Brushed Bronze',
    'ORB': 'Oil Rubbed Bronze',
    'VB': 'Venetian Bronze',
    'CA': 'Antique Copper',
    'PNI': 'Polished Nickel',
    'SBR': 'Satin Bronze',
    'MB': 'Matte Black',
    'MW': 'Matte White',
    'PW': 'Polished White',
    'UNL': 'Unlacquered Brass',
    'SCH': 'Satin Chrome',
    # ... add all 28 finishes
}

FINISH_COLOR_PROMPTS = {
    'PC': 'shiny silver polished chrome metal finish',
    'SN': 'brushed matte silver satin nickel finish',
    'AB': 'warm golden-brown antique brass with patina',
    'PB': 'bright gold polished brass finish',
    'BBR': 'dark brown brushed bronze finish',
    'ORB': 'deep brown oil-rubbed bronze with highlights',
    'VB': 'rich brown venetian bronze finish',
    'CA': 'warm copper with antique patina',
    'PNI': 'shiny silver polished nickel finish',
    'SBR': 'muted brown satin bronze finish',
    'MB': 'matte black powder-coated finish',
    'MW': 'matte white powder-coated finish',
    'PW': 'glossy white polished finish',
    'UNL': 'natural brass that will patina over time',
    'SCH': 'brushed silver satin chrome finish',
}


class VariantImageGenerator:
    """Generate lifestyle images for all finish variants."""

    def __init__(self):
        self.supabase = get_supabase_client()
        self.storage_client = storage.Client()
        self.bucket_name = os.getenv('GCS_BUCKET_NAME', 'feedops-images')
        self.model = ImageGenerationModel.from_pretrained('gemini-3-pro-image-preview')

    def get_variants_for_sku(self, master_sku: str) -> List[Dict]:
        """Get all finish variants for a master SKU."""
        result = self.supabase.table('variant_index') \
            .select('*') \
            .eq('master_sku', master_sku) \
            .execute()

        return result.data if result.data else []

    def generate_variant_images(
        self,
        master_sku: str,
        product_data: Dict,
        job_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate lifestyle images for all variants of a SKU.

        Args:
            master_sku: The master SKU
            product_data: Product information (category, dimensions, etc.)
            job_id: Optional job ID for tracking

        Returns:
            List of generated image records
        """
        variants = self.get_variants_for_sku(master_sku)
        results = []

        # Update job status
        if job_id:
            self.supabase.table('image_generation_jobs').update({
                'status': 'processing',
                'started_at': 'now()',
                'total_variants': len(variants)
            }).eq('id', job_id).execute()

        for i, variant in enumerate(variants):
            finish_code = variant.get('finish_code', 'PC')
            finish_name = FINISH_DESCRIPTIONS.get(finish_code, finish_code)

            try:
                # Build finish-specific prompt
                prompt = self._build_prompt(product_data, finish_code, finish_name)

                # Generate image
                image_response = self.model.generate_images(
                    prompt=prompt,
                    number_of_images=1,
                    aspect_ratio='1:1',
                    safety_filter_level='block_few'
                )

                if not image_response.images:
                    raise Exception('No image generated')

                image = image_response.images[0]

                # Add IPTC metadata
                image_bytes = add_iptc_metadata(
                    image._image_bytes,
                    title=f"{product_data['name']} - {finish_name}",
                    description=f"Lifestyle image of {product_data['name']} in {finish_name} finish",
                    keywords=[
                        product_data.get('category', ''),
                        finish_name,
                        'Allied Brass',
                        'bathroom fixture'
                    ]
                )

                # Upload to GCS
                gcs_path = f"lifestyle/{master_sku}/{finish_code}.jpg"
                gcs_url = self._upload_to_gcs(image_bytes, gcs_path)
                cdn_url = f"https://storage.googleapis.com/{self.bucket_name}/{gcs_path}"

                # Score image
                quality_score = score_image(image_bytes)

                # Save to database
                record = {
                    'master_sku': master_sku,
                    'finish': finish_name,
                    'finish_code': finish_code,
                    'gmc_offer_id': variant.get('gmc_offer_id'),
                    'shopify_variant_id': variant.get('shopify_variant_id'),
                    'image_type': 'lifestyle',
                    'prompt': prompt,
                    'gcs_url': gcs_url,
                    'cdn_url': cdn_url,
                    'quality_score': quality_score,
                    'status': 'ready'
                }

                self.supabase.table('variant_images').upsert(
                    record,
                    on_conflict='master_sku,finish,image_type'
                ).execute()

                results.append(record)

                # Update job progress
                if job_id:
                    self.supabase.table('image_generation_jobs').update({
                        'completed_variants': i + 1
                    }).eq('id', job_id).execute()

            except Exception as e:
                error_record = {
                    'master_sku': master_sku,
                    'finish': finish_name,
                    'finish_code': finish_code,
                    'image_type': 'lifestyle',
                    'status': 'failed',
                    'error_message': str(e)
                }

                self.supabase.table('variant_images').upsert(
                    error_record,
                    on_conflict='master_sku,finish,image_type'
                ).execute()

                results.append(error_record)

                if job_id:
                    self.supabase.table('image_generation_jobs').update({
                        'failed_variants': self.supabase.rpc(
                            'increment_failed_variants',
                            {'job_id': job_id}
                        )
                    }).eq('id', job_id).execute()

        # Mark job complete
        if job_id:
            self.supabase.table('image_generation_jobs').update({
                'status': 'completed',
                'completed_at': 'now()'
            }).eq('id', job_id).execute()

        return results

    def _build_prompt(
        self,
        product_data: Dict,
        finish_code: str,
        finish_name: str
    ) -> str:
        """Build a finish-specific image generation prompt."""
        category = product_data.get('category', 'bathroom accessory')
        dimensions = product_data.get('dimensions', '')

        finish_color = FINISH_COLOR_PROMPTS.get(finish_code, finish_name)

        prompt = f"""
Professional lifestyle photograph of a {category} bathroom fixture.

Product: {product_data.get('name', 'bathroom accessory')}
Finish: {finish_name} ({finish_color})
Dimensions: {dimensions}

Scene requirements:
- Modern luxury bathroom setting with clean marble or tile walls
- Natural daylight from a window
- The fixture must be prominently displayed and clearly show the {finish_name} finish
- Other bathroom elements should complement the {finish_name} color
- Warm, inviting atmosphere
- Professional commercial photography quality
- 4K resolution, sharp focus on the product

IMPORTANT: The metal finish must clearly be {finish_color}. Do not show chrome if the finish is brass.
"""
        return prompt.strip()

    def _upload_to_gcs(self, image_bytes: bytes, path: str) -> str:
        """Upload image to Google Cloud Storage."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(path)
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        return f"gs://{self.bucket_name}/{path}"


def generate_all_variant_images(master_sku: str, product_data: Dict) -> str:
    """
    Entry point for generating all variant images.

    Returns job ID for tracking.
    """
    supabase = get_supabase_client()

    # Create job record
    job = supabase.table('image_generation_jobs').insert({
        'master_sku': master_sku,
        'total_variants': 0,
        'status': 'queued'
    }).execute()

    job_id = job.data[0]['id']

    # Start generation (would be async in production)
    generator = VariantImageGenerator()
    generator.generate_variant_images(master_sku, product_data, job_id)

    return job_id
```

### shopify_media_upload.py

```python
# src/feedops/integrations/shopify_media_upload.py

import os
import requests
from typing import List, Dict, Optional
from feedops.db import get_supabase_client

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE_NAME', 'allied-brass')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ADMIN_ACCESS_TOKEN')
SHOPIFY_API_VERSION = '2024-10'


class ShopifyMediaUploader:
    """Upload variant images to Shopify."""

    def __init__(self):
        self.base_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN
        }
        self.supabase = get_supabase_client()

    def upload_variant_image(
        self,
        shopify_product_id: str,
        shopify_variant_id: str,
        image_url: str,
        alt_text: str
    ) -> Optional[str]:
        """
        Upload an image and attach it to a variant.

        Returns the Shopify media ID.
        """
        # Step 1: Create media from URL
        create_mutation = """
        mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
          productCreateMedia(media: $media, productId: $productId) {
            media {
              id
              alt
              mediaContentType
              status
            }
            mediaUserErrors {
              field
              message
            }
            product {
              id
            }
          }
        }
        """

        variables = {
            'productId': f"gid://shopify/Product/{shopify_product_id}",
            'media': [{
                'alt': alt_text,
                'mediaContentType': 'IMAGE',
                'originalSource': image_url
            }]
        }

        response = self._execute_graphql(create_mutation, variables)

        if response.get('errors') or response.get('data', {}).get('productCreateMedia', {}).get('mediaUserErrors'):
            print(f"Error creating media: {response}")
            return None

        media_id = response['data']['productCreateMedia']['media'][0]['id']

        # Step 2: Attach media to variant
        attach_mutation = """
        mutation productVariantAppendMedia(
          $productId: ID!,
          $variantMedia: [ProductVariantAppendMediaInput!]!
        ) {
          productVariantAppendMedia(productId: $productId, variantMedia: $variantMedia) {
            product {
              id
            }
            productVariants {
              id
              media(first: 5) {
                edges {
                  node {
                    id
                  }
                }
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        attach_variables = {
            'productId': f"gid://shopify/Product/{shopify_product_id}",
            'variantMedia': [{
                'variantId': f"gid://shopify/ProductVariant/{shopify_variant_id}",
                'mediaIds': [media_id]
            }]
        }

        attach_response = self._execute_graphql(attach_mutation, attach_variables)

        if attach_response.get('errors') or attach_response.get('data', {}).get('productVariantAppendMedia', {}).get('userErrors'):
            print(f"Error attaching media to variant: {attach_response}")
            return None

        return media_id

    def publish_variant_images(self, master_sku: str) -> Dict:
        """
        Publish all ready images for a SKU to Shopify.

        Returns summary of published images.
        """
        # Get ready images
        result = self.supabase.table('variant_images') \
            .select('*') \
            .eq('master_sku', master_sku) \
            .eq('status', 'ready') \
            .execute()

        images = result.data if result.data else []
        published = 0
        failed = 0

        for image in images:
            if not image.get('shopify_variant_id'):
                continue

            # Get product ID from variant
            variant_result = self.supabase.table('variant_index') \
                .select('shopify_product_id') \
                .eq('shopify_variant_id', image['shopify_variant_id']) \
                .single() \
                .execute()

            if not variant_result.data:
                continue

            product_id = variant_result.data['shopify_product_id']

            media_id = self.upload_variant_image(
                shopify_product_id=product_id,
                shopify_variant_id=image['shopify_variant_id'],
                image_url=image['cdn_url'],
                alt_text=f"{image['master_sku']} - {image['finish']} lifestyle"
            )

            if media_id:
                # Update record
                self.supabase.table('variant_images').update({
                    'shopify_media_id': media_id,
                    'status': 'published',
                    'published_at': 'now()'
                }).eq('id', image['id']).execute()

                published += 1
            else:
                failed += 1

        return {
            'total': len(images),
            'published': published,
            'failed': failed
        }

    def _execute_graphql(self, query: str, variables: Dict) -> Dict:
        """Execute a GraphQL query against Shopify."""
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json={'query': query, 'variables': variables}
        )
        return response.json()
```

## API Implementation

### GET /api/images

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const sku = searchParams.get('sku')
  const status = searchParams.get('status')

  const supabase = await createClient()

  let query = supabase
    .from('variant_images')
    .select('*')
    .order('created_at', { ascending: false })

  if (sku) {
    query = query.eq('master_sku', sku)
  }

  if (status) {
    query = query.eq('status', status)
  }

  const { data: images } = await query.limit(100)

  // Get job status
  const { data: jobs } = await supabase
    .from('image_generation_jobs')
    .select('*')
    .eq('status', 'processing')

  // Get summary stats
  const { data: stats } = await supabase
    .from('variant_images')
    .select('status')

  const summary = {
    total: stats?.length || 0,
    ready: stats?.filter(s => s.status === 'ready').length || 0,
    published: stats?.filter(s => s.status === 'published').length || 0,
    failed: stats?.filter(s => s.status === 'failed').length || 0,
    pending: stats?.filter(s => s.status === 'pending' || s.status === 'generating').length || 0
  }

  return NextResponse.json({ images, jobs, summary })
}
```

### POST /api/images/generate-variants

```typescript
import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function POST(request: Request) {
  const { masterSku, productData } = await request.json()

  const supabase = await createClient()

  // Create job record
  const { data: job, error } = await supabase
    .from('image_generation_jobs')
    .insert({
      master_sku: masterSku,
      status: 'queued'
    })
    .select()
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 })
  }

  // In production, this would trigger Cloud Run
  // For now, return the job ID for polling

  return NextResponse.json({
    success: true,
    jobId: job.id,
    message: `Queued image generation for ${masterSku}`
  })
}
```

## UI Components

### VariantImageGrid.tsx

```tsx
'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Check, X, Clock, Upload } from 'lucide-react'
import Image from 'next/image'

interface VariantImage {
  id: string
  master_sku: string
  finish: string
  finish_code: string
  cdn_url: string
  quality_score: number
  status: 'pending' | 'generating' | 'ready' | 'published' | 'failed'
}

interface VariantImageGridProps {
  images: VariantImage[]
  onPublish?: (imageId: string) => void
}

export function VariantImageGrid({ images, onPublish }: VariantImageGridProps) {
  const statusColors = {
    pending: 'bg-gray-100',
    generating: 'bg-blue-100',
    ready: 'bg-yellow-100',
    published: 'bg-green-100',
    failed: 'bg-red-100'
  }

  const statusIcons = {
    pending: <Clock className="h-3 w-3" />,
    generating: <Clock className="h-3 w-3 animate-spin" />,
    ready: <Check className="h-3 w-3" />,
    published: <Check className="h-3 w-3" />,
    failed: <X className="h-3 w-3" />
  }

  return (
    <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {images.map((image) => (
        <Card key={image.id} className="overflow-hidden">
          <div className="aspect-square relative bg-muted">
            {image.cdn_url ? (
              <Image
                src={image.cdn_url}
                alt={`${image.master_sku} - ${image.finish}`}
                fill
                className="object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                No image
              </div>
            )}
          </div>
          <CardContent className="p-3 space-y-2">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-sm">{image.finish}</p>
                <p className="text-xs text-muted-foreground">{image.finish_code}</p>
              </div>
              <Badge
                variant="outline"
                className={statusColors[image.status]}
              >
                {statusIcons[image.status]}
                <span className="ml-1">{image.status}</span>
              </Badge>
            </div>

            {image.quality_score && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Quality</span>
                <span className="font-medium">{image.quality_score.toFixed(0)}%</span>
              </div>
            )}

            {image.status === 'ready' && onPublish && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => onPublish(image.id)}
              >
                <Upload className="h-3 w-3 mr-1" />
                Publish to Shopify
              </Button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
```

## Main Page

```tsx
// dashboard/src/app/(dashboard)/images/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { VariantImageGrid } from '@/components/images/VariantImageGrid'
import { Image, RefreshCw, Upload, Sparkles } from 'lucide-react'

export default function ImagesPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [skuFilter, setSkuFilter] = useState('')

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    const url = skuFilter
      ? `/api/images?sku=${skuFilter}`
      : '/api/images'
    const res = await fetch(url)
    const json = await res.json()
    setData(json)
    setLoading(false)
  }

  async function generateForSku() {
    if (!skuFilter) return

    setGenerating(true)
    await fetch('/api/images/generate-variants', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        masterSku: skuFilter,
        productData: {} // Would include product details
      })
    })
    setGenerating(false)
    fetchData()
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Image className="h-6 w-6" />
            Variant Images
          </h1>
          <p className="text-muted-foreground">
            Generate and manage lifestyle images for all finish variants
          </p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters & Actions */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <Input
              placeholder="Filter by SKU..."
              value={skuFilter}
              onChange={(e) => setSkuFilter(e.target.value)}
              className="max-w-xs"
            />
            <Button onClick={fetchData}>Search</Button>
            {skuFilter && (
              <Button onClick={generateForSku} disabled={generating}>
                <Sparkles className="h-4 w-4 mr-2" />
                {generating ? 'Generating...' : 'Generate All Variants'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div>Loading...</div>
      ) : data ? (
        <>
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-5">
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold">{data.summary.total}</p>
                <p className="text-sm text-muted-foreground">Total Images</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-yellow-600">{data.summary.ready}</p>
                <p className="text-sm text-muted-foreground">Ready</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-green-600">{data.summary.published}</p>
                <p className="text-sm text-muted-foreground">Published</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-red-600">{data.summary.failed}</p>
                <p className="text-sm text-muted-foreground">Failed</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-blue-600">{data.summary.pending}</p>
                <p className="text-sm text-muted-foreground">Pending</p>
              </CardContent>
            </Card>
          </div>

          {/* Active Jobs */}
          {data.jobs?.length > 0 && (
            <Card className="bg-blue-50 border-blue-200">
              <CardHeader>
                <CardTitle className="text-blue-800">Generation in Progress</CardTitle>
              </CardHeader>
              <CardContent>
                {data.jobs.map((job: any) => (
                  <div key={job.id} className="flex justify-between items-center">
                    <span>SKU {job.master_sku}</span>
                    <span>
                      {job.completed_variants} / {job.total_variants} variants
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Image Grid */}
          <Card>
            <CardHeader>
              <CardTitle>Variant Images</CardTitle>
            </CardHeader>
            <CardContent>
              <VariantImageGrid images={data.images || []} />
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
```

## Success Criteria

1. [ ] Generate images for all 28 finishes of a SKU
2. [ ] IPTC metadata applied to all images
3. [ ] Images stored in GCS with CDN URLs
4. [ ] Shopify variant media upload works
5. [ ] Quality scoring for generated images
6. [ ] Progress tracking for generation jobs
7. [ ] Dashboard shows all variant images
8. [ ] Bulk publish to Shopify

## Future Enhancements

- GMC supplemental feed auto-update with lifestyle_image_link
- Image regeneration with feedback
- A/B testing of different lifestyle scenes
- Automatic quality threshold filtering
- Batch generation for multiple SKUs
- Scene variation per product category
