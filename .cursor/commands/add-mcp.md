---
description: Add or configure MCP (Model Context Protocol) servers for feed operations
---

# /add-mcp

## Purpose
Configure MCP servers to extend feed optimization capabilities with external data sources and services.

## Usage
```
/add-mcp [server-name] [configuration]
```

## Available MCP Integrations

### 1. Shopify MCP
Connect to Shopify stores for direct product data access.

```
/add-mcp shopify
```

**Capabilities**:
- Read product catalog (titles, descriptions, variants)
- Access metafields for additional attributes
- Pull collection and category data
- Retrieve product performance metrics

**Configuration Required**:
```json
{
  "store_url": "your-store.myshopify.com",
  "access_token": "[SHOPIFY_ACCESS_TOKEN]",
  "api_version": "2024-01"
}
```

**Use Cases**:
- Audit current product content
- Identify products needing optimization
- Export optimized content back to Shopify
- Sync metafields for attribute enrichment

### 2. Google Merchant Center MCP
Connect to Google Merchant Center for feed management.

```
/add-mcp google-merchant
```

**Capabilities**:
- Read product feed data
- Access product status and issues
- Pull performance metrics (impressions, clicks)
- Identify disapproved products

**Configuration Required**:
```json
{
  "merchant_id": "[MERCHANT_CENTER_ID]",
  "credentials_path": "./google-credentials.json"
}
```

**Use Cases**:
- Identify products with feed issues
- Track optimization impact on performance
- Export optimized titles/descriptions to feed
- Monitor disapprovals and compliance

### 3. Microsoft Merchant Center MCP
Connect to Microsoft Advertising for Bing Shopping.

```
/add-mcp microsoft-merchant
```

**Capabilities**:
- Read Bing Shopping feed
- Access product performance data
- Identify Copilot recommendation eligibility
- Track attribute completeness scores

**Configuration Required**:
```json
{
  "merchant_id": "[MS_MERCHANT_ID]",
  "client_id": "[CLIENT_ID]",
  "client_secret": "[CLIENT_SECRET]"
}
```

**Use Cases**:
- Compare Google vs Bing performance
- Ensure Bing-specific compliance
- Track Copilot visibility
- Optimize for Microsoft's literal matching

### 4. Google Analytics MCP
Connect to GA4 for conversion and behavior data.

```
/add-mcp google-analytics
```

**Capabilities**:
- Pull conversion data by product
- Access search query performance
- Track landing page metrics
- Measure optimization impact

**Configuration Required**:
```json
{
  "property_id": "[GA4_PROPERTY_ID]",
  "credentials_path": "./google-credentials.json"
}
```

**Use Cases**:
- Identify high-view/low-convert products
- Correlate description length with CVR
- Track A/B test results
- Measure incrementality

### 5. Supabase MCP
Use Supabase for product data storage and optimization history.

```
/add-mcp supabase
```

**Capabilities**:
- Store product optimization history
- Track version changes
- Query optimization performance
- Manage optimization workflows

**Configuration Required**:
```json
{
  "url": "[SUPABASE_URL]",
  "anon_key": "[SUPABASE_ANON_KEY]",
  "service_key": "[SUPABASE_SERVICE_KEY]"
}
```

**Use Cases**:
- Track optimization iterations
- Store before/after comparisons
- Manage approval workflows
- Build optimization audit trail

## Workflow Integration

### Setup Flow
```
1. /add-mcp shopify
   → Configure Shopify connection
   → Verify product data access

2. /add-mcp google-merchant
   → Configure GMC connection
   → Verify feed access

3. /add-mcp google-analytics
   → Configure GA4 connection
   → Verify metrics access
```

### Optimization Flow with MCPs
```
1. Pull product data via Shopify MCP
   ↓
2. Analyze performance via GA MCP
   ↓
3. Generate optimized content (agents)
   ↓
4. Verify content (verifier agent)
   ↓
5. Push to GMC via Google Merchant MCP
   ↓
6. Track results via GA MCP
```

## Configuration Management

### View Current MCPs
```
/add-mcp --list
```

Output:
```markdown
## Configured MCP Servers

| Server | Status | Last Sync |
|--------|--------|-----------|
| shopify | ✅ Connected | 2 hours ago |
| google-merchant | ✅ Connected | 1 hour ago |
| google-analytics | ⚠️ Auth expiring | 3 hours ago |
| microsoft-merchant | ❌ Not configured | - |
```

### Test Connection
```
/add-mcp shopify --test
```

Output:
```markdown
## Shopify MCP Connection Test

✅ Authentication: Valid
✅ Product Read: 1,247 products accessible
✅ Metafield Access: Enabled
✅ API Rate Limit: 38/40 requests remaining

Connection healthy.
```

### Remove MCP
```
/add-mcp shopify --remove
```

## Security Notes

1. **Never commit credentials** - Use environment variables or secure storage
2. **Minimum permissions** - Request only needed scopes
3. **Token rotation** - Refresh credentials regularly
4. **Audit access** - Log all MCP data operations

## Troubleshooting

### Common Issues

**Authentication Failed**
```
Error: Invalid credentials for shopify MCP

Solutions:
1. Verify access token is current
2. Check API version compatibility
3. Confirm store URL format
```

**Rate Limited**
```
Error: Rate limit exceeded for google-merchant MCP

Solutions:
1. Implement request batching
2. Add delay between requests
3. Cache frequently accessed data
```

**Permission Denied**
```
Error: Insufficient permissions for metafield access

Solutions:
1. Update app permissions in Shopify
2. Regenerate access token with correct scopes
3. Verify admin access level
```
