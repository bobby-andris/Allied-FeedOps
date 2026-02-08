/**
 * Shopify image upload and management via GraphQL Admin API.
 *
 * Handles:
 * - Uploading lifestyle images to Shopify from Supabase Storage
 * - Associating images with specific product variants
 * - Polling for image processing completion
 * - Returning Shopify CDN URLs for production use
 */

const SHOPIFY_API_VERSION = '2026-01'

// GraphQL mutation for uploading media to product
const PRODUCT_CREATE_MEDIA_MUTATION = `
mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
  productCreateMedia(media: $media, productId: $productId) {
    media {
      id
      alt
      status
      ... on MediaImage {
        image {
          url
        }
      }
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
`

// GraphQL mutation for associating media with variants
const PRODUCT_VARIANT_APPEND_MEDIA_MUTATION = `
mutation productVariantAppendMedia($productId: ID!, $variantMedia: [ProductVariantAppendMediaInput!]!) {
  productVariantAppendMedia(productId: $productId, variantMedia: $variantMedia) {
    product {
      id
    }
    userErrors {
      field
      message
    }
  }
}
`

// GraphQL query for checking media status
const CHECK_MEDIA_STATUS_QUERY = `
query checkMediaStatus($mediaId: ID!) {
  node(id: $mediaId) {
    ... on MediaImage {
      id
      status
      image {
        url
      }
    }
  }
}
`

interface ShopifyCredentials {
  storeUrl: string
  accessToken: string
}

interface UploadImageResult {
  mediaId: string
  cdnUrl: string | null
  status: 'PROCESSING' | 'READY' | 'FAILED'
}

/**
 * Get Shopify API credentials from environment variables.
 */
function getShopifyCredentials(): ShopifyCredentials {
  const storeUrl = process.env.SHOPIFY_STORE_URL
  const accessToken = process.env.SHOPIFY_ACCESS_TOKEN

  if (!storeUrl || !accessToken) {
    throw new Error(
      'Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN environment variables.'
    )
  }

  return { storeUrl, accessToken }
}

/**
 * Normalize store URL to API endpoint.
 */
function getGraphQLEndpoint(storeUrl: string): string {
  const hostname = storeUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')
  return `https://${hostname}/admin/api/${SHOPIFY_API_VERSION}/graphql.json`
}

/**
 * Execute a Shopify GraphQL mutation/query.
 */
async function executeShopifyGraphQL<T>(
  query: string,
  variables: Record<string, unknown>
): Promise<T> {
  const { storeUrl, accessToken } = getShopifyCredentials()
  const endpoint = getGraphQLEndpoint(storeUrl)

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': accessToken,
    },
    body: JSON.stringify({ query, variables }),
  })

  if (!response.ok) {
    throw new Error(`Shopify API error: ${response.status} ${response.statusText}`)
  }

  const json = await response.json()

  if (json.errors) {
    throw new Error(`GraphQL errors: ${JSON.stringify(json.errors)}`)
  }

  return json.data as T
}

/**
 * Upload lifestyle image from Supabase Storage to Shopify.
 *
 * @param supabaseImageUrl - Public URL from Supabase Storage
 * @param shopifyProductId - Shopify product GID (e.g., "gid://shopify/Product/123")
 * @param altText - Alt text for accessibility
 * @returns Upload result with media ID and status
 */
export async function uploadLifestyleImageToShopify(
  supabaseImageUrl: string,
  shopifyProductId: string,
  altText?: string
): Promise<UploadImageResult> {
  const result = await executeShopifyGraphQL<{
    productCreateMedia: {
      media: Array<{
        id: string
        status: string
        image?: { url: string } | null
      }>
      mediaUserErrors: Array<{ field: string[]; message: string }>
    }
  }>(PRODUCT_CREATE_MEDIA_MUTATION, {
    productId: shopifyProductId,
    media: [
      {
        originalSource: supabaseImageUrl,
        mediaContentType: 'IMAGE',
        alt: altText || 'Lifestyle image',
      },
    ],
  })

  if (result.productCreateMedia.mediaUserErrors.length > 0) {
    const errors = result.productCreateMedia.mediaUserErrors
      .map((e) => e.message)
      .join(', ')
    throw new Error(`Shopify media upload errors: ${errors}`)
  }

  const media = result.productCreateMedia.media[0]

  return {
    mediaId: media.id,
    cdnUrl: media.image?.url || null,
    status: media.status as 'PROCESSING' | 'READY' | 'FAILED',
  }
}

/**
 * Poll Shopify media status until READY or timeout.
 *
 * @param mediaId - Shopify media GID
 * @param maxAttempts - Maximum polling attempts (default: 10)
 * @param delayMs - Delay between attempts in milliseconds (default: 2000)
 * @returns Final status and CDN URL
 */
