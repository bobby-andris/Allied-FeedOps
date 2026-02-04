# Task: Implement Description Quality Analyzer

## Objective

Build a real-time description quality analyzer that scores content against buyer psychology principles and provides actionable improvement suggestions during the review process.

## Problem Statement

Writers don't have real-time feedback on description quality. They can't see what's working and what's not until after publishing, leading to:
- Inconsistent quality across SKUs
- Missed opportunities to address buyer questions
- Weak openings that don't convert scanners to readers
- Missing trust signals that reduce conversion

## Solution Overview

Add a quality analyzer panel to the SKU review page that:
1. Scores descriptions against 6 dimensions (from AGENTS.md rubric)
2. Checks for buyer psychology principles
3. Highlights specific issues with inline suggestions
4. Shows a comparison to high-performing patterns
5. Updates in real-time as content is edited

## Files to Create/Modify

### New Files
- `dashboard/src/components/review/QualityAnalyzer.tsx` - Main analyzer component
- `dashboard/src/lib/quality-scoring.ts` - Scoring logic
- `dashboard/src/lib/quality-checks.ts` - Individual quality checks

### Modified Files
- `dashboard/src/app/(dashboard)/review/[sku]/page.tsx` - Add analyzer panel
- `dashboard/src/components/review/SkuReviewClient.tsx` - Integrate analyzer

## Scoring Dimensions (0-10 each)

### 1. Specificity Score
- 10: All claims are specific and verifiable (dimensions, materials, capacities)
- 5: Mix of specific and vague claims
- 0: All claims are generic ("high-quality", "premium", "best")

**Checks:**
- Count specific numbers/measurements
- Detect banned vague words: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate
- Verify claims reference product data

### 2. Benefit Coverage Score
- 10: Primary benefits addressed in first 150 characters
- 5: Benefits mentioned but not in opening
- 0: Only features listed, no benefits stated

**Checks:**
- Opening mentions problem solved OR desired outcome
- First 150 chars contain value proposition
- Benefits before features pattern detected

### 3. Keyword Inclusion Score
- 10: All target keywords in optimal positions
- 5: Keywords present but suboptimal placement
- 0: Missing critical keywords

**Checks:**
- Product type in first 30 chars (title)
- Primary dimension before char 70 (title)
- Primary keyword in first sentence (description)

### 4. Format Adherence Score
- 10: Perfect compliance with character limits and structure
- 5: Minor violations (slightly over/under limits)
- 0: Major violations (exceeds limits, wrong structure)

**Checks:**
- Title: 60-150 chars (Google/Bing), max 255 (Shopify)
- Description: 500+ chars recommended
- Short title: max 70 chars
- Bullet format: uses "- " not Unicode bullets
- Structure: opening → bullets → specs

### 5. Brand Voice Score
- 10: Confident, specific, premium-appropriate tone
- 5: Neutral tone, neither premium nor budget
- 0: Uses superlatives, marketing fluff, or budget language

**Checks:**
- Uses confident verbs ("crafted", "provides") not hedging ("helps provide")
- No banned superlatives
- Mentions brand differentiators when supported (solid brass, warranty, 28 finishes)

### 6. Factual Accuracy Score
- 10: Every claim traceable to product data
- 5: Some claims inferred but reasonable
- 0: Contains invented specs or unverifiable claims

**Checks:**
- No source citations in output (catalog_csv.*)
- No internal terminology (MasterSKU, finish injection)
- All measurements match product data

## Buyer Psychology Checks

### Opening Hook Analysis
- Does it address buyer's problem? (Yes/No + suggestion)
- Does it mention desired outcome? (Yes/No)
- Is it scannable? (sentence length < 25 words)

### Trust Signal Presence
- [ ] Material quality mentioned (solid brass, etc.)
- [ ] Warranty mentioned
- [ ] Assembly/manufacturing location mentioned
- [ ] Finish coordination mentioned

### Buyer Questions Addressed
Based on prompts.py:
1. "Will this look good in MY bathroom?" → Visualization language present?
2. "Will this match my other fixtures?" → Finish coordination mentioned?
3. "Is this better than the $20 Amazon option?" → Value differentiation present?
4. "Will this last?" → Durability/material trust signals?

## Component Implementation

### QualityAnalyzer.tsx

