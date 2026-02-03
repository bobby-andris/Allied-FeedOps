/**
 * Publishing utilities for FeedOps dashboard.
 *
 * This module provides functions to publish optimized product content
 * to Google Merchant Center (via Sheets), Shopify, and Bing.
 */

// Types
export type {
  Platform,
  Environment,
  PublishRequest,
  ShopifyPublishRequest,
  PublishResult,
  BatchPublishRequest,
  BatchPublishResult,
  GoogleSheetsRow,
  SheetColumnMap,
  VariantIndexRow,
  GeneratedContentRow,
  PublishEventInsert,
} from './types'

// Google Sheets publishing
export {
  getGoogleSheetsClient,
  getSpreadsheetId,
  getColumnHeaders,
  buildColumnMap,
  getExistingIds,
  publishToGoogleSheets,
} from './google-sheets'
export type { PublishToGoogleSheetsResult } from './google-sheets'

// Shopify publishing
export {
  updateShopifyProduct,
  addProductTags,
  publishToShopify,
} from './shopify'
export type {
  UpdateProductResult,
  AddTagsResult,
  PublishToShopifyResult,
} from './shopify'
