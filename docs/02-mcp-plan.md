# Allied FeedOps: MCP Integration Plan

## Overview

This document outlines the plan for integrating Model Context Protocol (MCP) servers to enable automated data flow between Allied FeedOps and external systems.

---

## Architecture Vision

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Allied FeedOps Core                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│    │  Data    │   │   Feed   │   │ Verifier │   │  Report  │          │
│    │ Analyst  │   │Copywriter│   │  Agent   │   │Generator │          │
│    └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘          │
│         │              │              │              │                  │
│         └──────────────┴──────────────┴──────────────┘                  │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                  │
│                    │   MCP Gateway   │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │  Shopify  │      │  Google   │      │ Microsoft │
    │   MCP     │      │Merchant MCP│     │Merchant MCP│
    └───────────┘      └───────────┘      └───────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │  Shopify  │      │  Google   │      │   Bing    │
    │   Store   │      │ Shopping  │      │ Shopping  │
    └───────────┘      └───────────┘      └───────────┘
```

---

## Phase 1: Foundation (Current)

### Available MCPs

The following MCP servers are already configured in the workspace:

| MCP Server | Purpose | Status |
|------------|---------|--------|
| user-Shopify | Shopify Admin API access | Available |
| user-google-ads-mcp | Google Ads management | Available |
| user-analytics-mcp | Analytics data access | Available |
| user-Supabase | Database storage | Available |
| user-Context7 | Documentation lookup | Available |

### Immediate Integration: Shopify MCP

**Connection**: Already available via `user-Shopify`

**Capabilities**:
- Read all products with attributes
- Access metafields for extended data
- Retrieve collection information
- Pull product variants

**FeedOps Use Cases**:
```
1. AUDIT: Pull all products → Score each → Identify optimization targets
2. OPTIMIZE: Generate content → Push back to Shopify
3. SYNC: Ensure feed data matches Shopify source
```

**Implementation Steps**:
1. Verify Shopify MCP connection
2. Map Shopify product fields to FeedOps schema
3. Create product data extraction workflow
4. Test read/write operations
5. Build audit automation

---

## Phase 2: Analytics Integration

### Google Analytics MCP

**Purpose**: Track optimization impact on conversion

**Required Data**:
- Product-level conversion rates
- Landing page metrics (bounce rate, time on page)
- Search query → product mapping
- Revenue by product

**Integration Points**:
```yaml
analytics_queries:
  - name: "product_performance"
    metrics: [impressions, clicks, conversions, revenue]
    dimensions: [product_id, date]
    
  - name: "optimization_impact"
    metrics: [cvr, bounce_rate, avg_session_duration]
    dimensions: [product_id, optimization_date]
    
  - name: "query_matching"
    metrics: [impressions, clicks]
    dimensions: [search_term, product_id]
```

**FeedOps Use Cases**:
```
1. IDENTIFY: Find high-view/low-convert products
2. CORRELATE: Link description length to CVR
3. MEASURE: Track before/after optimization
4. REPORT: Generate impact dashboards
```

### Google Ads MCP

**Purpose**: Manage Shopping campaign optimization

**Required Data**:
- Product-level ad performance
- Quality Score indicators
- Search terms triggering ads
- Competitive metrics

**Integration Points**:
```yaml
ads_queries:
  - name: "shopping_performance"
    metrics: [impressions, clicks, conversions, cost, roas]
    dimensions: [product_id, campaign_id]
    
  - name: "quality_signals"
    metrics: [impression_share, search_impression_share]
    dimensions: [product_id]
    
  - name: "search_terms"
    metrics: [impressions, clicks]
    dimensions: [search_term, product_id]