```tsx
'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, CheckCircle, Info, Lightbulb } from 'lucide-react'
import { analyzeDescription, type QualityAnalysis } from '@/lib/quality-scoring'

interface QualityAnalyzerProps {
  title: string
  description: string
  platform: 'google' | 'bing' | 'shopify'
  productData?: {
    category?: string
    material?: string
    dimensions?: string
    finish?: string
  }
}

export function QualityAnalyzer({
  title,
  description,
  platform,
  productData
}: QualityAnalyzerProps) {
  const [analysis, setAnalysis] = useState<QualityAnalysis | null>(null)

  useEffect(() => {
    const result = analyzeDescription(title, description, platform, productData)
    setAnalysis(result)
  }, [title, description, platform, productData])

  if (!analysis) return null

  const compositeScore = Math.round(
    (analysis.specificity +
     analysis.benefitCoverage +
     analysis.keywordInclusion +
     analysis.formatAdherence +
     analysis.brandVoice +
     analysis.factualAccuracy) / 6 * 10
  )

  return (
    <Card className="h-fit">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          Quality Analysis
          <Badge variant={compositeScore >= 80 ? 'default' : compositeScore >= 70 ? 'secondary' : 'destructive'}>
            {compositeScore}%
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score Breakdown */}
        <div className="space-y-2">
          <ScoreRow label="Specificity" score={analysis.specificity} />
          <ScoreRow label="Benefits" score={analysis.benefitCoverage} />
          <ScoreRow label="Keywords" score={analysis.keywordInclusion} />
          <ScoreRow label="Format" score={analysis.formatAdherence} />
          <ScoreRow label="Voice" score={analysis.brandVoice} />
          <ScoreRow label="Accuracy" score={analysis.factualAccuracy} />
        </div>

        {/* Issues */}
        {analysis.issues.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium flex items-center gap-1">
              <AlertCircle className="h-4 w-4 text-yellow-500" />
              Issues ({analysis.issues.length})
            </h4>
            <ul className="text-sm space-y-1">
              {analysis.issues.map((issue, i) => (
                <li key={i} className="text-muted-foreground">• {issue}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Suggestions */}
        {analysis.suggestions.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium flex items-center gap-1">
              <Lightbulb className="h-4 w-4 text-blue-500" />
              Suggestions
            </h4>
            <ul className="text-sm space-y-1">
              {analysis.suggestions.map((suggestion, i) => (
                <li key={i} className="text-muted-foreground">• {suggestion}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Trust Signals */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Trust Signals</h4>
          <div className="flex flex-wrap gap-1">
            <TrustBadge label="Material" present={analysis.trustSignals.material} />
            <TrustBadge label="Warranty" present={analysis.trustSignals.warranty} />
            <TrustBadge label="Made in USA" present={analysis.trustSignals.madeInUSA} />
            <TrustBadge label="Finish Match" present={analysis.trustSignals.finishCoordination} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function ScoreRow({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-16">{label}</span>
      <Progress value={score * 10} className="h-2 flex-1" />
      <span className="text-xs w-6 text-right">{score}</span>
    </div>
  )
}

function TrustBadge({ label, present }: { label: string; present: boolean }) {
  return (
    <Badge variant={present ? 'default' : 'outline'} className="text-xs">
      {present ? <CheckCircle className="h-3 w-3 mr-1" /> : null}
      {label}
    </Badge>
  )
}
```

### quality-scoring.ts