export async function pollMediaStatus(
  mediaId: string,
  maxAttempts: number = 10,
  delayMs: number = 2000
): Promise<UploadImageResult> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const result = await executeShopifyGraphQL<{
      node: {
        id: string
        status: string
        image: { url: string } | null
      }
    }>(CHECK_MEDIA_STATUS_QUERY, { mediaId })

    const status = result.node.status as 'PROCESSING' | 'READY' | 'FAILED'

    if (status === 'READY' || status === 'FAILED') {
      return {
        mediaId,
        cdnUrl: result.node.image?.url || null,
        status,
      }
    }

    // Wait before next attempt
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }

  throw new Error(`Media processing timeout after ${maxAttempts} attempts`)
}

/**
 * Associate media with specific product variant.
 *
 * @param shopifyProductId - Shopify product GID
 * @param shopifyVariantId - Shopify variant GID
 * @param mediaId - Shopify media GID
 */
export async function associateImageWithVariant(
  shopifyProductId: string,
  shopifyVariantId: string,
  mediaId: string
): Promise<void> {
  const result = await executeShopifyGraphQL<{
    productVariantAppendMedia: {
      userErrors: Array<{ field: string[]; message: string }>
    }
  }>(PRODUCT_VARIANT_APPEND_MEDIA_MUTATION, {
    productId: shopifyProductId,
    variantMedia: [
      {
        variantId: shopifyVariantId,
        mediaIds: [mediaId],
      },
    ],
  })

  if (result.productVariantAppendMedia.userErrors.length > 0) {
    const errors = result.productVariantAppendMedia.userErrors
      .map((e) => e.message)
      .join(', ')
    throw new Error(`Shopify variant media association errors: ${errors}`)
  }
}

/**
 * Complete workflow: Upload image to Shopify, wait for processing, associate with variant.
 *
 * @param supabaseImageUrl - Public URL from Supabase Storage
 * @param shopifyProductId - Shopify product GID
 * @param shopifyVariantId - Shopify variant GID (optional, for variant-specific images)
 * @param altText - Alt text for accessibility
 * @returns Shopify CDN URL
 */
export async function uploadAndAssociateImage(
  supabaseImageUrl: string,
  shopifyProductId: string,
  shopifyVariantId?: string,
  altText?: string
): Promise<{ mediaId: string; cdnUrl: string }> {
  // Step 1: Upload image to Shopify product
  const uploadResult = await uploadLifestyleImageToShopify(
    supabaseImageUrl,
    shopifyProductId,
    altText
  )

  console.log(`[Shopify] Image uploaded, status: ${uploadResult.status}, media ID: ${uploadResult.mediaId}`)

  // Step 2: Poll until READY
  const finalResult = await pollMediaStatus(uploadResult.mediaId)

  if (finalResult.status === 'FAILED') {
    throw new Error('Shopify media processing failed')
  }

  if (!finalResult.cdnUrl) {
    throw new Error('Shopify CDN URL not returned after processing')
  }

  // Step 3: Associate with variant if specified
  if (shopifyVariantId) {
    await associateImageWithVariant(
      shopifyProductId,
      shopifyVariantId,
      finalResult.mediaId
    )
    console.log(`[Shopify] Image associated with variant ${shopifyVariantId}`)
  }

  return {
    mediaId: finalResult.mediaId,
    cdnUrl: finalResult.cdnUrl,
  }
}

/**
 * Upload product-level lifestyle image to Shopify product.
 * Used for images that appear on the product detail page (not variant-specific).
 *
 * @param imageUrl - Public URL from Supabase Storage
 * @param shopifyProductId - Shopify product GID (e.g., "gid://shopify/Product/123") or numeric ID
 * @param altText - Alt text for accessibility
 * @returns Upload result with media ID and CDN URL
 */
export async function uploadProductImage(
  imageUrl: string,
  shopifyProductId: string,
  altText: string
): Promise<{ mediaId: string; cdnUrl: string }> {
  // Convert product ID to GID format if needed
  const productGid = shopifyProductId.startsWith('gid://')
    ? shopifyProductId
    : `gid://shopify/Product/${shopifyProductId}`

  return await uploadAndAssociateImage(imageUrl, productGid, undefined, altText)
}

/**
 * Upload variant-level lifestyle image to Shopify and associate with specific variant.
 * These images are hosted on Shopify CDN but published to GMC feed (not shown on Shopify product pages).
 *
 * @param imageUrl - Public URL from Supabase Storage
 * @param shopifyProductId - Shopify product GID or numeric ID
 * @param shopifyVariantId - Shopify variant GID or numeric ID
 * @param altText - Alt text for accessibility
 * @returns Upload result with media ID and CDN URL
 */
export async function uploadVariantImage(
  imageUrl: string,
  shopifyProductId: string,
  shopifyVariantId: string,
  altText: string
): Promise<{ mediaId: string; cdnUrl: string }> {
  // Convert IDs to GID format if needed
  const productGid = shopifyProductId.startsWith('gid://')
    ? shopifyProductId
    : `gid://shopify/Product/${shopifyProductId}`

  const variantGid = shopifyVariantId.startsWith('gid://')
    ? shopifyVariantId
    : `gid://shopify/ProductVariant/${shopifyVariantId}`

  return await uploadAndAssociateImage(imageUrl, productGid, variantGid, altText)
}
