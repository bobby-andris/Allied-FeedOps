# Task: FeedOps Complete Implementation Overhaul

## Required Skills - READ FIRST

**Before doing anything else**, read these skills and follow them throughout:

1. Read: `/Users/bobby/.cursor/projects/Users-bobby-Documents-GitHub-Allied-FeedOps/skills/superpowers/skills/brainstorming/SKILL.md`
2. Read: `/Users/bobby/.cursor/projects/Users-bobby-Documents-GitHub-Allied-FeedOps/skills/superpowers/skills/writing-plans/SKILL.md`  
3. Read: `/Users/bobby/.cursor/projects/Users-bobby-Documents-GitHub-Allied-FeedOps/skills/superpowers/skills/verification-before-completion/SKILL.md`

Announce: "I'm using the superpowers skills to ensure proper planning and verification."

## Required Rules - READ SECOND

Read these Cursor rules:
1. `.cursor/rules/python-environment.mdc` - Critical for running any Python code
2. `.cursor/rules/context7-docs.mdc` - Use Context7 for library documentation

## Context

Review the existing implementation:
- Implementation plan: `.cursor/plans/feedops_mvp_implementation_f7d9387f.plan.md`
- Platform guidelines: `docs/04-platform-guidelines.md`
- YouTube video insights: `docs/Youtube-video-transcript.md`
- Current prompts: `src/feedops/pipeline/prompts.py`
- Agent rules: `AGENTS.md`

---

## CRITICAL ISSUES TO FIX

### Issue 1: Update Model Versions

**Use Context7 MCP** to verify the latest models, then update:

**OpenAI** (`src/feedops/providers/openai_provider.py`):
- Current: `gpt-4o`
- Update to latest stable version (e.g., `gpt-4o-2024-11-20` or newer)
- Enable vision capability for image input

**Gemini** (`src/feedops/providers/gemini_provider.py`):
- Current: `gemini-2.0-flash`
- Verify this is the latest, update if needed
- Enable multimodal input for images

---

### Issue 2: Add Product Image Input to LLM

**This is critical for preventing hallucinations and identifying product characteristics.**

From the YouTube transcript: "Lifestyle images can 2-3x click-through rate"

**Implementation:**

1. **Update evidence gathering** (`src/feedops/pipeline/evidence.py`):
   - Add image URL extraction from catalog (Main URL column)
   - Download/encode image for LLM input

2. **Update LLM providers** to accept image input:
   ```python
   # OpenAI vision
   messages = [
       {
           "role": "user",
           "content": [
               {"type": "text", "text": prompt},
               {"type": "image_url", "image_url": {"url": image_url}}
           ]
       }
   ]
   
   # Gemini multimodal
   contents = [prompt, types.Part.from_uri(file_uri=image_url, mime_type="image/jpeg")]
   ```

3. **Update prompts** to instruct LLM:
   - "Analyze the product image to identify key visual characteristics"
   - "Verify that any materials/colors mentioned match what's visible in the image"
   - "Do NOT describe features not visible in the image or listed in the data"

---

### Issue 3: Fix Source Reference Leakage

**Problem**: Generated descriptions contain `(catalog_csv.Weight Capacity)` - source citations are leaking into customer-facing content.

**Fix in** `src/feedops/pipeline/prompts.py`:

Add to SYSTEM_PROMPT:
```
CRITICAL: The title and description fields must contain ONLY customer-facing text.
- Do NOT include source citations like (catalog_csv.Field) in the output text
- Do NOT include field references or attribution in the description
- The 'claims' array is where you record source attribution, NOT in the description text
- If I see any parenthetical references to source fields in the title or description, the output is REJECTED
```

**Add validation** in pipeline to reject outputs containing citation patterns.

---

### Issue 4: Implement YouTube Video Insights

The video at `docs/Youtube-video-transcript.md` has critical insights that differ from current implementation:

#### A. Title Priority Order (lines 74-109)