```typescript
export interface QualityAnalysis {
  specificity: number
  benefitCoverage: number
  keywordInclusion: number
  formatAdherence: number
  brandVoice: number
  factualAccuracy: number
  issues: string[]
  suggestions: string[]
  trustSignals: {
    material: boolean
    warranty: boolean
    madeInUSA: boolean
    finishCoordination: boolean
  }
}

const BANNED_VAGUE_WORDS = [
  'finest', 'luxurious', 'premium', 'exclusive', 'exceptional',
  'unparalleled', 'superior', 'exquisite', 'ultimate', 'best',
  'amazing', 'incredible', 'perfect', 'stunning'
]

const HEDGING_WORDS = ['helps', 'may', 'might', 'could', 'possibly']

export function analyzeDescription(
  title: string,
  description: string,
  platform: 'google' | 'bing' | 'shopify',
  productData?: { category?: string; material?: string; dimensions?: string; finish?: string }
): QualityAnalysis {
  const issues: string[] = []
  const suggestions: string[] = []

  // Specificity
  const vagueCount = BANNED_VAGUE_WORDS.filter(w =>
    description.toLowerCase().includes(w)
  ).length
  const numberCount = (description.match(/\d+/g) || []).length
  const specificity = Math.max(0, Math.min(10, 10 - vagueCount * 2 + Math.min(numberCount, 3)))

  if (vagueCount > 0) {
    issues.push(`Contains ${vagueCount} vague word(s): avoid "premium", "finest", etc.`)
  }

  // Benefit Coverage
  const first150 = description.slice(0, 150).toLowerCase()
  const hasProblemLanguage = /solve|prevent|protect|keep|eliminate|reduce|improve/.test(first150)
  const hasOutcomeLanguage = /beautiful|elegant|organized|secure|safe|convenient/.test(first150)
  const benefitCoverage = hasProblemLanguage || hasOutcomeLanguage ? 8 : 4

  if (!hasProblemLanguage && !hasOutcomeLanguage) {
    suggestions.push('Start with the problem solved or desired outcome')
  }

  // Keyword Inclusion
  const titleLower = title.toLowerCase()
  const first30 = title.slice(0, 30).toLowerCase()
  const first70 = title.slice(0, 70).toLowerCase()

  let keywordInclusion = 5
  if (productData?.category && first30.includes(productData.category.toLowerCase().split(' ')[0])) {
    keywordInclusion += 2
  }
  if (productData?.dimensions && first70.includes(productData.dimensions.split(' ')[0])) {
    keywordInclusion += 2
  }
  if (titleLower.includes('allied brass')) {
    keywordInclusion += 1
  }

  // Format Adherence
  let formatAdherence = 10
  if (platform === 'google' || platform === 'bing') {
    if (title.length < 60) {
      formatAdherence -= 3
      issues.push(`Title too short (${title.length} chars, target 60-150)`)
    }
    if (title.length > 150) {
      formatAdherence -= 5
      issues.push(`Title exceeds limit (${title.length}/150 chars)`)
    }
  }
  if (description.length < 500) {
    formatAdherence -= 2
    suggestions.push(`Description is short (${description.length} chars, target 500+)`)
  }

  // Brand Voice
  const hedgingCount = HEDGING_WORDS.filter(w => description.toLowerCase().includes(w)).length
  const brandVoice = Math.max(0, 10 - hedgingCount * 2 - vagueCount)

  if (hedgingCount > 0) {
    suggestions.push('Use confident language: "provides" not "helps provide"')
  }

  // Factual Accuracy
  let factualAccuracy = 10
  if (description.includes('catalog_csv') || description.includes('MasterSKU')) {
    factualAccuracy = 0
    issues.push('Contains internal references - remove before publishing')
  }

  // Trust Signals
  const descLower = description.toLowerCase()
  const trustSignals = {
    material: descLower.includes('solid brass') || descLower.includes('brass construction'),
    warranty: descLower.includes('warranty') || descLower.includes('guarantee'),
    madeInUSA: descLower.includes('virginia') || descLower.includes('made in') || descLower.includes('assembled'),
    finishCoordination: descLower.includes('coordinate') || descLower.includes('match') || descLower.includes('28 finish')
  }

  const missingTrust = []
  if (!trustSignals.material) missingTrust.push('material quality')
  if (!trustSignals.warranty) missingTrust.push('warranty')
  if (missingTrust.length > 0) {
    suggestions.push(`Consider adding trust signals: ${missingTrust.join(', ')}`)
  }

  return {
    specificity,
    benefitCoverage,
    keywordInclusion: Math.min(10, keywordInclusion),
    formatAdherence,
    brandVoice,
    factualAccuracy,
    issues,
    suggestions,
    trustSignals
  }
}
```

## Integration Points

### Add to SKU Review Page

In `SkuReviewClient.tsx`, add the analyzer as a sidebar:

```tsx
<div className="grid grid-cols-3 gap-6">
  <div className="col-span-2">
    {/* Existing content comparison */}
  </div>
  <div className="col-span-1">
    <QualityAnalyzer
      title={currentContent.title}
      description={currentContent.description}
      platform={selectedPlatform}
      productData={{
        category: skuData.category,
        material: skuData.material,
        dimensions: skuData.dimensions,
        finish: selectedVariant?.finish
      }}
    />
  </div>
</div>
```

## Success Criteria

1. [ ] Quality analyzer renders on SKU review page
2. [ ] Scores update in real-time when content changes
3. [ ] Issues list shows specific, actionable problems
4. [ ] Suggestions help writers improve content
5. [ ] Trust signals checklist is accurate
6. [ ] Composite score matches manual evaluation (±10%)
7. [ ] No performance degradation (analysis < 50ms)

## Testing

### Unit Tests
- Test each scoring dimension with known inputs
- Test edge cases (empty strings, very long content)
- Test platform-specific rules

### Integration Tests
- Verify analyzer integrates with review page
- Test real-time updates work

### Manual QA
- Review 5 SKUs with analyzer
- Verify suggestions are actionable
- Confirm scores feel accurate
