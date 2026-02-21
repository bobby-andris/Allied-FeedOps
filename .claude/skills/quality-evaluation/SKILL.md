---
name: quality-evaluation
description: Evaluate generated product content quality using a rubric that measures what actually drives clicks and conversions, not just compliance. Replaces the current self-scoring system that gives 81% to bad descriptions.
---

# Quality Evaluation Skill

Evaluate Allied Brass generated product content using a performance-oriented rubric. This skill measures whether content would make a shopper click — not whether it followed the rules.

## When to Use

- After generating content via the pipeline, to validate quality before approval
- When reviewing existing `candidate_content` in the `generated_content` table
- When comparing content versions (before/after prompt changes)
- When creating gold standard examples for the `prompt_templates` table
- When the `quality-evaluation` skill is referenced by other skills (e.g., `quality_rubric.yaml`)

## Why the Current Scoring Fails

The pipeline's `self_score` in `prompts.py` uses 6 criteria:

| Current Criterion | What It Measures | The Problem |
|---|---|---|
| `specificity` | Does it mention specific product details? | Listing specs ≠ compelling copy. "18-inch center-to-center" scores high but reads like a database export. |
| `benefit_coverage` | Are product benefits mentioned? | "Provides space-efficient towel storage" is technically a benefit but is generic and forgettable. |
| `keyword_inclusion` | Are search keywords present? | Rewards keyword stuffing. "towel rack... towel storage... wall mounted towel rack... ladder towel bar" scores perfectly. |
| `format_adherence` | Does it follow structural rules? | Scores 10/10 for following the `shopping_intelligence.yaml` template literally — which CAUSES the robotic output. |
| `brand_voice` | Does it sound like the brand? | Scores 9/10 for any description that avoids banned words and uses "solid brass." No positive voice definition. |
| `factual_accuracy` | Are claims verifiable? | Important but binary — either accurate or not. Inflates scores when weighted equally with quality criteria. |

**The result**: A description like this scores 81%:

> ladder towel rack for bathroom installation. {FINISH_SENTENCE} Solid brass. 18-inch center-to-center. Wall-mounted, 4-tier vertical ladder design provides space-efficient towel storage with four horizontal bars at varying heights...

This is bad content that scores well because:
- **format_adherence** (10/10): Perfectly follows "[Product Type] for bathroom installation. {FINISH_SENTENCE}. [Material]. [Dimension]."
- **brand_voice** (9/10): Avoids banned words, mentions solid brass
- **factual_accuracy** (8/10): All claims are verifiable
- **keyword_inclusion** (8/10): "towel rack," "towel storage," "towel bar," "wall mounted" all present