**First 30-70 characters are MOST critical** (not just 70):
- Frontload highest-converting keywords
- Google can dynamically reorder keywords in titles

#### B. Brand Placement Logic (lines 113-165)

**Current rule is too simple.** Update to:

| Brand Recognition | Title Structure |
|-------------------|-----------------|
| Well-known (Nike, Apple, Samsung) | Brand FIRST |
| Lesser-known brand | Benefits/Keywords FIRST, Brand at END |

**Example from video**:
- Nike: `Nike React Flight Men's Running Shoes Black Gray Size 10.5`
- Home Reserve (unknown): `Kid and Pet Friendly Sectional Sofa Washable - Home Reserve`

**Allied Brass is NOT a household name** - consider putting benefits first for some products.

#### C. Key Benefits + Use Cases (lines 153-168)

For generic/homegoods products (which bathroom hardware IS):
- Frontload key benefits and use cases
- Brand at end if not well-known

**Examples for Allied Brass**:
- Current: `Allied Brass 16-Inch Grab Bar | Powder Coated Iron | Industrial Wall Mount`
- Better: `ADA-Compliant 16-Inch Grab Bar 250lb Capacity | Industrial Wall Mount | Allied Brass`

#### D. Search Term Integration (lines 197-211)

The video emphasizes using actual **search term data** from Google Ads:
- Use Google Ads MCP to pull high-performing search terms
- Bake those exact terms into titles

#### E. Unified Research → Complementary Outputs

**Note**: The video's "80/20 rule" applies to humans manually optimizing feeds with limited time. For an AI system, this doesn't apply.

**Our approach**: Research is done ONCE, then applied to BOTH title and description:

| Phase | What Happens |
|-------|--------------|
| **Research** | Gather evidence, analyze product, identify keywords, analyze images |
| **Title Output** | Apply research to capture attention, match search queries (drives CTR) |
| **Description Output** | Apply research to build trust, provide details, address objections (drives CVR) |

Both outputs must be excellent. A great title driving clicks to a weak description wastes ad spend.

#### F. GTIN Importance (lines 213-234)

Make sure GTIN/UPC is being used in the output and properly passed through.

---

### Issue 5: Implement Platform-Specific Outputs

**Reference**: `docs/04-platform-guidelines.md`

The current system generates ONE output. It should generate THREE:

1. **Google Shopping** output:
   - `title` (150 chars, optimized for semantic matching)
   - `short_title` (for video overlays)
   - `description` (benefit-first, keywords for long-tail)

2. **Bing/Microsoft Shopping** output:
   - Title with explicit synonyms (more literal matching)
   - Description with explicit keyword variations

3. **Shopify** output:
   - Title optimized for H1/SEO
   - Description with HTML formatting (bullets, etc.)

**Update Candidate model** (`src/feedops/models/candidate.py`):
```python
class Candidate(BaseModel):
    # Google
    google_title: str
    google_short_title: str
    google_description: str
    
    # Bing
    bing_title: str
    bing_description: str
    
    # Shopify
    shopify_title: str
    shopify_description: str
    
    # Keep existing
    claims: list[Claim]
    self_score: Score
```

**Update exports** to generate:
- `exports/google-patch-{SKU}.json`
- `exports/bing-patch-{SKU}.json`
- `exports/shopify-patch-{SKU}.json`

---

### Issue 6: Add Full LLM Input to Reports

**Update** `src/feedops/pipeline/reporter.py` to include:

```markdown
## Input Data Sent to LLM

### Evidence Table
| Field | Value | Source |
|-------|-------|--------|
[full evidence table here]

### Product Image
[image URL or "No image available"]

### Full Prompt
<details>
<summary>Click to expand full prompt</summary>

[complete prompt text]

</details>

### Token Usage
- Prompt tokens: X
- Completion tokens: Y
- Estimated cost: $Z
```

---

### Issue 7: Integrate MCP Servers

Create `src/feedops/integrations/` directory with optional MCP integrations:

