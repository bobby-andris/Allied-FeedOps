---
description: Evaluate generated content against the quality scoring rubric
---

# /evaluate-output

## Purpose
Score generated titles and descriptions against the research-backed quality rubric to determine publication readiness.

## Usage
```
/evaluate-output [content to evaluate]
```

Or provide content in the message:
```
/evaluate-output
Title: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome
Description: This towel bar is made from premium materials...
```

## Scoring Rubric

### 1. Specificity Score (0-10)
Ratio of specific, verifiable claims to vague claims.

**Specific claims** (count these):
- Dimensions: "24-inch", "18 inches"
- Materials: "solid brass", "stainless steel"
- Capacities: "500 lb capacity", "holds 4 towels"
- Certifications: "ADA compliant", "UL listed"
- Features: "concealed mounting", "tilt-adjustable"

**Vague claims** (count these):
- "high-quality", "premium", "best"
- "durable", "sturdy", "strong" (without specs)
- "beautiful", "elegant" (without specifics)
- "easy to install" (without details)

**Calculation**: `(Specific / (Specific + Vague)) × 10`

### 2. Benefit Coverage (0-10)
Does the first 150 characters contain a clear benefit?

| Score | Criteria |
|-------|----------|
| 10 | Benefit + key spec in opening sentence |
| 8 | Clear benefit in first 150 chars |
| 6 | Benefit present but not leading |
| 4 | Feature-first, benefit implied |
| 2 | Features only, no benefit |
| 0 | Generic/empty opening |

**Example 10/10**: "Protect your loved ones with this ADA-compliant grab bar supporting up to 500 pounds."

**Example 4/10**: "This 18-inch grab bar is made of solid brass and comes in satin nickel."

### 3. Keyword Inclusion (0-10)

**Title points** (max 6):
- Brand in first 70 chars: +2
- Product type in first 70 chars: +2
- Primary dimension in title: +1
- Functional modifier present: +1

**Description points** (max 4):
- Primary keyword in first sentence: +2
- Related terms/synonyms included: +1
- Use-case language present: +1

### 4. Format Adherence (0-10)

**Title checklist** (max 5):
- ≤150 characters: +2
- ≥50 characters: +1
- Proper separators used: +1
- No ALL CAPS: +0.5
- No promotional text: +0.5

**Description checklist** (max 5):
- ≥500 characters: +2
- Bullet points used: +1
- Structured sections: +1
- First 150 chars standalone: +1

### 5. Brand Voice (0-10)

**Premium indicators** (+2 each, max 10):
- Uses "crafted", "engineered", "precision"
- References specific materials properly
- Understated, confident tone
- Includes specific numbers/measurements
- Mentions warranty/guarantee

**Deductions**:
- Superlatives (best, amazing, incredible): -3
- ALL CAPS words: -2
- Exclamation points: -1
- Generic marketing fluff: -2
- Budget language (cheap, affordable, bargain): -3

### 6. Factual Accuracy (0-10)

| Score | Criteria |
|-------|----------|
| 10 | All claims verifiable against source data |
| 8 | Minor unverified claim (subjective quality) |
| 5 | Unverified specification present |
| 0 | Invented specification detected |

**CRITICAL**: Score below 8 triggers automatic REJECT.

## Output Format

```markdown
# Content Evaluation Report

## Content Evaluated
**Title**: [evaluated title]
**Description**: [evaluated description]

---

## Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Specificity | X/10 | [X] specific, [Y] vague claims |
| Benefit Coverage | X/10 | [assessment] |
| Keyword Inclusion | X/10 | [missing items] |
| Format Adherence | X/10 | [violations] |
| Brand Voice | X/10 | [tone assessment] |
| Factual Accuracy | X/10 | [verification status] |

### Composite Score: XX%

---

## Status: [APPROVED / REVISE / REJECT]

### Threshold Reference
- ≥80%: APPROVED for publication
- 70-79%: REVISE with specific improvements
- <70%: REJECT, major revision required

---

## Specific Feedback

### Strengths
1. [Strength 1]
2. [Strength 2]

### Areas for Improvement
1. [Issue]: [Specific recommendation]
2. [Issue]: [Specific recommendation]

### Suggested Revisions
[If status is REVISE, provide specific edit suggestions]
```

## Example Evaluation

**Input**:
```
/evaluate-output
Title: Towel Bar - High Quality Chrome
Description: This is a great towel bar for your bathroom. It's made of high-quality materials and looks beautiful. Easy to install.
```

**Output**:
```markdown
# Content Evaluation Report

## Content Evaluated
**Title**: Towel Bar - High Quality Chrome
**Description**: This is a great towel bar for your bathroom. It's made of high-quality materials and looks beautiful. Easy to install.

---

## Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Specificity | 1/10 | 0 specific claims, 4 vague (high-quality, great, beautiful, easy) |
| Benefit Coverage | 2/10 | No clear benefit, generic opening |
| Keyword Inclusion | 3/10 | Product type present, missing brand/dimension |
| Format Adherence | 3/10 | Title too short (28 chars), desc too short (108 chars) |
| Brand Voice | 2/10 | Generic marketing language, no premium indicators |
| Factual Accuracy | 5/10 | Cannot verify "high-quality materials" |

### Composite Score: 27%

---

## Status: ❌ REJECT

---

## Specific Feedback

### Strengths
1. Product type (towel bar) is included

### Areas for Improvement
1. **No dimensions**: Add specific size (e.g., "24-inch")
2. **Missing brand**: Include brand name at start
3. **Vague material**: Replace "high-quality materials" with actual material (e.g., "solid brass")
4. **No specifics**: Replace "easy to install" with "includes mounting hardware"
5. **Too short**: Title needs 70+ chars, description needs 500+ chars

### Suggested Revision
**Title**: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount

**Description**: 
Crafted from solid brass that will never corrode, peel, or tarnish, this 24-inch towel bar brings enduring elegance to your bathroom.

• Solid brass construction – corrosion-proof durability
• 24-inch length – ideal for standard bath towels
• Concealed mounting hardware – clean, modern appearance
• Polished chrome finish – coordinates with existing fixtures

Includes mounting hardware and installation template. Backed by lifetime warranty.
```

## Quick Score Reference

For rapid evaluation, use this checklist:

### Title Quick Check
- [ ] Has brand? (+2)
- [ ] Has product type? (+2)
- [ ] Has dimension? (+1)
- [ ] Has material? (+1)
- [ ] 70-150 characters? (+2)
- [ ] No ALL CAPS or promos? (+2)

### Description Quick Check
- [ ] Benefit in first sentence? (+3)
- [ ] ≥500 characters? (+2)
- [ ] Has bullet points? (+1)
- [ ] All claims specific? (+2)
- [ ] No vague language? (+2)
