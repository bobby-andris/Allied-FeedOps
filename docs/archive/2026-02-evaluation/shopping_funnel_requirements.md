# Shopping Funnel Search Terms Management - Requirements Document

**Project:** Add Shopping Campaign Search Terms Management to FeedOps Dashboard  
**Developer:** Bobby  
**Implementation Tool:** Claude Code  
**Date:** February 19, 2026  
**Version:** 1.0

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Context](#system-context)
3. [Feature Scope](#feature-scope)
4. [Data Sources & Integration](#data-sources--integration)
5. [Classification Logic](#classification-logic)
6. [User Interface Specifications](#user-interface-specifications)
7. [Action Processing & Google Ads API Posting](#action-processing--google-ads-api-posting)
8. [Database Schema](#database-schema)
9. [API Endpoints](#api-endpoints)
10. [Error Handling](#error-handling)
11. [Testing Checklist](#testing-checklist)
12. [Phase 2 Considerations](#phase-2-considerations)

---

## 1. Project Overview

### Purpose
Add a Shopping Campaign search terms management module to the existing FeedOps dashboard. This module will help manage 189 Shopping campaigns across 63 custom_label_0 product categories by:
- Identifying search terms that need decisions
- Managing a 3-tier funnel structure (HIGH/MEDIUM/LOW intent levels)
- Automating posting of negative keywords to Google Ads via API

### Current Business Context
- 77,000 SKU ecommerce business (bathroom hardware)
- 189 Shopping campaigns organized by custom_label_0 categories
- 3-tier funnel structure per category (HIGH, MEDIUM, LOW intent)
- 3 shared negative keyword lists for brand/competitor/spam terms
- Monthly revenue ~$160K, scaling to $300K

### Key Principle
**Shopping campaigns only use NEGATIVE keywords** (no positive keywords). The funnel works by blocking search terms in 2 tiers, which drives traffic to the 3rd unblocked tier.

---

## 2. System Context

### Existing Infrastructure
- **Frontend:** Next.js on Vercel
- **Backend:** Vercel Serverless Functions
- **Database:** Supabase (PostgreSQL)
- **Authentication:** Supabase Auth
- **Current App:** FeedOps feed optimizer for Google Merchant Center

### New Integration Points
- **Google Ads API:** Read search terms, write negative keywords
- **Google Ads Customer ID:** Use Bobby's credentials (same as used in Python scripts)
- **Shared Lists:**
  - "AVD - Global Block"
  - "AVD - Competitor Terms"
  - "AVD - BRANDED_SEARCH_TERMS - US"

### Navigation Addition
Add new section to existing FeedOps navigation:
- Current: Overview, Generate, Review Queue, Competitors, Batches, Performance, Search Insights, Backlist Monitoring, Settings
- **Add:** "Shopping Funnel" (or "Search Terms Management")

---

## 3. Feature Scope

### Phase 1 (This Project)
✅ Shopping campaigns only  
✅ Two workflows:
   1. **Needs Decision** - Unprocessed search terms
   2. **Existing Funnel** - Already decisioned terms with editing capability
✅ Classification logic matching existing Python script  
✅ Google Ads API integration for reading and writing  
✅ Exact match keywords only  

### Explicitly Out of Scope (Phase 2)
❌ Performance Max (PMax) campaigns  
❌ Search campaigns  
❌ Broad/Phrase match types  
❌ Action history/audit logging  
❌ Export to CSV  
❌ Saved filter presets  
❌ Performance-based priority scoring  

---

## 4. Data Sources & Integration

### Google Ads API - Data to Fetch

#### Search Terms (30-day default, configurable date range)
```
Query: search_term_view
Filters: 
  - campaign.advertising_channel_type = SHOPPING
  - segments.date >= {start_date}
  - segments.date <= {end_date}
  - campaign.status = ENABLED
  
Fields to retrieve:
  - search_term_view.search_term
  - campaign.name
  - ad_group.name
  - metrics.impressions
  - metrics.clicks
  - metrics.cost_micros
  - metrics.conversions
  - metrics.conversions_value
```

#### Negative Keywords - Campaign Level
```
Query: campaign_criterion
Filters:
  - campaign_criterion.type = KEYWORD
  - campaign_criterion.negative = TRUE
  - campaign.advertising_channel_type = SHOPPING
  - campaign.status = ENABLED
  
Fields:
  - campaign.name
  - campaign_criterion.keyword.text
  - campaign_criterion.keyword.match_type
```

#### Negative Keywords - Ad Group Level
```
Query: ad_group_criterion
Filters:
  - ad_group_criterion.type = KEYWORD
  - ad_group_criterion.negative = TRUE
  - campaign.advertising_channel_type = SHOPPING
  - campaign.status = ENABLED
  - ad_group.status = ENABLED
  
Fields:
  - campaign.name
  - ad_group.name
  - ad_group_criterion.keyword.text
  - ad_group_criterion.keyword.match_type
```

#### Shared Negative Keyword Lists
```
Query: shared_criterion
Filters:
  - shared_set.type = NEGATIVE_KEYWORDS
  - shared_set.name IN [
      "AVD - Global Block",
      "AVD - Competitor Terms", 
      "AVD - BRANDED_SEARCH_TERMS - US"
    ]
  
Fields:
  - shared_set.name
  - shared_criterion.keyword.text
  - shared_criterion.keyword.match_type
```

### Campaign Naming Convention
**Format:** `AVD - Shopping - US - {custom_label_0} - {TIER}`

**Examples:**
- `AVD - Shopping - US - Cabinet Hardware - HIGH`
- `AVD - Shopping - US - Cabinet Hardware - MEDIUM`
- `AVD - Shopping - US - Cabinet Hardware - LOW`

**Parsing Logic:**
```javascript
function parseCustomLabel0(campaignName) {
  // Extract custom_label_0 from campaign name
  const pattern = /AVD - Shopping - US - (.+?) - (HIGH|MEDIUM|LOW)/;
  const match = campaignName.match(pattern);
  if (!match) return { customLabel0: null, tier: null };
  return {
    customLabel0: match[1].trim(),
    tier: match[2]
  };
}
```

### Ad Group Naming Convention
**Format:** Ad group name matches campaign name exactly

**Example:**
- Campaign: `AVD - Shopping - US - Cabinet Hardware - LOW`
- Ad Group: `AVD - Shopping - US - Cabinet Hardware - LOW`

---

## 5. Classification Logic

### "Needs Decision" Definition
A search term needs a decision if:
1. **NOT in any of the 3 shared negative keyword lists**, AND
2. **The (search_term + custom_label_0) combo does not exist in that custom_label_0's funnel**

### "Exists in Funnel" Definition
A search term exists in a custom_label_0 funnel if it appears as a negative keyword in:
- **Campaign-level negatives:** In any of the 3 tier campaigns (HIGH/MEDIUM/LOW) for that custom_label_0
- **OR Ad group-level negatives:** In any of the 3 tier campaigns for that custom_label_0

### Classification Algorithm

```javascript
function classifySearchTerm(searchTerm, campaignName, sharedLists, campaignNegatives, adGroupNegatives) {
  const { customLabel0, tier } = parseCustomLabel0(campaignName);
  
  // Normalize search term (lowercase, trim, collapse whitespace)
  const normalizedTerm = searchTerm.toLowerCase().trim().replace(/\s+/g, ' ');
  
  // Check shared negative lists
  const sharedListNames = [
    "AVD - Global Block",
    "AVD - Competitor Terms",
    "AVD - BRANDED_SEARCH_TERMS - US"
  ];
  
  for (const listName of sharedListNames) {
    if (sharedLists[listName]?.has(normalizedTerm)) {
      return {
        status: "Decisioned",
        reason: `Found in shared list: ${listName}`,
        location: listName
      };
    }
  }
  
  // Check if exists in this custom_label_0's funnel (any tier)
  const tiers = ['HIGH', 'MEDIUM', 'LOW'];
  const funnelCampaigns = tiers.map(t => 
    `AVD - Shopping - US - ${customLabel0} - ${t}`
  );
  
  // Check campaign-level negatives
  for (const campaign of funnelCampaigns) {
    if (campaignNegatives[campaign]?.has(normalizedTerm)) {
      return {
        status: "Decisioned",
        reason: `Campaign-level negative in ${customLabel0} funnel`,
        location: campaign,
        tier: "Campaign Negative"
      };
    }
  }
  
  // Check ad group-level negatives
  for (const campaign of funnelCampaigns) {
    const adGroupName = campaign; // Ad group name = campaign name
    const key = `${campaign}|${adGroupName}`;
    if (adGroupNegatives[key]?.has(normalizedTerm)) {
      return {
        status: "Decisioned",
        reason: `Ad group-level negative in ${customLabel0} funnel`,
        location: campaign,
        tier: inferTierFromAdGroupNegatives(campaign, normalizedTerm, adGroupNegatives)
      };
    }
  }
  
  // If not found anywhere, needs decision
  return {
    status: "Needs Decision",
    reason: "Not found in shared lists or funnel",
    customLabel0: customLabel0,
    sourceTier: tier
  };
}

function inferTierFromAdGroupNegatives(customLabel0, searchTerm, adGroupNegatives) {
  const tiers = ['HIGH', 'MEDIUM', 'LOW'];
  const campaigns = tiers.map(t => `AVD - Shopping - US - ${customLabel0} - ${t}`);
  
  const foundIn = campaigns.filter(c => {
    const key = `${c}|${c}`; // ad group name = campaign name
    return adGroupNegatives[key]?.has(searchTerm);
  });
  
  // If in MEDIUM and LOW → term is targeted in HIGH
  if (foundIn.includes('MEDIUM') && foundIn.includes('LOW') && !foundIn.includes('HIGH')) {
    return 'HIGH';
  }
  // If in HIGH and LOW → term is targeted in MEDIUM
  if (foundIn.includes('HIGH') && foundIn.includes('LOW') && !foundIn.includes('MEDIUM')) {
    return 'MEDIUM';
  }
  // If in HIGH and MEDIUM → term is targeted in LOW
  if (foundIn.includes('HIGH') && foundIn.includes('MEDIUM') && !foundIn.includes('LOW')) {
    return 'LOW';
  }
  // If in all 3 or only 1 → ERROR
  return 'ERROR';
}
```

---

## 6. User Interface Specifications

### 6.1 Navigation Structure

Add to sidebar:
```
Shopping Funnel
  ├─ Needs Decision
  └─ Existing Funnel
```

### 6.2 Needs Decision View

#### Header Section
```
┌─────────────────────────────────────────────────────────────────┐
│ Shopping Funnel - Needs Decision                                │
│                                                                 │
│ Date Range: [Last 30 days ▼]  [Refresh Data]                  │
│                                                                 │
│ 127 search terms need decisions                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Filters (Optional - Nice to Have)
```
┌─────────────────────────────────────────────────────────────────┐
│ Filters:                                                         │
│ Custom Label 0: [All ▼]  Campaign: [All ▼]  Min Impressions: [__] │
└─────────────────────────────────────────────────────────────────┘
```

#### Search Term List
**Important:** Do NOT show performance metrics (impressions, clicks, cost) in Needs Decision view

```
┌─────────────────────────────────────────────────────────────────┐
│ ☐ chrome towel bar                                              │
│    ○ Global Block  ○ Competitor Term  ○ Branded Term  ● Funnel Term │
│                                                                 │
│    Wall Mounted Towel Bars (from HIGH):                         │
│       ○ Campaign Negative  ● High  ○ Medium  ○ Low             │
│                                                                 │
│    Shower Door Towel Bars (from MEDIUM):                        │
│       ○ Campaign Negative  ○ High  ● Medium  ○ Low             │
│                                                                 │
│ ─────────────────────────────────────────────────────────────  │
│                                                                 │
│ ☐ black soap dispenser                                          │
│    ○ Global Block  ○ Competitor Term  ○ Branded Term  ● Funnel Term │
│                                                                 │
│    Soap Dispensers (from HIGH):                                 │
│       ○ Campaign Negative  ○ High  ○ Medium  ● Low             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

[Select All] [Deselect All]           [Save Decisions] [Post to Google Ads]
```

#### UI Behavior Rules

1. **Main Checkbox:** Selects/deselects the entire search term

2. **Action Radio Buttons (Top Level):**
   - `Global Block` - Add to "AVD - Global Block" shared list
   - `Competitor Term` - Add to "AVD - Competitor Terms" shared list
   - `Branded Term` - Add to "AVD - BRANDED_SEARCH_TERMS - US" shared list
   - `Funnel Term` - Show custom_label_0 rows below

3. **Custom Label 0 Rows:**
   - Only visible if "Funnel Term" is selected
   - One row per custom_label_0 where search term got impressions
   - Show source tier in parentheses: "(from HIGH)" indicates the term got impressions from the HIGH tier campaign
   - **Default selection:** Default to the same tier as source (e.g., if from HIGH, default to HIGH radio button)
   - **User can change:** Radio buttons are changeable - user will frequently select different tier than default

4. **Tier Radio Buttons (per custom_label_0):**
   - `Campaign Negative` - Block at all 3 tiers (campaign level)
   - `High` - Block at MEDIUM and LOW (ad group level)
   - `Medium` - Block at HIGH and LOW (ad group level)
   - `Low` - Block at HIGH and MEDIUM (ad group level)

5. **Buttons:**
   - `Save Decisions` - Save selections to Supabase (optional staging)
   - `Post to Google Ads` - Process selected terms and post via API

### 6.3 Existing Funnel View

#### Header Section
```
┌─────────────────────────────────────────────────────────────────┐
│ Shopping Funnel - Existing Funnel                               │
│                                                                 │
│ Date Range: [Last 30 days ▼]  [Refresh Data]                  │
│                                                                 │
│ 1,847 search terms in funnel                                    │
└─────────────────────────────────────────────────────────────────┘
```

#### Filters
```
┌─────────────────────────────────────────────────────────────────┐
│ Filters:                                                         │
│ Custom Label 0: [All ▼]  Tier: [All ▼]  Show Errors Only: [☐]  │
└─────────────────────────────────────────────────────────────────┘
```

#### Search Term List
**Important:** DO show performance metrics in Existing Funnel view

```
┌─────────────────────────────────────────────────────────────────┐
│ chrome towel bar                                                │
│ 📊 342 impressions | 28 clicks | $56.40 cost | 3 conversions   │
│                                                                 │
│    Wall Mounted Towel Bars:  [High ▼]                          │
│    Shower Door Towel Bars:   [Medium ▼]                        │
│    Single Glass Shelf:       [Campaign Negative ▼]             │
│                                                                 │
│    [○ Keep in Funnel] [○ Move to Global Block] [○ Move to Competitor] [○ Move to Branded] │
│                                                                 │
│ ─────────────────────────────────────────────────────────────  │
│                                                                 │
│ ⚠️ black soap dispenser                                          │
│ 📊 89 impressions | 7 clicks | $14.20 cost | 0 conversions     │
│                                                                 │
│    ⚠️ Soap Dispensers:  [ERROR - in all 3 tiers] [Fix ▼]      │
│                                                                 │
│    [○ Keep in Funnel] [○ Move to Global Block] [○ Move to Competitor] [○ Move to Branded] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

[Save Changes] [Post to Google Ads]
```

#### Error Detection Rules

A custom_label_0 funnel entry has an ERROR if:

1. **Blocked at all 3 tiers (ad group level):**
   - Search term exists as ad group negative in HIGH AND MEDIUM AND LOW
   - Result: Term is completely blocked, gets no traffic
   - **Display:** `⚠️ ERROR - Blocked in all 3 tiers`

2. **Blocked at only 1 tier (ad group level):**
   - Search term exists as ad group negative in only HIGH (or only MEDIUM, or only LOW)
   - Result: Term should be in exactly 2 tiers (to target the 3rd)
   - **Display:** `⚠️ ERROR - Only blocked in 1 tier`

3. **Campaign negative in only 1 or 2 tiers:**
   - Search term exists as campaign-level negative in only HIGH, or only MEDIUM, or only LOW
   - Or in only 2 out of 3 tiers
   - Result: Campaign negatives should be in all 3 tiers or none
   - **Display:** `⚠️ ERROR - Campaign negative incomplete`

#### Tier Display Logic

For each custom_label_0 where the search term exists, determine tier by checking:

```javascript
function determineTier(customLabel0, searchTerm, campaignNegatives, adGroupNegatives) {
  const campaigns = {
    high: `AVD - Shopping - US - ${customLabel0} - HIGH`,
    medium: `AVD - Shopping - US - ${customLabel0} - MEDIUM`,
    low: `AVD - Shopping - US - ${customLabel0} - LOW`
  };
  
  // Check campaign-level negatives
  const campaignNegCount = [
    campaignNegatives[campaigns.high]?.has(searchTerm),
    campaignNegatives[campaigns.medium]?.has(searchTerm),
    campaignNegatives[campaigns.low]?.has(searchTerm)
  ].filter(Boolean).length;
  
  if (campaignNegCount === 3) return { tier: 'Campaign Negative', error: false };
  if (campaignNegCount > 0 && campaignNegCount < 3) {
    return { tier: 'Campaign Negative', error: true, errorMsg: 'Campaign negative incomplete' };
  }
  
  // Check ad group-level negatives
  const inHigh = adGroupNegatives[`${campaigns.high}|${campaigns.high}`]?.has(searchTerm);
  const inMedium = adGroupNegatives[`${campaigns.medium}|${campaigns.medium}`]?.has(searchTerm);
  const inLow = adGroupNegatives[`${campaigns.low}|${campaigns.low}`]?.has(searchTerm);
  
  // Check for errors
  if (inHigh && inMedium && inLow) {
    return { tier: 'Unknown', error: true, errorMsg: 'Blocked in all 3 tiers' };
  }
  
  const adGroupCount = [inHigh, inMedium, inLow].filter(Boolean).length;
  if (adGroupCount === 1) {
    return { tier: 'Unknown', error: true, errorMsg: 'Only blocked in 1 tier' };
  }
  
  // Determine tier (blocked in 2, targeted in 3rd)
  if (inMedium && inLow && !inHigh) return { tier: 'High', error: false };
  if (inHigh && inLow && !inMedium) return { tier: 'Medium', error: false };
  if (inHigh && inMedium && !inLow) return { tier: 'Low', error: false };
  
  return { tier: 'Unknown', error: true, errorMsg: 'Invalid configuration' };
}
```

#### Editing in Existing Funnel

**User can change:**
1. **Tier within funnel:** Change from High → Medium, Medium → Low, etc.
2. **Move to shared list:** Move from funnel to Global Block / Competitor / Branded
3. **Campaign Negative ↔ Tiered:** Change between Campaign Negative and specific tier

**Posting Rules:**
- Use same rules as "Needs Decision" posting (see Section 7)
- If moving tier (e.g., High → Medium), must first REMOVE from old tier before adding to new tier

---

## 7. Action Processing & Google Ads API Posting

### 7.1 Posting Rules - Needs Decision

When user clicks "Post to Google Ads", process each selected search term:

#### Rule 1: Global Block
```
Action: Global Block
API Call: Add to shared negative keyword list "AVD - Global Block"
Match Type: EXACT
```

#### Rule 2: Competitor Term
```
Action: Competitor Term
API Call: Add to shared negative keyword list "AVD - Competitor Terms"
Match Type: EXACT
```

#### Rule 3: Branded Term
```
Action: Branded Term
API Call: Add to shared negative keyword list "AVD - BRANDED_SEARCH_TERMS - US"
Match Type: EXACT
```

#### Rule 4: Funnel Term - Campaign Negative
```
Action: Funnel Term → Campaign Negative
For each custom_label_0 selected:
  Target campaigns:
    - AVD - Shopping - US - {custom_label_0} - HIGH
    - AVD - Shopping - US - {custom_label_0} - MEDIUM
    - AVD - Shopping - US - {custom_label_0} - LOW
  
  API Call: Add campaign_criterion (negative keyword) to all 3 campaigns
  Match Type: EXACT
```

#### Rule 5: Funnel Term - High Tier
```
Action: Funnel Term → High
For the selected custom_label_0:
  
  Step 1: Check if term exists in HIGH tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - HIGH
    Ad Group: AVD - Shopping - US - {custom_label_0} - HIGH
    If EXISTS: Remove from HIGH ad group negatives
  
  Step 2: Add to MEDIUM tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - MEDIUM
    Ad Group: AVD - Shopping - US - {custom_label_0} - MEDIUM
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT
  
  Step 3: Add to LOW tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - LOW
    Ad Group: AVD - Shopping - US - {custom_label_0} - LOW
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT

Goal: Term is blocked in MEDIUM and LOW, so traffic flows to HIGH
```

#### Rule 6: Funnel Term - Medium Tier
```
Action: Funnel Term → Medium
For the selected custom_label_0:
  
  Step 1: Check if term exists in MEDIUM tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - MEDIUM
    Ad Group: AVD - Shopping - US - {custom_label_0} - MEDIUM
    If EXISTS: Remove from MEDIUM ad group negatives
  
  Step 2: Add to HIGH tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - HIGH
    Ad Group: AVD - Shopping - US - {custom_label_0} - HIGH
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT
  
  Step 3: Add to LOW tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - LOW
    Ad Group: AVD - Shopping - US - {custom_label_0} - LOW
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT

Goal: Term is blocked in HIGH and LOW, so traffic flows to MEDIUM
```

#### Rule 7: Funnel Term - Low Tier
```
Action: Funnel Term → Low
For the selected custom_label_0:
  
  Step 1: Check if term exists in LOW tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - LOW
    Ad Group: AVD - Shopping - US - {custom_label_0} - LOW
    If EXISTS: Remove from LOW ad group negatives
  
  Step 2: Add to HIGH tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - HIGH
    Ad Group: AVD - Shopping - US - {custom_label_0} - HIGH
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT
  
  Step 3: Add to MEDIUM tier ad group negatives
    Campaign: AVD - Shopping - US - {custom_label_0} - MEDIUM
    Ad Group: AVD - Shopping - US - {custom_label_0} - MEDIUM
    API Call: Add ad_group_criterion (negative keyword)
    Match Type: EXACT

Goal: Term is blocked in HIGH and MEDIUM, so traffic flows to LOW
```

### 7.2 Posting Rules - Existing Funnel Edits

#### Moving Between Tiers
When changing tier assignment (e.g., High → Medium):

```
Step 1: Remove from old tier configuration
  If was HIGH: Remove from MEDIUM and LOW ad group negatives
  If was MEDIUM: Remove from HIGH and LOW ad group negatives
  If was LOW: Remove from HIGH and MEDIUM ad group negatives

Step 2: Apply new tier configuration (use Rules 5-7 from above)
```

#### Moving to Shared List
When moving from funnel to shared list (e.g., High → Global Block):

```
Step 1: Remove from all funnel locations for that custom_label_0
  - Remove from all campaign-level negatives (HIGH, MEDIUM, LOW)
  - Remove from all ad group-level negatives (HIGH, MEDIUM, LOW)

Step 2: Add to shared list (use Rules 1-3 from above)
```

#### Fixing Campaign Negative
When converting Campaign Negative → Tiered:

```
Step 1: Remove from all 3 campaign-level negatives
  Campaigns:
    - AVD - Shopping - US - {custom_label_0} - HIGH
    - AVD - Shopping - US - {custom_label_0} - MEDIUM
    - AVD - Shopping - US - {custom_label_0} - LOW

Step 2: Apply tier configuration (use Rules 5-7 from above)
```

### 7.3 Google Ads API Implementation

#### Required API Resources

1. **SharedCriterionService** (for shared negative lists)
   ```
   Operation: CREATE
   Resource: shared_criterion
   Fields:
     - shared_set: "customers/{customer_id}/sharedSets/{shared_set_id}"
     - keyword.text: "{search_term}"
     - keyword.match_type: EXACT
     - negative: true
   ```

2. **CampaignCriterionService** (for campaign-level negatives)
   ```
   Operation: CREATE / REMOVE
   Resource: campaign_criterion
   Fields:
     - campaign: "customers/{customer_id}/campaigns/{campaign_id}"
     - keyword.text: "{search_term}"
     - keyword.match_type: EXACT
     - negative: true
   ```

3. **AdGroupCriterionService** (for ad group-level negatives)
   ```
   Operation: CREATE / REMOVE
   Resource: ad_group_criterion
   Fields:
     - ad_group: "customers/{customer_id}/adGroups/{ad_group_id}"
     - keyword.text: "{search_term}"
     - keyword.match_type: EXACT
     - negative: true
   ```

#### Campaign & Ad Group ID Resolution

Since we have campaign/ad group names but need IDs for API calls:

```javascript
// Cache campaign and ad group IDs on initial data fetch
async function fetchCampaignAndAdGroupIds(client, customerId) {
  const query = `
    SELECT 
      campaign.id,
      campaign.name,
      ad_group.id,
      ad_group.name
    FROM ad_group
    WHERE campaign.advertising_channel_type = SHOPPING
      AND campaign.status = ENABLED
      AND ad_group.status = ENABLED
  `;
  
  const results = await client.searchStream({ customerId, query });
  
  const campaignMap = new Map(); // campaign_name → campaign_id
  const adGroupMap = new Map();  // "campaign_name|ad_group_name" → ad_group_id
  
  for await (const row of results) {
    campaignMap.set(row.campaign.name, row.campaign.id);
    adGroupMap.set(`${row.campaign.name}|${row.adGroup.name}`, row.adGroup.id);
  }
  
  return { campaignMap, adGroupMap };
}
```

#### Shared Set ID Resolution

```javascript
// Fetch shared set IDs for the 3 negative lists
async function fetchSharedSetIds(client, customerId) {
  const query = `
    SELECT 
      shared_set.id,
      shared_set.name
    FROM shared_set
    WHERE shared_set.type = NEGATIVE_KEYWORDS
      AND shared_set.status = ENABLED
  `;
  
  const results = await client.searchStream({ customerId, query });
  
  const sharedSetMap = new Map(); // list_name → shared_set_id
  
  for await (const row of results) {
    sharedSetMap.set(row.sharedSet.name, row.sharedSet.id);
  }
  
  return sharedSetMap;
}
```

---

## 8. Database Schema

### 8.1 Optional Staging Table (if implementing Save Decisions button)

```sql
CREATE TABLE search_term_decisions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  search_term TEXT NOT NULL,
  action_type TEXT NOT NULL, -- 'global_block', 'competitor', 'branded', 'funnel'
  custom_label_0 TEXT, -- NULL if action_type is shared list
  tier TEXT, -- 'campaign_negative', 'high', 'medium', 'low', NULL if action_type is shared list
  source_campaign TEXT,
  source_tier TEXT,
  impressions INTEGER,
  clicks INTEGER,
  cost_micros BIGINT,
  conversions DECIMAL(10,2),
  conversions_value DECIMAL(10,2),
  posted_to_google_ads BOOLEAN DEFAULT FALSE,
  posted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by TEXT -- user email/id
);

CREATE INDEX idx_search_term_decisions_posted ON search_term_decisions(posted_to_google_ads);
CREATE INDEX idx_search_term_decisions_created_at ON search_term_decisions(created_at);
```

### 8.2 Error Log Table (for API failures)

```sql
CREATE TABLE google_ads_api_errors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  search_term TEXT NOT NULL,
  action_attempted TEXT NOT NULL,
  error_message TEXT,
  error_code TEXT,
  campaign_name TEXT,
  ad_group_name TEXT,
  retry_count INTEGER DEFAULT 0,
  resolved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_google_ads_api_errors_resolved ON google_ads_api_errors(resolved);
```

---

## 9. API Endpoints

### Backend API Routes (Serverless Functions)

#### 9.1 GET /api/search-terms/needs-decision
```
Query Parameters:
  - start_date: YYYY-MM-DD (default: 30 days ago)
  - end_date: YYYY-MM-DD (default: yesterday)
  - custom_label_0: string (optional filter)
  - min_impressions: integer (optional filter)

Response:
{
  "terms": [
    {
      "search_term": "chrome towel bar",
      "custom_label_0s": [
        {
          "custom_label_0": "Wall Mounted Towel Bars",
          "source_campaign": "AVD - Shopping - US - Wall Mounted Towel Bars - HIGH",
          "source_tier": "HIGH",
          "impressions": 45,
          "clicks": 3,
          "cost_micros": 8500000,
          "conversions": 0,
          "conversions_value": 0
        },
        {
          "custom_label_0": "Shower Door Towel Bars",
          "source_campaign": "AVD - Shopping - US - Shower Door Towel Bars - MEDIUM",
          "source_tier": "MEDIUM",
          "impressions": 12,
          "clicks": 1,
          "cost_micros": 2300000,
          "conversions": 0,
          "conversions_value": 0
        }
      ]
    }
  ],
  "total_count": 127
}
```

#### 9.2 GET /api/search-terms/existing-funnel
```
Query Parameters:
  - start_date: YYYY-MM-DD (default: 30 days ago)
  - end_date: YYYY-MM-DD (default: yesterday)
  - custom_label_0: string (optional filter)
  - tier: string (optional filter: 'high', 'medium', 'low', 'campaign_negative')
  - show_errors_only: boolean (optional)

Response:
{
  "terms": [
    {
      "search_term": "chrome towel bar",
      "total_impressions": 342,
      "total_clicks": 28,
      "total_cost_micros": 56400000,
      "total_conversions": 3,
      "total_conversions_value": 89.50,
      "funnels": [
        {
          "custom_label_0": "Wall Mounted Towel Bars",
          "tier": "High",
          "error": false,
          "error_message": null
        },
        {
          "custom_label_0": "Shower Door Towel Bars",
          "tier": "Medium",
          "error": false,
          "error_message": null
        },
        {
          "custom_label_0": "Single Glass Shelf",
          "tier": "Campaign Negative",
          "error": false,
          "error_message": null
        }
      ]
    },
    {
      "search_term": "black soap dispenser",
      "total_impressions": 89,
      "total_clicks": 7,
      "total_cost_micros": 14200000,
      "total_conversions": 0,
      "total_conversions_value": 0,
      "funnels": [
        {
          "custom_label_0": "Soap Dispensers",
          "tier": "Unknown",
          "error": true,
          "error_message": "Blocked in all 3 tiers"
        }
      ]
    }
  ],
  "total_count": 1847,
  "error_count": 23
}
```

#### 9.3 POST /api/search-terms/post-decisions
```
Request Body:
{
  "decisions": [
    {
      "search_term": "chrome towel bar",
      "action_type": "funnel",
      "assignments": [
        {
          "custom_label_0": "Wall Mounted Towel Bars",
          "tier": "high"
        },
        {
          "custom_label_0": "Shower Door Towel Bars",
          "tier": "medium"
        }
      ]
    },
    {
      "search_term": "spam keyword",
      "action_type": "global_block"
    }
  ]
}

Response:
{
  "results": [
    {
      "search_term": "chrome towel bar",
      "status": "success",
      "actions_completed": [
        "Added to MEDIUM ad group negatives for Wall Mounted Towel Bars",
        "Added to LOW ad group negatives for Wall Mounted Towel Bars",
        "Added to HIGH ad group negatives for Shower Door Towel Bars",
        "Added to LOW ad group negatives for Shower Door Towel Bars"
      ]
    },
    {
      "search_term": "spam keyword",
      "status": "success",
      "actions_completed": [
        "Added to AVD - Global Block shared list"
      ]
    }
  ],
  "success_count": 2,
  "error_count": 0
}
```

#### 9.4 POST /api/search-terms/update-existing
```
Request Body:
{
  "updates": [
    {
      "search_term": "chrome towel bar",
      "custom_label_0": "Wall Mounted Towel Bars",
      "old_tier": "high",
      "new_tier": "medium"
    },
    {
      "search_term": "spam keyword",
      "custom_label_0": "Soap Dispensers",
      "old_tier": "low",
      "new_action": "global_block"
    }
  ]
}

Response:
{
  "results": [
    {
      "search_term": "chrome towel bar",
      "custom_label_0": "Wall Mounted Towel Bars",
      "status": "success",
      "actions_completed": [
        "Removed from MEDIUM ad group negatives",
        "Removed from LOW ad group negatives",
        "Added to HIGH ad group negatives",
        "Added to LOW ad group negatives"
      ]
    }
  ],
  "success_count": 1,
  "error_count": 0
}
```

#### 9.5 GET /api/campaigns/list
```
Response:
{
  "campaigns": [
    {
      "id": "1234567890",
      "name": "AVD - Shopping - US - Cabinet Hardware - HIGH",
      "custom_label_0": "Cabinet Hardware",
      "tier": "HIGH",
      "status": "ENABLED"
    }
  ]
}
```

#### 9.6 GET /api/custom-labels/list
```
Response:
{
  "custom_labels": [
    "2 Post TP Holder",
    "4 Tier Glass Wall Shelf",
    "Assorted Freestanding Accessories",
    // ... all 63 categories
  ]
}
```

---

## 10. Error Handling

### 10.1 Google Ads API Errors

#### Rate Limiting
```
If API returns RATE_EXCEEDED error:
  - Wait 60 seconds
  - Retry request
  - Max 3 retries per request
  - If still failing, log error and show user
```

#### Network Errors
```
If API call fails due to network:
  - Retry immediately (1 retry)
  - If fails again, show error to user
  - Allow user to manually retry
```

#### Invalid Resource Errors
```
If campaign/ad group not found:
  - Log error with details
  - Show user: "Campaign '{name}' not found. Data may be out of sync."
  - Provide "Refresh Data" button
```

### 10.2 User Feedback

#### During Posting
```
Show progress indicator:
"Posting 15 search terms to Google Ads..."
"✓ Posted 5 of 15..."
"✓ Posted 10 of 15..."
"✓ Completed! 14 successful, 1 error"
```

#### Success Messages
```
Toast notification:
"✓ Successfully posted 14 search terms to Google Ads"
```

#### Error Messages
```
Toast notification:
"⚠️ 1 search term failed to post. Check error log for details."

Error detail view:
Search Term: "chrome towel bar"
Campaign: "AVD - Shopping - US - Wall Mounted Towel Bars - HIGH"
Error: "RATE_EXCEEDED - API rate limit reached"
Retry Count: 3/3
Status: Failed
[Retry Now] button
```

### 10.3 Automatic Retry Logic

```javascript
async function postToGoogleAds(decision, retryCount = 0) {
  const MAX_RETRIES = 3;
  
  try {
    const result = await googleAdsClient.post(decision);
    return { success: true, result };
  } catch (error) {
    if (error.code === 'RATE_EXCEEDED' && retryCount < MAX_RETRIES) {
      await sleep(60000); // Wait 60 seconds
      return postToGoogleAds(decision, retryCount + 1);
    }
    
    if (error.code === 'NETWORK_ERROR' && retryCount < 1) {
      await sleep(1000); // Wait 1 second
      return postToGoogleAds(decision, retryCount + 1);
    }
    
    // Log error to database
    await logError({
      search_term: decision.search_term,
      action_attempted: decision.action_type,
      error_message: error.message,
      error_code: error.code,
      retry_count: retryCount
    });
    
    return { success: false, error };
  }
}
```

### 10.4 Data Consistency

#### Handling Stale Data
```
After posting to Google Ads:
  - Wait 5 seconds for propagation
  - Refresh data from API
  - Update UI to reflect changes
  
If term still appears in "Needs Decision":
  - Show warning: "Changes may take a few minutes to appear in Google Ads"
  - Provide manual refresh button
```

---

## 11. Testing Checklist

### 11.1 Classification Logic Tests

- [ ] Search term in "AVD - Global Block" list → Shows as Decisioned
- [ ] Search term in "AVD - Competitor Terms" list → Shows as Decisioned
- [ ] Search term in "AVD - BRANDED_SEARCH_TERMS - US" list → Shows as Decisioned
- [ ] Search term as campaign negative in all 3 tiers → Shows as Decisioned (Campaign Negative)
- [ ] Search term as ad group negative in HIGH and LOW → Shows as Decisioned (Medium tier)
- [ ] Search term as ad group negative in HIGH and MEDIUM → Shows as Decisioned (Low tier)
- [ ] Search term as ad group negative in MEDIUM and LOW → Shows as Decisioned (High tier)
- [ ] Search term not in any list or funnel → Shows as Needs Decision
- [ ] Search term from multiple custom_label_0s → Shows all custom_label_0 rows

### 11.2 Posting Tests - Needs Decision

**Shared Lists:**
- [ ] Post "Global Block" → Verify in "AVD - Global Block" list, exact match
- [ ] Post "Competitor Term" → Verify in "AVD - Competitor Terms" list, exact match
- [ ] Post "Branded Term" → Verify in "AVD - BRANDED_SEARCH_TERMS - US" list, exact match

**Campaign Negative:**
- [ ] Post as Campaign Negative → Verify in all 3 tier campaigns at campaign level, exact match
- [ ] Verify not added to ad group level

**High Tier:**
- [ ] Post as High → Verify NOT in HIGH ad group negatives
- [ ] Verify IN MEDIUM ad group negatives, exact match
- [ ] Verify IN LOW ad group negatives, exact match
- [ ] If previously in HIGH ad group negatives → Verify removed before adding to MED/LOW

**Medium Tier:**
- [ ] Post as Medium → Verify NOT in MEDIUM ad group negatives
- [ ] Verify IN HIGH ad group negatives, exact match
- [ ] Verify IN LOW ad group negatives, exact match
- [ ] If previously in MEDIUM ad group negatives → Verify removed before adding to HIGH/LOW

**Low Tier:**
- [ ] Post as Low → Verify NOT in LOW ad group negatives
- [ ] Verify IN HIGH ad group negatives, exact match
- [ ] Verify IN MEDIUM ad group negatives, exact match
- [ ] If previously in LOW ad group negatives → Verify removed before adding to HIGH/MED

### 11.3 Posting Tests - Existing Funnel

**Tier Changes:**
- [ ] Change High → Medium → Verify removed from MED/LOW, added to HIGH/LOW
- [ ] Change Medium → Low → Verify removed from HIGH/LOW, added to HIGH/MED
- [ ] Change Low → High → Verify removed from HIGH/MED, added to MED/LOW
- [ ] Change Campaign Negative → High → Verify removed from all campaign negatives, added to MED/LOW ad group negatives

**Moving to Shared List:**
- [ ] Move High tier → Global Block → Verify removed from MED/LOW ad group negatives, added to shared list
- [ ] Move Campaign Negative → Competitor → Verify removed from all 3 campaign negatives, added to shared list

### 11.4 Error Detection Tests

- [ ] Term in all 3 tiers at ad group level → Shows error "Blocked in all 3 tiers"
- [ ] Term in only 1 tier at ad group level → Shows error "Only blocked in 1 tier"
- [ ] Term in only 1 or 2 tiers at campaign level → Shows error "Campaign negative incomplete"
- [ ] Error icon displays correctly in Existing Funnel view
- [ ] Can fix errors by selecting correct tier

### 11.5 UI/UX Tests

- [ ] Date range picker changes data
- [ ] Filters work correctly
- [ ] Radio button defaults to source tier
- [ ] Can change radio button selection
- [ ] Checkbox selection works
- [ ] Multiple custom_label_0 rows display correctly
- [ ] Performance metrics show in Existing Funnel view
- [ ] Performance metrics hidden in Needs Decision view
- [ ] Post button shows progress indicator
- [ ] Success/error messages display correctly

### 11.6 Edge Cases

- [ ] Search term with special characters (e.g., "chrome 12" towel bar")
- [ ] Search term with quotes
- [ ] Very long search terms (>80 characters)
- [ ] Search term from discontinued campaign (campaign no longer exists)
- [ ] Posting when Google Ads API is down
- [ ] Posting with rate limit hit
- [ ] Multiple users posting simultaneously (if applicable)

---

## 12. Phase 2 Considerations

Features explicitly deferred to Phase 2:

### 12.1 Performance Max (PMax) Campaigns
- Separate workflow for PMax search terms
- PMax terms require CSV download (not available via API)
- Similar classification and posting logic
- Separate navigation item: "PMax Funnel"

### 12.2 Search Campaigns
- Separate workflow for Search campaigns
- Different posting rules (positive keywords, not just negatives)
- Match type variations (exact, phrase, broad)
- Separate navigation item: "Search Campaigns"

### 12.3 Match Type Expansion
- Add broad match and phrase match options
- UI changes: Add match type selector
- API changes: Pass match_type parameter

### 12.4 Advanced Features
- Action history / audit log
- Performance-based priority scoring
- Export to CSV
- Saved filter presets
- Bulk auto-classification rules (e.g., "if contains 'free' → Global Block")
- Dashboard analytics (terms processed per day, most common actions, etc.)

### 12.5 Multi-User Support
- User permissions (who can post to Google Ads)
- Activity tracking (who posted what and when)
- Conflict resolution (two users editing same term)

---

## Implementation Priority Order

### Sprint 1: Core Infrastructure (Week 1)
1. Set up Google Ads API connection in Vercel serverless functions
2. Implement data fetching endpoints (search terms, negative keywords, shared lists)
3. Implement classification logic
4. Create database schema (if using staging tables)

### Sprint 2: Needs Decision View (Week 2)
1. Build Needs Decision UI
2. Implement filters
3. Build action selection UI (radio buttons)
4. Implement "Save Decisions" (if using staging)

### Sprint 3: Posting Logic (Week 3)
1. Implement Google Ads API posting functions
2. Add retry logic and error handling
3. Implement "Post to Google Ads" button
4. Add progress indicators and success/error messages

### Sprint 4: Existing Funnel View (Week 4)
1. Build Existing Funnel UI
2. Implement tier display logic
3. Implement error detection
4. Add editing capability

### Sprint 5: Testing & Polish (Week 5)
1. Run full testing checklist
2. Fix bugs
3. Performance optimization
4. UI polish and responsive design

---

## Technical Notes

### Google Ads API Client Setup

```javascript
// Example using Google Ads API Node.js client
const { GoogleAdsApi } = require('google-ads-api');

const client = new GoogleAdsApi({
  client_id: process.env.GOOGLE_ADS_CLIENT_ID,
  client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
  developer_token: process.env.GOOGLE_ADS_DEVELOPER_TOKEN,
});

const customer = client.Customer({
  customer_id: process.env.GOOGLE_ADS_CUSTOMER_ID,
  refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN,
});
```

### Environment Variables Needed

```
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_REFRESH_TOKEN=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

### Serverless Function Timeout
- Vercel serverless functions have 10-second timeout on free tier, 60-second on paid
- Google Ads API calls can take 5-10 seconds for large data fetches
- Consider implementing:
  - Data caching in Supabase
  - Background jobs for large data refreshes
  - Pagination for large result sets

### Rate Limiting
- Google Ads API: 15,000 operations per day (standard access)
- Each keyword addition/removal = 1 operation
- Monitor usage to avoid hitting limits
- Implement batching for bulk operations

---

## Questions for Clarification

Before starting implementation, Bobby should clarify:

1. **Google Ads Credentials:**
   - Confirm Bobby has access to Google Ads API credentials
   - Confirm customer ID to use
   - Confirm API access level (standard vs test)

2. **Supabase Database:**
   - Should staging tables be implemented? Or post directly to Google Ads without intermediate storage?
   - Should error logs be stored in Supabase?

3. **UI Framework:**
   - What UI component library is currently used in FeedOps? (Tailwind? Material-UI? shadcn?)
   - Should Shopping Funnel match existing design system?

4. **Deployment:**
   - Any specific Vercel configuration needed?
   - Should this be behind feature flag initially?

---

## Success Criteria

This implementation is successful when:

1. ✅ All search terms from Shopping campaigns are correctly classified as "Decisioned" or "Needs Decision"
2. ✅ Classification logic exactly matches the Python script behavior
3. ✅ User can select actions for terms and post to Google Ads
4. ✅ Posting follows all 7 rules correctly (shared lists, campaign negatives, tier assignments)
5. ✅ Existing funnel view shows all terms currently in funnel with correct tier assignments
6. ✅ Errors are detected and highlighted (blocked in all 3 tiers, incomplete campaign negatives, etc.)
7. ✅ User can edit existing funnel assignments and re-post to Google Ads
8. ✅ All Google Ads API errors are handled gracefully with retry logic
9. ✅ UI is responsive and matches FeedOps design system
10. ✅ Rob can process 50-100 search terms in under 10 minutes

---

## Appendix A: Campaign Name Examples

All 63 custom_label_0 categories with campaign naming examples:

```
AVD - Shopping - US - 2 Post TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - 4 Tier Glass Wall Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Assorted Freestanding Accessories - HIGH/MEDIUM/LOW
AVD - Shopping - US - Baskets - HIGH/MEDIUM/LOW
AVD - Shopping - US - Assorted Wall Mounted Accessories - HIGH/MEDIUM/LOW
AVD - Shopping - US - Cabinet Hardware - HIGH/MEDIUM/LOW
AVD - Shopping - US - Candle Holders - HIGH/MEDIUM/LOW
AVD - Shopping - US - Ceiling Hung Mirrors - HIGH/MEDIUM/LOW
AVD - Shopping - US - Corner Glass Shelves - HIGH/MEDIUM/LOW
AVD - Shopping - US - Door Pull - HIGH/MEDIUM/LOW
AVD - Shopping - US - Double Glass Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Double Glass Shelf with Towel Bar - HIGH/MEDIUM/LOW
AVD - Shopping - US - European Style TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Free Standing Make-Up Mirrors - HIGH/MEDIUM/LOW
AVD - Shopping - US - Freestanding Towel Stand - HIGH/MEDIUM/LOW
AVD - Shopping - US - Freestanding TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Garment Rods - HIGH/MEDIUM/LOW
AVD - Shopping - US - Grab Bars - HIGH/MEDIUM/LOW
AVD - Shopping - US - Guest Towel Tray - HIGH/MEDIUM/LOW
AVD - Shopping - US - Ladder Towel Bar - HIGH/MEDIUM/LOW
AVD - Shopping - US - Mug Holders - HIGH/MEDIUM/LOW
AVD - Shopping - US - Multi Roll TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Multi Roll TP Holder with Glass Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Multi Roll TP Holder with Wood Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Paper Towel Holders - HIGH/MEDIUM/LOW
AVD - Shopping - US - Patriotic - HIGH/MEDIUM/LOW
AVD - Shopping - US - Recessed TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Refrigerator Pull - HIGH/MEDIUM/LOW
AVD - Shopping - US - Retractable Hooks - HIGH/MEDIUM/LOW
AVD - Shopping - US - Robe Hook - HIGH/MEDIUM/LOW
AVD - Shopping - US - Rollerless - HIGH/MEDIUM/LOW
AVD - Shopping - US - Shower Curtain Brackets - HIGH/MEDIUM/LOW
AVD - Shopping - US - Shower Door Knobs and Hooks - HIGH/MEDIUM/LOW
AVD - Shopping - US - Shower Door Pull - HIGH/MEDIUM/LOW
AVD - Shopping - US - Shower Door Towel Bars - HIGH/MEDIUM/LOW
AVD - Shopping - US - Shower Squeegee - HIGH/MEDIUM/LOW
AVD - Shopping - US - Single Glass Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Single Glass Shelf with Towel Bar - HIGH/MEDIUM/LOW
AVD - Shopping - US - Soap Dishes & Holders - HIGH/MEDIUM/LOW
AVD - Shopping - US - Soap Dispensers - HIGH/MEDIUM/LOW
AVD - Shopping - US - Sports - HIGH/MEDIUM/LOW
AVD - Shopping - US - Toothbrush Holders - HIGH/MEDIUM/LOW
AVD - Shopping - US - Towel Bar with Hook - HIGH/MEDIUM/LOW
AVD - Shopping - US - Towel Shelves - HIGH/MEDIUM/LOW
AVD - Shopping - US - TP Holder with Glass Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - TP Holder with Wood Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Triple Glass Shelf - HIGH/MEDIUM/LOW
AVD - Shopping - US - Triple Glass Shelf with Towel Bar - HIGH/MEDIUM/LOW
AVD - Shopping - US - Upright TP Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Vanity Top Make-Up Mirrors - HIGH/MEDIUM/LOW
AVD - Shopping - US - Vanity Towel Rings - HIGH/MEDIUM/LOW
AVD - Shopping - US - Vanity Towel Stand - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mirrors - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Double Towel Bar - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Guest Towel Holder - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Make-Up Mirrors - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Multi Hooks - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Swing Towel Arms - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Towel Bars - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wall Mounted Towel Rings - HIGH/MEDIUM/LOW
AVD - Shopping - US - Wood Shelves - HIGH/MEDIUM/LOW
AVD - Shopping - US - Reserve Roll TP Holder - HIGH/MEDIUM/LOW
```

---

## Appendix B: Reference Python Script Logic

The existing Python script (`search_terms_workflow.py`) that this implementation should match:

**Key functions to replicate:**
- `infer_label0_and_tier()` - Parse campaign name
- `determine_decisioned()` - Classification logic
- `build_label0_group_sets()` - Aggregate funnel keywords across tiers

**Critical rules:**
1. Ignore campaigns containing 'tst' (case-insensitive)
2. Normalize search terms (lowercase, trim, collapse whitespace)
3. Check shared lists first, then campaign-level, then ad group-level
4. For Shopping funnels, check across all 3 tiers for a given custom_label_0

---

**End of Requirements Document**

**Bobby: Use Claude Code to implement this specification. Start with Sprint 1 and work sequentially through the sprints. Test thoroughly at each stage before moving to the next sprint.**