```

---

## Phase 3: Merchant Center Integration

### Google Merchant Center MCP

**Purpose**: Direct feed management and monitoring

**Capabilities Needed**:
- Read current product feed
- Identify disapproved products
- Access feed processing errors
- Update product data

**Implementation Approach**:

Option A: Content API Integration
```
- Use Google Content API for Shopping
- Real-time updates
- Full CRUD operations
- Requires OAuth setup
```

Option B: Supplemental Feed
```
- Generate optimized content as supplemental feed
- Upload via Google Merchant Center
- Overrides primary feed attributes
- Simpler implementation
```

**Recommended**: Start with Option B (supplemental feed), migrate to Option A for real-time sync.

**Data Schema Mapping**:
```yaml
feedops_to_gmc:
  title: "title"
  description: "description"
  brand: "brand"
  product_type: "product_type"
  material: "material"
  size: "size"
  color: "color"
  custom_label_0: "optimization_score"
  custom_label_1: "optimization_date"
```

### Microsoft Merchant Center MCP

**Purpose**: Bing Shopping feed management

**Capabilities Needed**:
- Read current feed status
- Track Copilot recommendation eligibility
- Monitor attribute completeness
- Update product data

**Differences from Google**:
- More literal keyword matching
- Confidence score for Copilot
- Exact match keyword priority
- Different category taxonomy

**Implementation**:
```yaml
bing_specific:
  - Ensure brand always in title (required)
  - Complete all optional attributes (Copilot confidence)
  - Include synonyms in description
  - Map to Microsoft category taxonomy