**What's missing entirely:**
- Does the opening hook make you want to read more? (No — it's a fragment)
- Could this describe only THIS product? (No — any ladder towel bar)
- Why should I buy THIS over a $40 Amazon alternative? (No answer)
- Does it connect to my actual life? (No scenario, no emotion)
- Is this description noticeably different from the 500 other descriptions in the catalog? (No — same pattern)

## The New Quality Framework (10 Criteria)

### 1. Hook Quality (Weight: 15%)

Does the opening sentence make you want to read more? In Google Shopping, the first ~100 characters are visible before truncation. This is the most CTR-impactful element.

| Score | Anchor | Example |
|---|---|---|
| 0-2 | Fragment or keyword dump | "ladder towel rack for bathroom installation." |
| 3-4 | Complete sentence but generic | "This towel bar is made from solid brass." |
| 5-6 | Correct and clear but no pull | "This 18-inch wall-mounted towel bar adds traditional style to your bathroom." |
| 7-8 | Identifies product with context | "Organize your family's towels on four staggered bars — all within 18 inches of wall space." |
| 9-10 | Specific, engaging, creates curiosity | "Four solid brass bars at different heights let everyone grab their own towel without the pile-up — this 18-inch ladder design fits beside the shower where you need it most." |

**Key test**: Read just the first sentence. Would you click to learn more, or scroll past?

### 2. Product Specificity (Weight: 15%)

Could this description ONLY describe this exact product? Or could you swap in any competitor's product and it would still work?

| Score | Anchor | Example |
|---|---|---|
| 0-2 | Could describe any towel bar | "A towel bar for your bathroom. Solid brass construction." |
| 3-4 | Mentions brand but still generic | "Allied Brass towel bar with solid brass construction and concealed mounting." |
| 5-6 | Mentions collection/dimensions | "Skyline Collection 18-inch towel bar with solid brass and concealed screw mounting." |
| 7-8 | Unique details that narrow to THIS product | "The Carolina Collection's ladder design stacks four horizontal bars at graduated heights on a single 18-inch wall mount." |
| 9-10 | Unmistakably this product | "Carolina Collection 4-tier ladder towel bar — four solid brass bars graduate upward from 5 to 20 inches, turning 18 inches of wall space into organized storage for bath sheets down to hand towels." |

**Key test**: Could a competitor copy-paste this description for their product? If yes, score ≤5.

### 3. Competitive Differentiation (Weight: 12%)

Does it explain why THIS product over the $40 Amazon alternative or the Kingston Brass equivalent?

| Score | Anchor | Example |
|---|---|---|
| 0-2 | No differentiation | "Wall-mounted towel bar. Solid brass." |
| 3-4 | Generic quality claims | "Made from solid brass for durability." |
| 5-6 | Mentions advantage but generically | "Solid brass construction resists corrosion better than die-cast zinc alternatives." |
| 7-8 | Clear advantage woven into narrative | "Solid brass bars won't flex under wet towels the way hollow zinc alternatives do — and the concealed mounting hardware means no visible screws to corrode." |
| 9-10 | Competitive advantage feels like a natural selling point | "While most ladder towel bars use hollow tubes that flex and show water spots, these solid brass bars keep their shape and finish for the life of your bathroom — backed by Allied Brass's lifetime warranty." |

**Key test**: After reading, do you understand why this costs more than alternatives?

### 4. Keyword Integration (Weight: 10%)

Are search terms included naturally, or are they stuffed in awkwardly?

| Score | Anchor | Example |
|---|---|---|
| 0-2 | No keywords OR obvious stuffing | "towel rack towel bar towel holder wall mounted towel storage bathroom towel organizer" |
| 3-4 | Keywords present but jarring | "This towel bar is a wall mounted towel rack for bathroom towel storage." |
| 5-6 | Keywords present, mildly awkward | "This wall-mounted towel bar provides towel storage in your bathroom." |
| 7-8 | Natural integration, good variety | "Mount this solid brass towel bar beside the shower for everyday towel storage — the ladder design doubles as a decorative bathroom accent." |
| 9-10 | Keywords invisible, copy flows | "Hang bath towels, hand towels, and washcloths on four staggered bars that turn a narrow wall into an organized drying station." |

**Key test**: Read it aloud. Do you stumble on any phrase that sounds like it was inserted for SEO rather than for the reader?

### 5. Customer Scenario (Weight: 10%)

Does it connect to a real buying situation? 85% of shoppers say product information influences buying decisions. Scenarios make abstract features concrete.

| Score | Anchor | Example |
|---|---|---|
| 0-2 | Pure spec dump | "18-inch. Solid brass. Wall-mounted. 20 lb capacity. Concealed screws." |
| 3-4 | Generic "upgrade your bathroom" | "Upgrade your bathroom with this solid brass towel bar." |
| 5-6 | Vague scenario | "Keep your towels organized and within reach." |
| 7-8 | Relatable but common | "Perfect for a bathroom renovation where you want fixtures that match and last." |
| 9-10 | Specific scenario that resonates | "Renovating a guest bath? The four-bar ladder design lets you set out fresh towels for visitors without a bulky freestanding rack taking up floor space." |

**Key test**: Can the reader see themselves using this product in their actual home?

### 6. Emotional Resonance (Weight: 10%)

Does it make you FEEL something about owning this product? Not hype — genuine desire, confidence, or satisfaction.

| Score | Anchor | Example |
|---|---|---|
| 0-2 | Reads like a database export | "Towel bar. Brass. 18 inches. Wall mount." |
| 3-4 | Technically correct, zero feeling | "This towel bar is designed in a traditional style." |
| 5-6 | Pleasant but forgettable | "This towel bar adds a nice touch to your bathroom." |
| 7-8 | Creates mild desire | "The kind of bathroom hardware you notice when everything in the room just works together." |
| 9-10 | Creates genuine desire or confidence | "There's a quiet satisfaction in a bathroom where the towel bar matches the robe hook, the toilet paper holder, and the shower door handle — the Carolina Collection makes that coordination effortless." |

**Key test**: After reading, do you want this product slightly more than before? If the answer is neutral, score ≤5.

### 7. Factual Accuracy (Weight: 10%)

Are all claims verifiable from the evidence table? This is binary with a gradient for severity.

| Score | Anchor |
|---|---|
| 10 | All claims verifiable from evidence. No fabricated specs, dimensions, certifications, or features. |
| 7-9 | Minor inference that's reasonable (e.g., "ideal for modern bathrooms" when style evidence says "contemporary"). |
| 3-6 | Unverifiable claims that could be true (e.g., claiming "ADA compliant" without evidence). |
| 0-2 | Fabricated specifications, invented dimensions, or false certifications. |

**Key test**: Can you trace every factual claim to a row in the evidence table?

### 8. Platform Compliance (Weight: 8%)

Does it meet platform-specific requirements? This is the baseline — necessary but not sufficient.

| Platform | Requirements |
|---|---|
| **Google Shopping** | Plain text only. Title 60-150 chars, product type in first 30 chars, brand as final segment. Description 600-800 chars target. No HTML. |
| **Bing Shopping** | Plain text only. Similar to Google but 700-1000 chars target. Synonym coverage. |
| **Shopify** | HTML allowed. Starts with `<p>`, uses `<ul><li>` for benefits. Meta description 140-155 chars. No brand in title. |

| Score | Anchor |
|---|---|
| 10 | Meets all platform requirements perfectly. |
| 7-9 | Minor issues (slightly over/under length targets). |
| 4-6 | Significant issues (wrong format, missing required elements). |
| 0-3 | Wrong platform format entirely (HTML in Google, plain text in Shopify). |

### 9. Finish Integration (Weight: 5%)

Is the finish described naturally and compellingly? Allied Brass products come in 25+ finishes — the finish is a design decision, not an afterthought.

| Score | Anchor | Example |
|---|---|---|
| 0-2 | Raw placeholder or broken template | "{FINISH_SENTENCE}" or "Available in Antique Brass." |
| 3-4 | Finish mentioned but disconnected | "Antique Brass. This towel bar is made from solid brass." |
| 5-6 | Finish present, generic framing | "This towel bar comes in Antique Brass for a traditional look." |
| 7-8 | Finish as design choice | "The Antique Brass finish brings warm, aged character that pairs naturally with oil-rubbed bronze faucets and vintage-inspired tile." |
| 9-10 | Finish woven into the narrative | "In Antique Brass, the Carolina Collection's ladder design becomes a statement piece — the warm, aged patina draws the eye upward and gives your bathroom the character of a well-curated boutique hotel." |

**Note on {FINISH_SENTENCE} placeholders**: During master-SKU generation, `{FINISH_SENTENCE}` is expected and should NOT be penalized. Score finish integration based on the structural setup — does the placeholder sit naturally in the flow? Will the expanded sentence read well? If evaluating variant-expanded content, score the actual finish language.

### 10. Variety Score (Weight: 5%)

Is this description noticeably different from others in the catalog? Monotony is a catalog-level quality problem — when every description follows the same pattern, the brand feels robotic.

| Score | Anchor |
|---|---|
| 0-2 | Identical sentence structure and pattern to other descriptions (e.g., every description opens with "This [product type] [verb] [generic benefit]"). |
| 3-4 | Different words but same skeleton ("This X provides Y. {FINISH_SENTENCE} Crafted from solid brass..."). |
| 5-6 | Some structural variation but predictable overall. |
| 7-8 | Noticeably different opening, structure, or narrative approach from catalog peers. |
| 9-10 | Unique voice and structure — could not be confused with another product's description by pattern alone. |

**Key test**: Put 5 descriptions side by side. Can you tell them apart by structure alone (not just product details)?

## Scoring Methodology

### Weighted Average Calculation

```
Overall = (Hook * 0.15) + (Specificity * 0.15) + (Differentiation * 0.12)
        + (Keywords * 0.10) + (Scenario * 0.10) + (Emotion * 0.10)
        + (Accuracy * 0.10) + (Compliance * 0.08) + (Finish * 0.05)
        + (Variety * 0.05)
```

### Grade Thresholds

| Grade | Score Range | Meaning | Action |
|---|---|---|---|
| **Reject** | 0-59 | Content would hurt brand perception or CTR | Block from approval. Regenerate with specific feedback. |
| **Needs Work** | 60-74 | Functional but generic — no competitive advantage | Flag for revision. Identify top 2 weaknesses. |
| **Acceptable** | 75-84 | Solid content that won't embarrass the brand | Approve for low-priority SKUs. Improve for high-value SKUs. |
| **Good** | 85-94 | Compelling content that differentiates the product | Approve. Consider as near-gold-standard. |
| **Excellent** | 95-100 | Best-in-class — would outperform competitors | Approve and flag as gold standard example for this category. |

### Comparison to Old Scoring

Under the old rubric, the CL-28-18 description scored ~81% (Specificity 7.8, Benefit Coverage 7.5, Keyword Inclusion 8, Format Adherence 10, Brand Voice 9, Factual Accuracy 8).

Under this rubric, the same description scores:

| Criterion | Score | Reason |
|---|---|---|
| Hook Quality | 2 | Fragment opening — "ladder towel rack for bathroom installation" |
| Product Specificity | 4 | Mentions 4-tier and 18-inch but could describe any manufacturer's product |
| Competitive Differentiation | 1 | Zero differentiation — no reason to choose this over alternatives |
| Keyword Integration | 3 | Obvious stuffing — "towel rack... towel storage... wall mounted towel rack... ladder towel bar" |
| Customer Scenario | 1 | Pure spec dump — no human context whatsoever |
| Emotional Resonance | 1 | Reads like a database export |
| Factual Accuracy | 9 | All claims verifiable (minor deduction: "traditional style" is interpretive) |
| Platform Compliance | 8 | Correct format, reasonable length |
| Finish Integration | 2 | Raw {FINISH_SENTENCE} placeholder with no setup |
| Variety Score | 2 | Identical pattern to every other description in the catalog |

**New score: 31/100 (Reject)** vs old score 81/100.

The 50-point gap is the difference between measuring compliance and measuring quality.

## Evaluation Process

Follow these steps when evaluating generated content:

### Step 1: Read Cold
Read the description without looking at the product data. What's your gut reaction?
- Would you click this listing on Google Shopping?
- Does it tell you something interesting about the product?
- Does it feel like a human wrote it or a template filled it in?

### Step 2: Score Each Criterion Independently
Go through all 10 criteria using the anchors above. Score each 0-10. Do NOT adjust scores to hit a target — let the number fall where it falls.

### Step 3: Calculate Weighted Score
Apply the weights. Record the overall score and grade.

### Step 4: Identify #1 Weakness and #1 Strength
- **Weakness**: The single criterion dragging the score down most. This is where revision effort should focus.
- **Strength**: What the description does well. Preserve this in revision.

### Step 5: Generate Specific Improvement Suggestions
For each criterion scoring below 7, provide:
- What's wrong (specific quote from the description)
- What it should say instead (concrete rewrite of that section)
- Why the change matters (connection to CTR/conversion)

### Step 6: Compare Against Category Standard
If gold standard examples exist for this category in `prompt_templates`, compare structure and quality. If no gold standard exists, note this as a gap.

## Bad-to-Good Examples

### Example 1: Towel Ring (SKU 1016, Towel Rings)

**Original** (Old score: 87, New score: 42):
> This 6-inch wall-mounted towel ring provides a secure hand towel holder for everyday bathroom use. {FINISH_SENTENCE} Crafted from solid brass, it resists corrosion better than common die-cast zinc alternatives and supports up to 10 lb. The round ring design is ideal for decorative towels or daily hand towels, while the compact 1.5-inch projection helps keep the space feeling open. Concealed screw mounting hardware creates a clean, finished look once installed, and all installation hardware is included. Part of the Skyline Collection for a coordinated traditional bathroom hardware look. Backed by a limited lifetime warranty.

**Criterion breakdown**:
- Hook: 4 (complete sentence but "provides a secure hand towel holder for everyday bathroom use" is generic)
- Specificity: 5 (mentions Skyline Collection, 6-inch, but pattern is interchangeable)
- Differentiation: 5 (mentions solid brass vs zinc — good — but generically)
- Keywords: 5 (towel ring, hand towel holder — present but slightly forced)
- Scenario: 3 ("everyday bathroom use" is barely a scenario)
- Emotion: 2 (no feeling at all)
- Accuracy: 9 (all verifiable)
- Compliance: 8 (good format and length)
- Finish: 3 ({FINISH_SENTENCE} dropped in after the opener with no setup)
- Variety: 3 (same "This [size] [mount] [product] provides..." pattern)

**What's wrong**: Opens with the most generic possible sentence. "Provides a secure hand towel holder for everyday bathroom use" — what towel ring doesn't? No scenario, no emotion, no reason to choose this one.

**Improved version** (New score: 78):
> Keep a fresh hand towel within arm's reach of the vanity without cluttering the counter — this 6-inch solid brass towel ring projects just 1.5 inches from the wall, holding up to 10 lb while taking up almost no visual space. {FINISH_SENTENCE} Unlike die-cast zinc rings that corrode in humid bathrooms, solid brass keeps its finish and strength for the long haul, backed by a limited lifetime warranty. Part of the Skyline Collection, so it coordinates with towel bars, robe hooks, and tissue holders in the same finish across your bathroom.

**What changed**: Opens with a use scenario (hand towel by the vanity). Leads with the compact size as a benefit, not a spec. Differentiates against zinc competitors naturally. Collection coordination framed as a practical benefit.

---

### Example 2: Cabinet Knob (SKU 102, Cabinet Hardware)

**Original** (Old score: 84, New score: 38):
> This 1-1/2 inch cabinet knob adds an elegant, modern accent to kitchen or bathroom cabinetry. {FINISH_SENTENCE} Crafted from solid brass, it delivers lasting durability and a substantial feel compared with lightweight, plated alternatives. Cabinet-mount design installs easily with included installation hardware—no assembly required. The 1.5 x 1.5 inch knob offers a comfortable grip, with a 2.25 inch projection for easy pull and control on drawers and doors. A simple update that helps your space look intentional, and coordinates well with traditional bathroom hardware. Backed by a limited lifetime warranty.

**Criterion breakdown**:
- Hook: 3 ("adds an elegant, modern accent" is the most generic possible cabinet knob opener)
- Specificity: 4 (dimensions present but description could be any brass knob)
- Differentiation: 4 ("substantial feel compared with lightweight, plated alternatives" — decent but vague)
- Keywords: 5 (cabinet knob, drawers and doors — reasonable)
- Scenario: 3 ("simple update that helps your space look intentional" is almost a scenario)
- Emotion: 3 ("substantial feel" hints at tactile quality but doesn't develop it)
- Accuracy: 9 (verifiable)
- Compliance: 8 (good format)
- Finish: 3 ({FINISH_SENTENCE} placeholder, no integration)
- Variety: 3 (same pattern as every other product)

**Improved version** (New score: 75):
> You notice a cabinet knob every time you open a drawer — this 1-1/2 inch solid brass knob has the weight and resistance of quality hardware, not the hollow rattle of plated zinc. {FINISH_SENTENCE} The round profile fits comfortably under your fingers with 2.25 inches of projection for a clean pull on cabinet doors and drawers. Single-bolt installation takes five minutes per knob, and the solid brass won't loosen over years of daily use the way lightweight alternatives do. Swap out a kitchen's worth of knobs in an afternoon for a finish that coordinates across your entire room.

**What changed**: Opens with a sensory hook (you notice it every time). Differentiates on tactile quality (weight vs hollow rattle). Frames installation as easy weekend project. Practical coordination benefit.

---

### Example 3: Robe Hook (SKU 1020, Robe Hooks)

**Original** (Old score: 90, New score: 45):
> This wall-mounted robe hook from the Skyline Collection provides convenient hanging space for robes and towels in the bathroom. {FINISH_SENTENCE} Crafted from solid brass for durability, it features concealed screw mounting for a clean, refined look. In, it coordinates easily with darker fixtures and traditional bathroom hardware while keeping your space looking intentional. Compact size measures 2.8 in L x 2.3 in W with a 2.3 in projection and 3.6 in height—ideal beside the shower, vanity, or door. Includes the robe hook and all installation hardware (no assembly required). Supports up to 2 lb. Backed by a limited lifetime warranty.

**Criterion breakdown**:
- Hook: 3 ("provides convenient hanging space" — could describe a nail in the wall)
- Specificity: 5 (Skyline Collection, dimensions — but generic narrative)
- Differentiation: 2 (no reason to choose this over any hook)
- Keywords: 5 (robe hook, robes and towels — fine)
- Scenario: 4 ("beside the shower, vanity, or door" — placement suggestion is almost a scenario)
- Emotion: 2 (no feeling)
- Accuracy: 7 ("In, it coordinates" appears to have a broken finish placeholder — deduction)
- Compliance: 7 (broken sentence fragment "In, it coordinates")
- Finish: 2 (broken — "In, it coordinates" suggests missing finish name)
- Variety: 3 (same template pattern)

**Note**: This scored 90 under the old rubric despite having a BROKEN SENTENCE ("In, it coordinates") — demonstrating how compliance-focused scoring misses actual quality issues.

**Improved version** (New score: 76):
> Hang your robe where you'll actually reach for it — beside the shower, behind the bathroom door, or next to the vanity. {FINISH_SENTENCE} This Skyline Collection robe hook holds up to 2 lb on a compact 2.3-inch projection that won't crowd narrow spaces. Solid brass means the hook keeps its shape even with a heavy terry robe, and concealed screw mounting gives you a clean wall with no visible hardware. Coordinates with Skyline towel bars, tissue holders, and towel rings for a pulled-together bathroom. Lifetime warranty included.

**What changed**: Opens with a use scenario (where you'd put it). Leads with the benefit of compact size. Weight capacity framed practically (heavy robe). Collection as coordination benefit.

---

### Example 4: 3-Position Multi Hook (SKU 1020-3, Multi Hooks)

**Original** (Old score: 98, New score: 44):
> This 3-inch wall-mounted 3 position multi hook from the Skyline Collection adds compact hanging storage in the bathroom. {FINISH_SENTENCE} Crafted from solid brass for durability and backed by a limited lifetime warranty. Three hooks keep robes, towels, and clothing organized in one space-saving fixture, and it also works well as a tie and belt rack. Concealed screw mounting hardware delivers a clean, traditional look and straightforward installation with included hardware (no assembly required). The designer finish is corrosion-resistant and rust-resistant to maintain its appearance over time, coordinating easily with traditional bathroom hardware.

**Criterion breakdown**:
- Hook: 3 ("adds compact hanging storage" — functional but zero pull)
- Specificity: 5 (3-position, Skyline — but generic)
- Differentiation: 2 (nothing about why this multi hook over others)
- Keywords: 5 (multi hook, tie and belt rack — decent keyword variety)
- Scenario: 5 ("tie and belt rack" is a nice use-case expansion — partial credit)
- Emotion: 2 (no feeling)
- Accuracy: 9 (verifiable)
- Compliance: 8 (good format)
- Finish: 3 ({FINISH_SENTENCE} with no context)
- Variety: 3 (same pattern)

**This scored 98 under the old rubric** — nearly perfect — despite being generic, emotionless content with no differentiation. This is the clearest evidence that the old rubric measures the wrong things.

**Improved version** (New score: 79):
> Three solid brass hooks on a single 3-inch mount — hang a robe, a towel, and a washcloth without drilling three separate holes. {FINISH_SENTENCE} The Skyline Collection multi hook works in the bathroom, but also doubles as a tie and belt organizer inside a closet door. At just 3 inches wide, it fits spaces where individual hooks won't — between a door frame and a light switch, beside the shower in a narrow bath, or on the back of a cabinet door. Concealed screws, solid brass that won't corrode, and a lifetime warranty. Coordinates with the full Skyline Collection lineup.

**What changed**: Opens with the key value proposition (3 hooks, 1 mount, fewer holes). Dual-use framed concretely (closet door). Narrow-space benefit made vivid with real locations.

---

### Example 5: Toilet Paper Holder (SKU 1024, Toilet Paper Holders)

**Original** (Old score: 83, New score: 40):
> This wall-mounted toilet tissue holder is crafted from solid brass and backed by a limited lifetime warranty. {FINISH_SENTENCE} It brings a warm, classic look that complements modern bathroom hardware. The two-post, open design makes roll changes quick and easy—so empty rolls don't linger. Concealed screw mounting hardware keeps the installation clean and secure while saving space on bathroom surfaces. From the Skyline Collection with an elegant, timeless motif. Includes the toilet paper holder and all installation hardware. Available in a wide variety of lifetime designer finishes, including statement colors, to coordinate across your bath.

**Criterion breakdown**:
- Hook: 2 ("crafted from solid brass and backed by a limited lifetime warranty" — leads with warranty?!)
- Specificity: 4 (two-post, open design, Skyline — but generic)
- Differentiation: 2 (no competitive advantage)
- Keywords: 5 (toilet tissue holder, toilet paper holder — both present)
- Scenario: 4 ("empty rolls don't linger" is a mini-scenario — partial credit)
- Emotion: 3 ("warm, classic look" — mild but undeveloped)
- Accuracy: 9 (verifiable)
- Compliance: 8 (format OK)
- Finish: 3 (placeholder)
- Variety: 3 (same pattern again)

**Improved version** (New score: 77):
> No more fumbling with a spring-loaded roller — this two-post toilet paper holder lets you swap rolls with one hand. {FINISH_SENTENCE} Solid brass construction means the posts stay rigid (no wobble after six months like plastic-core holders), and concealed screw mounting keeps the wall clean. Part of the Skyline Collection, so it matches your towel bar, robe hook, and shower accessories in the same finish. Wall-mounted to keep your bathroom surfaces clear. Lifetime warranty included.

**What changed**: Opens with the product's actual UX advantage (no spring roller). Differentiates against plastic-core competitors. Practical one-hand scenario. Collection coordination as practical matching benefit.

---

### Example 6: Paper Towel Holder (SKU 1025U, Paper Towel Holders)

**Original** (Old score: 88, New score: 35):
> Wall-mounted paper towel holder with a 15-inch height and 5-inch projection, crafted from solid brass for durable everyday kitchen use. {FINISH_SENTENCE} The concealed screw mounting hardware provides a clean look and straightforward installation, and the wall-mount design keeps countertops clear and clutter free. Finished in and available in a wide variety of lifetime designer finishes to coordinate with your kitchen décor. Includes the paper towel holder and all installation hardware, backed by a Limited Lifetime Warranty.

**Criterion breakdown**:
- Hook: 1 (opens with "Wall-mounted paper towel holder with a 15-inch height" — a spec sheet header)
- Specificity: 3 (15-inch, 5-inch projection, but utterly generic)
- Differentiation: 1 (zero — why not buy any paper towel holder?)
- Keywords: 4 (paper towel holder repeated, basic)
- Scenario: 3 ("keeps countertops clear" — barely)
- Emotion: 1 (database export energy)
- Accuracy: 7 ("Finished in and available in" — broken sentence, missing finish name)
- Compliance: 6 (broken sentence fragment)
- Finish: 1 ("Finished in and available in" — clearly broken template)
- Variety: 2 (worst example of the template pattern)

**Note**: Another case where the old rubric gave 88% to content with a BROKEN SENTENCE.

**Improved version** (New score: 74):
> Free up counter space by moving your paper towels to the wall — this solid brass holder keeps a full roll at tearing height with a 5-inch projection that won't crowd your backsplash. {FINISH_SENTENCE} Unlike flimsy suction-cup or adhesive holders, concealed screw mounting holds firmly through years of one-handed tears. The 15-inch height accommodates jumbo rolls without the holder looking oversized. Coordinates with Skyline Collection kitchen and bar accessories for a consistent hardware finish across the room. Lifetime warranty.

**What changed**: Opens with the benefit (counter space). Differentiates against suction/adhesive alternatives. "One-handed tears" is a real use moment. Jumbo roll compatibility framed as a practical detail.

---

### Example 7: Tumbler & Toothbrush Holder (SKU 1026, Tumbler Toothbrush Holders)

**Original** (Old score: 89, New score: 48):
> This wall-mounted tumbler and toothbrush holder adds organized countertop-free storage in the bathroom. {FINISH_SENTENCE} Crafted from solid brass, it provides a sturdy, rust-resistant place for a tumbler and toothbrushes. Skyline Collection twist accents bring traditional, refined style that complements classic bath accessories. Measures 4.5 in L x 3.5 in W x 2.9 in H with a 5 in projection for practical everyday reach. Concealed screw mounting hardware creates a clean look, and all installation hardware is included—no assembly required. Available in 28 designer lifetime finishes, including statement colors, to coordinate with traditional bathroom hardware. Backed by a limited lifetime warranty.

**Criterion breakdown**:
- Hook: 4 ("adds organized countertop-free storage" — functional, not compelling)
- Specificity: 6 (Skyline twist accents, 28 finishes — more specific than most)
- Differentiation: 3 ("rust-resistant" — weak differentiator)
- Keywords: 5 (tumbler and toothbrush holder — present)
- Scenario: 4 ("countertop-free" hints at the mess problem but doesn't develop it)
- Emotion: 3 ("refined style" is mild)
- Accuracy: 9 (verifiable, "28 finishes" is specific)
- Compliance: 8 (good)
- Finish: 3 (placeholder)
- Variety: 3 (same pattern)

**Improved version** (New score: 77):
> Get toothbrushes and the rinse cup off your vanity counter — this wall-mounted holder keeps them at arm's reach without the puddle. {FINISH_SENTENCE} The Skyline Collection's signature twist accent gives it more character than a plain chrome holder, and solid brass won't corrode even right beside the sink where water splashes constantly. Measures 4.5 x 3.5 inches with a 5-inch projection — big enough for a standard tumbler and four toothbrushes. Available in 28 designer finishes, from matte black to antique copper, to match your faucet and other hardware. Lifetime warranty.

**What changed**: Opens with the universal bathroom annoyance (cluttered counter, water puddle). Twist accent framed as a visual differentiator. Splash resistance as a practical benefit. 28 finishes made concrete with examples.

---

### Example 8: 18-Inch Towel Bar (SKU 1031/18, Towel Bars)

**Original** (New score: 52):
> This 18-inch wall-mounted towel bar adds traditional style to your bathroom while keeping towels within easy reach. {FINISH_SENTENCE} Crafted from solid brass to resist rust in humid spaces, it holds up to 20 lb of wet towels without sagging. The straight 0.5-inch diameter bar provides a clean, refined profile that complements classic bath accessories. Concealed screw mounting hardware keeps the installation looking neat, and mounting plates plus all installation hardware are included. Designed for easy assembly-free installation and backed by a limited lifetime warranty, it's a durable way to coordinate your bathroom with traditional bathroom hardware.

**Criterion breakdown**:
- Hook: 5 (complete sentence, but "adds traditional style" is generic)
- Specificity: 5 (0.5-inch diameter, 20 lb — good specs but generic framing)
- Differentiation: 5 ("resist rust in humid spaces" + "20 lb without sagging" — decent)
- Keywords: 6 (towel bar, towels — naturally placed)
- Scenario: 4 ("within easy reach" — barely)
- Emotion: 3 ("traditional style" — mild)
- Accuracy: 9 (verifiable)
- Compliance: 8 (good)
- Finish: 3 (placeholder)
- Variety: 4 (slightly better — mentions bar diameter)

**This is actually the best of the originals** — it has real differentiation (20 lb, 0.5-inch diameter) woven in somewhat naturally. But it still follows the template and lacks a scenario or emotional pull.

---

### Example 9: 24-Inch Towel Bar (SKU 1031/24, Towel Bars)

**Original** (New score: 43):
> This 24-inch wall-mounted towel bar provides everyday towel storage with solid brass construction and a limited lifetime warranty. {FINISH_SENTENCE} The Skyline Collection straight bar design complements modern and traditional bathroom hardware and keeps towels neatly displayed without crowding the room. Solid brass resists rust in humid bathrooms and supports up to 10 lb for wet bath towels. Concealed screw mounting hardware keeps the look clean on the wall. Includes the towel bar, mounting plates, and all installation hardware; no assembly required. Available in a wide variety of designer finishes for coordinated bathroom décor.

**Criterion breakdown**:
- Hook: 3 ("provides everyday towel storage with solid brass construction and a limited lifetime warranty" — leads with warranty again)
- Specificity: 4 (24-inch, Skyline, but template language)
- Differentiation: 3 ("resists rust" — minimal)
- Keywords: 5 (towel bar, towel storage, bath towels — present)
- Scenario: 3 ("keeps towels neatly displayed" — barely)
- Emotion: 2 (no feeling)
- Accuracy: 9 (verifiable)
- Compliance: 8 (format OK)
- Finish: 3 (placeholder)
- Variety: 2 (nearly identical structure to the 18-inch version — catalog monotony)

**Key insight**: Compare this to SKU 1031/18 above. Two towel bars from the SAME COLLECTION in different sizes should NOT have nearly identical descriptions. The variety score for the catalog as a whole suffers when every product reads the same.

---

### Example 10: Ladder Towel Bar (SKU CL-28-18, Towel Bars) — The Case Study

**Original** (Old score: 81, New score: 31):
> ladder towel rack for bathroom installation. {FINISH_SENTENCE} Solid brass. 18-inch center-to-center. Wall-mounted, 4-tier vertical ladder design provides space-efficient towel storage with four horizontal bars at varying heights. This wall mounted towel rack uses concealed screw mounting hardware for a clean look, and includes the ladder towel bar plus all installation hardware. Designed in a traditional style, it supports up to 20 lb and is offered in a wide variety of lifetime designer finishes. Backed by a Limited Lifetime Warranty.

This is the description that triggered the entire content quality reassessment. See the full scoring breakdown in the "Comparison to Old Scoring" section above.

**Improved version** (New score: 82):
> Four solid brass bars at different heights let everyone in the house grab their own towel — this 18-inch ladder design from the Carolina Collection fits beside a shower or tub without eating wall space. {FINISH_SENTENCE} The staggered bars hold bath sheets on top and hand towels below, supporting up to 20 lb total without the flex you get from hollow-tube alternatives. Concealed screw mounting means nothing visible but the ladder itself — clean lines, no exposed hardware. The Carolina Collection includes matching towel rings, robe hooks, and tissue holders for a coordinated bathroom that looks intentional, not assembled from whatever was on sale. Lifetime warranty on every finish.

**What changed**: Opens with the unique product benefit (four bars, everyone gets their own). Size framed as a space benefit. Weight capacity compared to hollow competitors. Collection framed as "intentional vs assembled from sales" — an emotional hook that resonates with the buyer who cares about design.

## Output Format

When evaluating content, produce this structured output:

```
## Quality Evaluation: [SKU] ([Category])

### Content Evaluated
> [The full description being evaluated]

### Scores
| Criterion | Score | Weight | Weighted |
|---|---|---|---|
| Hook Quality | X/10 | 15% | X.XX |
| Product Specificity | X/10 | 15% | X.XX |
| Competitive Differentiation | X/10 | 12% | X.XX |
| Keyword Integration | X/10 | 10% | X.XX |
| Customer Scenario | X/10 | 10% | X.XX |
| Emotional Resonance | X/10 | 10% | X.XX |
| Factual Accuracy | X/10 | 10% | X.XX |
| Platform Compliance | X/10 | 8% | X.XX |
| Finish Integration | X/10 | 5% | X.XX |
| Variety Score | X/10 | 5% | X.XX |
| **Overall** | | | **XX.X/100** |

### Grade: [Reject/Needs Work/Acceptable/Good/Excellent]

### Top Strength
[What the description does best — preserve this in revision]

### Top Weakness
[The single biggest issue — focus revision here]

### Improvement Suggestions
1. **[Criterion]**: [Specific quote] -> [Specific rewrite] (Why: [CTR/conversion impact])
2. ...

### Suggested Rewrite
> [Full improved description if score < 75]
```

## Integration Points

This skill should be used by:
- **Pipeline self-scoring**: Replace the 6-criterion `self_score` in `CANDIDATE_SCHEMA` with this 10-criterion rubric
- **Gold standard creation**: Score candidate gold examples — only store examples scoring 85+
- **Content review UI**: Display the 10-criterion breakdown in the SKU review dashboard
- **Prompt improvement**: When descriptions score <60, the specific weakness identifies which prompt section needs revision
- **A/B testing**: Compare scores between prompt versions to measure improvement
- **Other skills**: `allied-brass-brand-expert` for brand voice, `product-storytelling` for narrative patterns

## References

- Current rubric: `src/feedops/pipeline/prompts.py` (CANDIDATE_SCHEMA.self_score)
- Quality crisis analysis: `docs/plans/2026-02-21-strategic-milestone-assessment.md` (Part 2)
- System prompt: `src/feedops/pipeline/prompts.py` (SYSTEM_PROMPT)
- Shopping intelligence: `src/feedops/config/shopping_intelligence.yaml`
- Category guidance: `src/feedops/pipeline/prompts.py` (_CATEGORY_GUIDANCE)