#### A. Google Ads MCP (`user-google-ads-mcp`)
- Pull search term performance data for the product category
- Identify high-CTR keywords to incorporate into titles
- Add to evidence table as "high_performing_keywords"

#### B. Analytics MCP (`user-analytics-mcp`)
- Pull product page metrics (if available)
- Bounce rate, time on page, conversion rate
- Helps prioritize which products to optimize

#### C. Apify MCP (`user-Apify`)
- Scrape competitor titles for similar products
- Identify keyword gaps
- Add competitive analysis section to reports

#### D. MAPI-Docs MCP (`user-MAPI-Docs`)
- Validate output against current GMC specifications
- Query for any new requirements

**Implementation notes:**
- Make all MCP integrations optional (graceful degradation)
- Check server status before calling
- Log when servers are unavailable but continue processing

---

### Issue 8: Strengthen Claim Verification

**Current problem**: Some outputs have hallucinated content (e.g., "Solid Brass" when material is "Iron")

**Fixes in** `src/feedops/pipeline/verifier.py`:

1. Add strict mode that does exact string matching
2. Add material consistency check - verify material claims against actual Material field
3. Cross-reference with product image if available
4. Reject any claim not directly traceable to source data

---

## Updated Prompt Template

Replace the content in `src/feedops/pipeline/prompts.py` with a prompt that incorporates:

1. Image analysis instructions (verify visual characteristics)
2. Brand placement logic based on recognition (Allied Brass = benefits first)
3. 30-70 character priority zone for titles
4. Platform-specific output requirements (Google, Bing, Shopify)
5. Explicit prohibition of source citations in output text
6. Search term integration (if available from Google Ads MCP)
7. Unified research approach: both title AND description are critical outputs

---

## Verification Checklist

Before claiming ANY task complete, verify by running actual commands:

### Environment Setup
```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
uv pip install -e ".[dev]"
```

### Run Tests
```bash
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v --tb=short
```
- [ ] All tests pass (should be more than 48 after adding new tests)

### Run Healthcheck
```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main healthcheck
```
- [ ] All checks pass

### Test with Real SKU
```bash
PYTHONPATH=./src .venv/bin/python -c "
from dotenv import load_dotenv
load_dotenv()
import asyncio
from feedops.pipeline.optimize import optimize_parent_sku

result = asyncio.run(optimize_parent_sku(
    master_sku='101',
    catalog_path='data/catalog/Product Catalog.csv',
    dry_run=True,
))
print('Score:', result.candidate.final_score.composite)
"
```

### Verify Outputs
- [ ] Descriptions contain NO source citations (no `catalog_csv.` text)
- [ ] Reports show the full evidence table sent to LLM
- [ ] Reports show product image URL (if available)
- [ ] Platform-specific outputs exist (Google, Bing, Shopify)
- [ ] `short_title` field is populated
- [ ] Material claims match actual CSV data exactly
- [ ] Brand placement follows recognition-based logic

---

## Deliverables

1. **Updated code files** with all fixes
2. **New tests** for:
   - Image input handling
   - Platform-specific output generation
   - Source citation rejection
   - MCP integration (mocked)
3. **Updated verification report** at `reports/verification-report.md`
4. **Commit** with message: `feat: complete FeedOps overhaul with image input, platform outputs, and MCP integration`

---

## Priority Order

If time is limited, implement in this order:

1. **Fix source citation leakage** (critical bug)
2. **Add image input to LLM** (prevents hallucinations)
3. **Update title logic per YouTube insights** (immediate performance impact)
4. **Add LLM input to reports** (debugging/transparency)
5. **Platform-specific outputs** (feature enhancement)
6. **MCP integrations** (nice to have)

---

## Important Rules to Follow

1. **AGENTS.md** - The no-hallucination rule is CRITICAL
2. **Use Context7** - Check for latest library versions before implementing
3. **Python environment** - Always use `PYTHONPATH=./src` pattern
4. **Verify before claiming** - Run actual tests and show output
5. **Document decisions** - Add comments explaining non-obvious choices