```

---

## Phase 4: Data Storage (Supabase)

### Schema Design

```sql
-- Products table (source of truth)
CREATE TABLE products (
  id UUID PRIMARY KEY,
  sku TEXT UNIQUE NOT NULL,
  brand TEXT,
  product_type TEXT,
  collection TEXT,
  attributes JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content versions (optimization history)
CREATE TABLE content_versions (
  id UUID PRIMARY KEY,
  product_id UUID REFERENCES products(id),
  version_number INTEGER,
  title TEXT,
  description TEXT,
  quality_score DECIMAL,
  status TEXT, -- draft, approved, live, archived
  source_verification JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by TEXT
);

-- Performance tracking
CREATE TABLE performance_metrics (
  id UUID PRIMARY KEY,
  product_id UUID REFERENCES products(id),
  content_version_id UUID REFERENCES content_versions(id),
  platform TEXT, -- google, bing, shopify
  date DATE,
  impressions INTEGER,
  clicks INTEGER,
  conversions INTEGER,
  revenue DECIMAL,
  ctr DECIMAL GENERATED ALWAYS AS (clicks::DECIMAL / NULLIF(impressions, 0)) STORED,
  cvr DECIMAL GENERATED ALWAYS AS (conversions::DECIMAL / NULLIF(clicks, 0)) STORED
);

-- Optimization tracking
CREATE TABLE optimizations (
  id UUID PRIMARY KEY,
  product_id UUID REFERENCES products(id),
  before_version_id UUID REFERENCES content_versions(id),
  after_version_id UUID REFERENCES content_versions(id),
  optimization_type TEXT, -- title, description, both
  score_before DECIMAL,
  score_after DECIMAL,
  deployed_at TIMESTAMPTZ,
  performance_delta JSONB,
  status TEXT -- pending, deployed, rolled_back
);
```

### FeedOps Use Cases

```
1. VERSION CONTROL: Track all content changes
2. A/B TESTING: Compare version performance
3. AUDIT TRAIL: Record who changed what when
4. REPORTING: Query historical performance
5. ROLLBACK: Restore previous versions
```

---

## Phase 5: Automation Pipelines

### Daily Audit Pipeline

```yaml
name: "daily_feed_audit"
schedule: "0 6 * * *"  # 6 AM daily
steps:
  - name: "pull_products"
    mcp: "shopify"
    action: "list_products"
    
  - name: "score_products"
    action: "calculate_quality_scores"
    
  - name: "identify_issues"
    action: "filter_below_threshold"
    threshold: 80
    
  - name: "store_results"
    mcp: "supabase"
    action: "insert_audit_results"
    
  - name: "alert_if_needed"
    condition: "critical_issues > 0"
    action: "send_notification"
```

### Optimization Pipeline

```yaml
name: "optimize_product"
trigger: "manual or scheduled"
steps:
  - name: "fetch_product"
    mcp: "shopify"
    action: "get_product"
    params: ["sku"]
    
  - name: "analyze_current"
    agent: "data_analyst"
    
  - name: "generate_content"
    agent: "feed_copywriter"
    
  - name: "verify_content"
    agent: "verifier"
    
  - name: "store_version"
    mcp: "supabase"
    action: "create_content_version"
    
  - name: "deploy_if_approved"
    condition: "quality_score >= 80"
    mcp: "shopify"
    action: "update_product"
```

### Performance Tracking Pipeline

```yaml
name: "track_performance"
schedule: "0 8 * * *"  # 8 AM daily
steps:
  - name: "fetch_ga_metrics"
    mcp: "analytics"
    action: "get_product_performance"
    
  - name: "fetch_ads_metrics"
    mcp: "google_ads"
    action: "get_shopping_performance"
    
  - name: "calculate_changes"
    action: "compare_to_baseline"
    
  - name: "store_metrics"
    mcp: "supabase"
    action: "insert_performance_metrics"
    
  - name: "identify_winners"
    action: "find_significant_improvements"
    
  - name: "generate_report"
    action: "create_performance_report"
```

---

## Implementation Roadmap

### Sprint 1: Foundation
- [ ] Verify Shopify MCP connection
- [ ] Create product data schema mapping
- [ ] Build basic product read workflow
- [ ] Test with sample products

### Sprint 2: Core Integration
- [ ] Implement Supabase schema
- [ ] Create content versioning system
- [ ] Build optimization storage workflow
- [ ] Add audit trail logging

### Sprint 3: Analytics
- [ ] Connect Google Analytics MCP
- [ ] Build performance tracking queries
- [ ] Create baseline metrics capture
- [ ] Implement before/after comparison

### Sprint 4: Merchant Centers
- [ ] Implement Google Merchant Center sync
- [ ] Add Microsoft Merchant Center sync
- [ ] Build feed export automation
- [ ] Create compliance monitoring

### Sprint 5: Automation
- [ ] Deploy daily audit pipeline
- [ ] Create optimization triggers
- [ ] Build performance alerts
- [ ] Implement reporting automation

---

## Security Considerations

### Credential Management
```yaml
secrets:
  - name: SHOPIFY_ACCESS_TOKEN
    storage: environment_variable
    rotation: 90_days
    
  - name: GOOGLE_CREDENTIALS
    storage: secure_file
    rotation: 365_days
    
  - name: SUPABASE_SERVICE_KEY
    storage: environment_variable
    rotation: 90_days
```

### Access Control
```yaml
permissions:
  data_analyst:
    - read: all_products
    - read: performance_metrics
    - write: audit_results
    
  feed_copywriter:
    - read: product_attributes
    - write: content_versions
    
  verifier:
    - read: content_versions
    - read: product_attributes
    - write: verification_results
    
  admin:
    - all: all_resources
```

### Data Handling
```yaml
data_policies:
  - no_pii_in_content: true
  - audit_all_changes: true
  - retain_versions: 365_days
  - encrypt_at_rest: true
```

---

## Monitoring and Observability

### Health Checks
```yaml
health_checks:
  - name: "shopify_connection"
    interval: 5_minutes
    timeout: 30_seconds
    
  - name: "supabase_connection"
    interval: 5_minutes
    timeout: 30_seconds
    
  - name: "analytics_connection"
    interval: 15_minutes
    timeout: 60_seconds
```

### Metrics to Track
```yaml
operational_metrics:
  - products_audited_daily
  - products_optimized_daily
  - average_quality_score
  - api_call_latency
  - error_rate_by_mcp
  
business_metrics:
  - optimization_impact_ctr
  - optimization_impact_cvr
  - cost_per_optimization
  - time_to_deploy
```

### Alerting
```yaml
alerts:
  - name: "high_error_rate"
    condition: "error_rate > 5%"
    severity: critical
    
  - name: "quality_score_drop"
    condition: "avg_score_change < -10%"
    severity: warning
    
  - name: "mcp_connection_failed"
    condition: "health_check_failed"
    severity: critical
```
