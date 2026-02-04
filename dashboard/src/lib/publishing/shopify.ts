/**
 * Shopify publishing integration via GraphQL Admin API.
 *
 * Publishes optimized product content (title, description) to Shopify
 * and adds environment tracking tags.
 */

import type { Environment } from './types'

const SHOPIFY_API_VERSION = '2026-01'

// GraphQL mutation for updating product title and description
const UPDATE_PRODUCT_MUTATION = `
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      descriptionHtml
      tags
    }
    userErrors {
      field
      message
    }
  }
}
`

// GraphQL mutation for adding tags to a product
const ADD_TAGS_MUTATION = `
mutation AddProductTags($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
    node {
      ... on Product {
        id
        tags
      }
    }
    userErrors {
      field
      message
    }
  }
}
`

interface ShopifyGraphQLResponse<T = unknown> {
  data?: T
  errors?: Array<{ message: string }>
}

interface ProductUpdateResponse {
  productUpdate: {
    product: {
      id: string
      title: string
      descriptionHtml: string
      tags: string[]
    } | null
    userErrors: Array<{
      field: string[]
      message: string
    }>
  }
}

interface TagsAddResponse {
  tagsAdd: {
    node: {
      id: string
      tags: string[]
    } | null
    userErrors: Array<{
      field: string[]
      message: string
    }>
  }
}

/**
 * Get Shopify API credentials from environment variables.
 */
function getShopifyCredentials(): { storeUrl: string; accessToken: string } {
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
 * Normalize store URL to just the hostname.
 */
function normalizeStoreHost(storeUrl: string): string {
  // Remove protocol if present
  let host = storeUrl
    .replace('https://', '')
    .replace('http://', '')
    .trim()
    .replace(/\/$/, '')

  // Remove any path components
  const slashIndex = host.indexOf('/')
  if (slashIndex !== -1) {
    host = host.substring(0, slashIndex)
  }

  return host
}

/**
 * Convert a numeric product ID to GID format.
 */
function toProductGid(productId: string): string {
  if (productId.startsWith('gid://')) {
    return productId
  }
  return `gid://shopify/Product/${productId}`
}

/**
 * Execute a GraphQL query/mutation against Shopify Admin API.
 */
async function shopifyGraphQL<T>(
  query: string,
  variables: Record<string, unknown>
): Promise<ShopifyGraphQLResponse<T>> {
  const { storeUrl, accessToken } = getShopifyCredentials()
  const host = normalizeStoreHost(storeUrl)
  const endpoint = `https://${host}/admin/api/${SHOPIFY_API_VERSION}/graphql.json`

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': accessToken,
    },
    body: JSON.stringify({ query, variables }),
  })

  if (!response.ok) {
    throw new Error(
      `Shopify API request failed: ${response.status} ${response.statusText}`
    )
  }

  return response.json() as Promise<ShopifyGraphQLResponse<T>>
}

export interface UpdateProductResult {
  success: boolean
  product?: {
    id: string
    title: string
    descriptionHtml: string
    tags: string[]
  }
  errors: string[]
}

/**
 * Update Shopify product title and/or description.
 */
export async function updateShopifyProduct(
  productId: string,
  title?: string,
  descriptionHtml?: string
): Promise<UpdateProductResult> {
  if (!title && !descriptionHtml) {
    return {
      success: false,
      errors: ['No title or description provided'],
    }
  }

  const gid = toProductGid(productId)
  const input: Record<string, string> = { id: gid }

  if (title) {
    input.title = title
  }
  if (descriptionHtml) {
    input.descriptionHtml = descriptionHtml
  }

  try {
    const response = await shopifyGraphQL<ProductUpdateResponse>(
      UPDATE_PRODUCT_MUTATION,
      { input }
    )

    // Check for GraphQL-level errors
    if (response.errors && response.errors.length > 0) {
      return {
        success: false,
        errors: response.errors.map((e) => e.message),
      }
    }

    // Check for user errors from the mutation
    const userErrors = response.data?.productUpdate?.userErrors || []
    if (userErrors.length > 0) {
      return {
        success: false,
        errors: userErrors.map((e) => `${e.field.join('.')}: ${e.message}`),
      }
    }

    const product = response.data?.productUpdate?.product
    if (!product) {
      return {
        success: false,
        errors: ['No product returned from update'],
      }
    }

    return {
      success: true,
      product,
      errors: [],
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return {
      success: false,
      errors: [`Shopify API error: ${message}`],
    }
  }
}

export interface AddTagsResult {
  success: boolean
  tags?: string[]
  errors: string[]
}

/**
 * Add tags to a Shopify product.
 */
export async function addProductTags(
  productId: string,
  tags: string[]
): Promise<AddTagsResult> {
  if (tags.length === 0) {
    return {
      success: true,
      tags: [],
      errors: [],
    }
  }

  const gid = toProductGid(productId)

  try {
    const response = await shopifyGraphQL<TagsAddResponse>(ADD_TAGS_MUTATION, {
      id: gid,
      tags,
    })

    // Check for GraphQL-level errors
    if (response.errors && response.errors.length > 0) {
      return {
        success: false,
        errors: response.errors.map((e) => e.message),
      }
    }

    // Check for user errors from the mutation
    const userErrors = response.data?.tagsAdd?.userErrors || []
    if (userErrors.length > 0) {
      return {
        success: false,
        errors: userErrors.map((e) => `${e.field.join('.')}: ${e.message}`),
      }
    }

    const node = response.data?.tagsAdd?.node
    return {
      success: true,
      tags: node?.tags || [],
      errors: [],
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return {
      success: false,
      errors: [`Shopify API error: ${message}`],
    }
  }
}

export interface PublishToShopifyResult {
  success: boolean
  product_id: string
  tracking_tag: string
  environment: Environment
  errors: string[]
  product?: {
    id: string
    title: string
    descriptionHtml: string
    tags: string[]
  }
}

/**
 * Publish optimized content to Shopify with environment tracking.
 *
 * This is the main publish function that:
 * 1. Adds environment-specific tag (feedops-staging or feedops-production)
 * 2. Updates the product title and description
 */
export async function publishToShopify(
  productId: string,
  title: string,
  descriptionHtml: string,
  environment: Environment
): Promise<PublishToShopifyResult> {
  const trackingTag = `feedops-${environment}`

  // First, add the tracking tag
  const tagResult = await addProductTags(productId, [trackingTag])
  if (!tagResult.success) {
    return {
      success: false,
      product_id: productId,
      tracking_tag: trackingTag,
      environment,
      errors: tagResult.errors.length > 0
        ? tagResult.errors
        : ['Failed to add tracking tag'],
    }
  }

  // Then update the product
  const updateResult = await updateShopifyProduct(
    productId,
    title,
    descriptionHtml
  )

  if (!updateResult.success) {
    return {
      success: false,
      product_id: productId,
      tracking_tag: trackingTag,
      environment,
      errors: updateResult.errors.length > 0
        ? updateResult.errors
        : ['Failed to update product'],
    }
  }

  return {
    success: true,
    product_id: productId,
    tracking_tag: trackingTag,
    environment,
    errors: [],
    product: updateResult.product,
  }
}
