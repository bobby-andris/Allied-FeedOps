---
description: Generate documentation and reports for feed optimization workflows
---

# /generate-docs

## Purpose
Generate documentation, reports, and exports for feed optimization activities.

## Usage
```
/generate-docs [doc-type] [options]
```

## Document Types

### 1. Optimization Report
Summary of optimization activities and results.

```
/generate-docs optimization-report --period=last-30-days
```

**Output**:
```markdown
# Feed Optimization Report
**Period**: [Start Date] - [End Date]
**Generated**: [Timestamp]

## Executive Summary
- Products optimized: [X]
- Average quality score improvement: [X]%
- Estimated impact: [metrics]

## Optimization Activity

### By Category
| Category | Products | Avg Score Before | Avg Score After |
|----------|----------|-----------------|-----------------|
| Towel Bars | 45 | 52% | 87% |
| Grab Bars | 23 | 48% | 91% |
| Mirrors | 18 | 55% | 84% |

### Top Improvements
1. [SKU] - Score improved from X% to Y%
2. [SKU] - Score improved from X% to Y%

### Pending Optimizations
- [X] products below 70% quality score
- [Y] products missing key attributes

## Performance Impact
[If performance data available]
- CTR change: +X%
- CVR change: +X%
- ROAS change: +X%
```

### 2. Feed Audit Report
Comprehensive analysis of current feed quality.

```
/generate-docs feed-audit
```

**Output**:
```markdown
# Feed Audit Report
**Total Products**: [X]
**Audit Date**: [Timestamp]

## Overall Feed Health

### Quality Score Distribution
| Score Range | Products | % of Catalog |
|-------------|----------|--------------|
| 90-100% | 45 | 15% |
| 80-89% | 89 | 30% |
| 70-79% | 67 | 22% |
| Below 70% | 99 | 33% |

### Attribute Completeness
| Attribute | Filled % | Recommendation |
|-----------|----------|----------------|
| Title | 100% | ✅ Complete |
| Description | 85% | ⚠️ Fill 45 missing |
| Material | 60% | ❌ High priority |
| Dimensions | 78% | ⚠️ Medium priority |

### Critical Issues
1. **[X] products with generic titles** - Missing brand/dimensions
2. **[Y] products with short descriptions** - Below 500 chars
3. **[Z] products missing functional modifiers**

## Recommendations
1. [Priority 1 action]
2. [Priority 2 action]
3. [Priority 3 action]
```

### 3. Style Guide Export
Export brand voice and content guidelines.

```
/generate-docs style-guide
```

**Output**:
```markdown
# Allied Brass Feed Content Style Guide

## Brand Voice
- Confident, not boastful
- Specific, not vague
- Premium, understated elegance

## Title Structure
[Format]: [Brand] + [Product Type] + [Dimension] + [Material] + [Finish]
[Example]: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome

## Description Structure
1. Opening hook (benefit + key spec)
2. Bullet highlights (3-5)
3. Specifications
4. Trust elements (warranty, installation)

## Approved Terminology
| Use | Avoid |
|-----|-------|
| Crafted | Made |
| Solid brass | Premium material |
| Enduring | Long-lasting |
| Engineered | Designed |

## Character Guidelines
- Title: 70-150 characters
- Description: 500+ characters
- First 150 chars: Must contain value proposition
```

### 4. Training Data Export
Export optimized content pairs for model fine-tuning.

```
/generate-docs training-data --format=jsonl
```

**Output** (JSONL format):
```jsonl
{"input": {"sku": "AB-123", "raw_title": "Towel Bar 24", "attributes": {...}}, "output": {"optimized_title": "Allied Brass 24-Inch Towel Bar | Solid Brass | Chrome", "optimized_description": "..."}}
{"input": {"sku": "AB-456", "raw_title": "Grab Bar", "attributes": {...}}, "output": {"optimized_title": "ADA Grab Bar 18-Inch | 500lb Capacity | Solid Brass", "optimized_description": "..."}}
```

### 5. Platform Feed Export
Export optimized content in platform-specific formats.

```
/generate-docs feed-export --platform=google
```

**Formats**:
- `--platform=google` - Google Merchant Center format
- `--platform=bing` - Microsoft Merchant Center format
- `--platform=shopify` - Shopify CSV import format

**Output** (Google format):
```csv
id,title,description,link,image_link,price,brand,product_type
AB-123,"Allied Brass 24-Inch Towel Bar | Solid Brass | Chrome","Crafted from solid brass...","https://...","https://...","89.99","Allied Brass","Bathroom > Towel Bars"
```

### 6. Compliance Report
Check content against platform policies.

```
/generate-docs compliance-report
```

**Output**:
```markdown
# Platform Compliance Report
**Checked**: [X] products
**Date**: [Timestamp]

## Google Merchant Center

### Passing
- ✅ [X] products fully compliant

### Issues Found
| Issue Type | Count | Examples |
|------------|-------|----------|
| Title too long | 3 | SKU-123, SKU-456 |
| Promotional text | 1 | SKU-789 |
| Missing required attribute | 5 | [list] |

### Recommended Fixes
1. [Fix 1]
2. [Fix 2]

## Microsoft Merchant Center

### Passing
- ✅ [X] products fully compliant

### Issues Found
| Issue Type | Count | Examples |
|------------|-------|----------|
| Missing brand in title | 8 | [list] |
```

## Options

| Option | Description |
|--------|-------------|
| `--period` | Time period for reports (e.g., last-30-days, 2024-Q1) |
| `--format` | Output format (md, json, csv, pdf) |
| `--platform` | Target platform for exports |
| `--category` | Filter by product category |
| `--score-threshold` | Filter by quality score |
| `--output` | Output file path |

## Examples

```bash
# Generate audit for grab bars category
/generate-docs feed-audit --category="Grab Bars"

# Export training data in JSON format
/generate-docs training-data --format=json --output=training.json

# Generate compliance report for products below 80% score
/generate-docs compliance-report --score-threshold=80

# Create feed export for Google with specific products
/generate-docs feed-export --platform=google --category="Towel Bars"
```

## Automation

### Scheduled Reports
Configure automatic report generation:

```yaml
# .cursor/schedules/reports.yml
reports:
  - type: optimization-report
    schedule: "0 9 * * 1"  # Every Monday 9am
    format: pdf
    recipients: [team@example.com]
    
  - type: feed-audit
    schedule: "0 6 1 * *"  # First of month
    format: md
    output: ./reports/monthly-audit.md
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Generate Feed Audit
  run: /generate-docs feed-audit --format=json --output=audit.json

- name: Check Compliance
  run: |
    /generate-docs compliance-report --format=json
    # Fail if compliance issues found
```
