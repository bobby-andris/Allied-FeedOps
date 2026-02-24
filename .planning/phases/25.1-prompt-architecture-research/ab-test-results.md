# A/B Prompt Testing Results (v2.1 — Variant-Level)

**Date:** 2026-02-23
**Phase:** 25.1-prompt-architecture-research, Plan 03 (revised)
**Model:** GPT-5.2 (reasoning_effort=medium, strict JSON schema)
**SKUs tested:** 3 representative + 3 unseen
**Key change from v1:** Variant-level generation with specific finishes per SKU

## Executive Summary

Three prompt variations tested with VARIANT-LEVEL generation (specific finish per SKU):
- **A (Current):** Full SKILL.md injection (267K chars) + finish instruction appended
- **B (Minimal):** SYSTEM_PROMPT base only (6.4K chars) + finish instruction appended
- **C (Optimized):** New CTCO prompt (~18K chars) with gold examples, finish context, competitor prohibition

### Key Findings

**A_Current:** Google title starts with finish: 3/3 | Bing title starts with finish: 1/3 | Competitor brand leaks: 1/3
**B_Minimal:** Google title starts with finish: 3/3 | Bing title starts with finish: 1/3 | Competitor brand leaks: 1/3
**C_Optimized:** Google title starts with finish: 3/3 | Bing title starts with finish: 3/3 | Competitor brand leaks: 0/3

## Summary Table

| SKU | Finish | Category | Variation | Google Title (first 70 chars) | Desc Len | Finish First? | Competitors? | Filler | Robert |
|-----|--------|----------|-----------|-------------------------------|----------|---------------|-------------|--------|--------|
| 1025U | Polished Nickel | Paper Towel Holders | A_Current | Polished Nickel Paper Towel Holder Wall Mount, 5-Inch Projection - Sol | 917 | YES | jan barboglio | Clean | Clean |
| 1025U | Polished Nickel | Paper Towel Holders | B_Minimal | Polished Nickel Paper Towel Holder, 15-Inch Solid Brass Wall Mount - S | 934 | YES | jan barboglio | Clean | Clean |
| 1025U | Polished Nickel | Paper Towel Holders | C_Optimized | Polished Nickel Skyline Collection Wall Mounted Paper Towel Holder - T | 927 | YES | Clean | finest | Clean |
| WP-2/16-GAL | Oil Rubbed Bronze | Glass Shelves | A_Current | Oil Rubbed Bronze Glass Shelf, 16-Inch Double with Gallery Rail - Soli | 834 | YES | Clean | Clean | Clean |
| WP-2/16-GAL | Oil Rubbed Bronze | Glass Shelves | B_Minimal | Oil Rubbed Bronze 16-Inch Double Glass Shelf, Solid Brass Gallery Rail | 774 | YES | Clean | Clean | Clean |
| WP-2/16-GAL | Oil Rubbed Bronze | Glass Shelves | C_Optimized | Oil Rubbed Bronze Glass Shelf - Waverly Place Collection 16-Inch Doubl | 884 | YES | Clean | Clean | Clean |
| DMF-2/2X | Satin Brass | Make-Up Mirrors | A_Current | Satin Brass 8-Inch 2X Floor Standing Makeup Mirror - Adjustable Height | 698 | YES | Clean | Clean | Clean |
| DMF-2/2X | Satin Brass | Make-Up Mirrors | B_Minimal | Satin Brass 8-Inch 2X Floor Standing Makeup Mirror, Double-Faced - Sol | 800 | YES | Clean | Clean | Clean |
| DMF-2/2X | Satin Brass | Make-Up Mirrors | C_Optimized | Satin Brass Floor Standing Makeup Mirror 8-Inch Diameter, 2X - Traditi | 887 | YES | Clean | Clean | Clean |

## Token Usage Comparison

| Variation | System Chars | System Tokens | Reduction vs Current |
|-----------|-------------|---------------|---------------------|
| A_Current | 266,242 | 57,504 | 0.0% |
| B_Minimal | 6,406 | 1,328 | 97.7% |
| C_Optimized | 18,313 | 3,890 | 93.2% |

## Side-by-Side Comparisons

### 1025U (Paper Towel Holders) — Polished Nickel [Representative]

#### A_Current

**Google Title:** Polished Nickel Paper Towel Holder Wall Mount, 5-Inch Projection - Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** Brass Paper Towel Holder Wall Mount, Solid Brass

**Google Description** (917 chars):
> Free up counter space while keeping a roll at tearing height—this Polished Nickel wall-mount brass paper towel holder is built from solid brass with a 5-inch projection for everyday kitchen reach. Concealed screw mounting keeps the look clean, so you see the Skyline Collection’s petite spherical end pieces and smooth circular backplates, not exposed fasteners. The holder includes all installation hardware and requires no assembly. Borrowing the jewelry-like cues of petite bathroom hardware, Skyline reads like a designed detail even in the kitchen. If you’re comparing styles such as a Jan Barboglio paper towel holder, this is a traditional take with crisp, intentional detailing. Skyline is known for elegant bath accessories; this piece brings that same matching Skyline look to the wall where you use it most. Backed by a Limited Lifetime Warranty and finished with a lifetime finish designed to resist rust.

**Bing Title:** Polished Nickel 5-Inch Projection Paper Towel Holder - Wall Mount Solid Brass Towel Rack - Skyline Collection - Allied Brass
**Bing Description** (940 chars):
> Keep your counter clear while putting paper towels right where you reach for them—this Polished Nickel wall mounted paper towel holder is solid brass with a 5-inch projection for everyday kitchen use. Concealed screw mounting keeps the wall clean, highlighting the Skyline Collection’s petite spherical end pieces and smooth circular backplates instead of exposed fasteners. Includes the paper towel holder and all installation hardware, with no assembly required. If you are comparing options like a Jan Barboglio paper towel holder, Skyline offers a traditional profile with design-aware detail that looks intentional on the wall. This solid brass towel rack style holder is part of the Skyline collection look often used in petite bathroom hardware and elegant bath accessories, so it is easy to carry a matching Skyline finish across nearby wall mounted hardware. Limited Lifetime Warranty and a lifetime finish designed to resist rust.

**Shopify Title:** Wall Mounted Paper Towel Holder - Skyline Collection

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: YES
- Competitor brands in content: LEAKED: ['jan barboglio']
- Keyword stuffing: FLAGGED [('skyline', 10), ('towel', 9), ('holder', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 143 words
- Opening words: ['Free', 'Concealed', 'The', 'Borrowing', 'If']
- Claims density: 4.2 per 100 words
- Self-score: hook_quality=8, product_specificity=7, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=10, platform_compliance=9, finish_integration=8, variety_score=7

#### B_Minimal

**Google Title:** Polished Nickel Paper Towel Holder, 15-Inch Solid Brass Wall Mount - Skyline Collection - Allied Brass
**Google Short Title:** brass paper towel holder wall mount

**Google Description** (934 chars):
> Clear the counter and keep a roll ready—this Polished Nickel wall-mount brass paper towel holder is 15 inches tall, built from solid brass with concealed-screw mounting for a clean, finished look. The Skyline collection design adds a refined detail with petite spherical end pieces paired with smooth circular backplates, so the holder looks intentional on the wall instead of purely utilitarian. Solid brass construction plus a lifetime finish are designed to ensure the holder will never rust, making it a smart choice for everyday kitchen use near sinks and prep areas. Includes the paper towel holder and all installation hardware, with no assembly required. If you’re searching for a brass paper towel holder or even a jan barboglio paper towel holder, Skyline offers a coordinated, design-forward alternative—ideal when you want a matching Skyline look across your hardware and elegant bath accessories used throughout the home.

**Bing Title:** Polished Nickel Paper Towel Holder, 15-Inch Solid Brass Wall Mount - Skyline Collection - Allied Brass
**Bing Description** (1049 chars):
> Clear the counter and keep a roll ready—this Polished Nickel wall-mount brass paper towel holder is 15 inches tall, built from solid brass with concealed-screw mounting for a clean, finished look. The Skyline collection styling stands out in the details: petite spherical end pieces and smooth circular backplates that read like small, jewelry-like accents on the wall. Solid brass construction and a lifetime finish are designed to ensure the holder will never rust, helping it stay steady and good-looking through everyday kitchen use. The wall mounted design is an ideal use of space when you want less clutter on the countertop. Includes the paper towel holder and all installation hardware, and no assembly is required. Backed by a Limited Lifetime Warranty. For shoppers typing brass paper towel holder wall mount, wall mounted paper towel holder, or even jan barboglio paper towel holder, this is a strong match when you want coordinated hardware—matching Skyline pieces and elegant bath accessories—without compromising on solid-brass build.

**Shopify Title:** Skyline Collection Wall Mounted Paper Towel Holder

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: YES
- Competitor brands in content: LEAKED: ['jan barboglio']
- Keyword stuffing: FLAGGED [('holder', 14), ('brass', 13), ('paper', 11)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 145 words
- Opening words: ['Clear', 'The', 'Solid', 'Includes', 'If']
- Claims density: 4.1 per 100 words
- Self-score: hook_quality=8, product_specificity=7, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=9, platform_compliance=7, finish_integration=8, variety_score=6

#### C_Optimized

**Google Title:** Polished Nickel Skyline Collection Wall Mounted Paper Towel Holder - Traditional Solid Brass Wall Mount - Allied Brass
**Google Short Title:** Polished Nickel Brass Paper Towel Holder Wall Mount

**Google Description** (927 chars):
> Keep your countertop clean and clutter free with a wall-mounted paper towel holder that adds the finishing touch to your kitchen décor. Polished Nickel gives this piece a warm silver glow — richer than chrome, with subtle golden undertones that designers choose for transitional bathrooms. Crafted from the finest solid brass materials, this brass paper towel holder is made with a lifetime finish to insure products will never rust. Concealed screw mounting hardware makes installation easy, and the wall mount design is an ideal use of space. You receive the paper towel holder plus all installation hardware, and no assembly is required. From the Skyline collection, the design features distinctively petite spherical end pieces paired with smooth circular backplates for a refined, jewelry-like presence on the wall. Coordinate with matching Skyline pieces for a pulled-together look, backed by a Limited Lifetime Warranty.

**Bing Title:** Polished Nickel Skyline Collection Wall Mount Paper Towel Rack - Traditional Solid Brass - Allied Brass
**Bing Description** (912 chars):
> Clear the counter and keep a roll ready—this Polished Nickel wall mount paper towel holder is designed for an ideal use of space in the kitchen. Crafted from the finest solid brass materials, it is made with a lifetime finish to insure products will never rust. Polished Nickel gives this piece a warm silver glow — richer than chrome, with subtle golden undertones that designers choose for transitional bathrooms. Concealed screw mounting hardware makes installation easy, and the paper towel holder includes all installation hardware (screw size: #8 X1 1/4"). No assembly is required. Part of the Skyline collection, it carries Skyline’s petite spherical end pieces and smooth circular backplates for a refined, jewelry-like look. Choose this brass paper towel holder wall mount when you want elegant bath accessories styling translated to kitchen hardware, with a Limited Lifetime Warranty for peace of mind.

**Shopify Title:** Skyline Collection Wall Mounted Paper Towel Holder - Solid Brass

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: YES
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('wall', 8), ('paper', 8), ('towel', 8)]
- Filler words: FLAGGED ['finest']
- Robert's concerns: Clean
- Structure: 7 sentences, 142 words
- Opening words: ['Keep', 'Polished', 'Crafted', 'Concealed', 'You']
- Claims density: 4.2 per 100 words
- Self-score: accuracy=8, specificity=7, engagement=7


### WP-2/16-GAL (Glass Shelves) — Oil Rubbed Bronze [Representative]

#### A_Current

**Google Title:** Oil Rubbed Bronze Glass Shelf, 16-Inch Double with Gallery Rail - Solid Brass Wall Mount - Waverly Place Collection - Allied Brass
**Google Short Title:** 16-Inch Double Glass Shelf

**Google Description** (834 chars):
> Put everyday toiletries up off the counter with an Oil Rubbed Bronze 16-inch wall-mounted double glass shelf built on solid brass hardware and a front gallery rail. Two tiers make smart use of vertical space, while the gallery rail helps keep bottles and jars in place. Each shelf is made from 3/8-inch thick tempered glass for strength and peace of mind. Concealed screw mounting keeps the installation looking clean, and the shelf includes the glass and all installation hardware (no assembly required). Part of the Waverly Place Collection, where cylindrical posts are detailed with precisely machined concentric grooves for subtle texture. A refined bathroom shelf solution when you want bathroom shelves that look intentional—ideal for bathroom wall shelves and brass and glass shelves, including bistro shelves-inspired styling.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: NO
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('glass', 5), ('shelf', 5), ('brass', 4)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 127 words
- Opening words: ['Put', 'Two', 'Each', 'Concealed', 'Part']
- Claims density: 4.7 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=10, platform_compliance=9, finish_integration=8, variety_score=7

#### B_Minimal

**Google Title:** Oil Rubbed Bronze 16-Inch Double Glass Shelf, Solid Brass Gallery Rail - Wall Mount - Waverly Place - Allied Brass
**Google Short Title:** 16-Inch Double Glass Shelf

**Google Description** (774 chars):
> Get two levels of storage without cluttering the wall—this 16-inch double glass shelf in Oil Rubbed Bronze pairs 3/8-inch tempered glass with solid brass, wall-mounted hardware and a protective gallery rail. The raised rail helps keep everyday items in place, while the double-shelf design makes smart use of vertical space over a vanity. Concealed screw mounting keeps the look clean and streamlined once installed. Built as one of Allied Brass’s brass and glass shelves, it’s a strong choice when you want a bathroom shelf that looks intentional, not temporary. Part of the Waverly Place collection, with precisely machined concentric grooves that add subtle texture—an easy way to coordinate bathroom shelves and other bathroom wall shelves in a matching design language.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: NO
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('brass', 5), ('glass', 4), ('shelf', 4)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 120 words
- Opening words: ['Get', 'The', 'Concealed', 'Built', 'Part']
- Claims density: 5.0 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=10, platform_compliance=7, finish_integration=8, variety_score=7

#### C_Optimized

**Google Title:** Oil Rubbed Bronze Glass Shelf - Waverly Place Collection 16-Inch Double with Gallery Rail - Traditional Solid Brass Wall Mount - Allied Brass
**Google Short Title:** Oil Rubbed Bronze 16-Inch Double Glass Shelf

**Google Description** (884 chars):
> Two tiers of tempered glass storage with a gallery rail—this 16-inch Waverly Place double glass shelf keeps everyday items organized while adding a traditional decorative detail. Finished in Oil Rubbed Bronze. Built with 3/8-inch thick tempered glass for safety and strength, paired with solid brass hardware. The wall-mount design uses concealed screw mounting hardware to make installation easy and keep fasteners out of sight. Use it as a bathroom shelf on its own or combine multiples as coordinated bathroom shelves. Part of the Waverly Place collection, with cylindrical posts wrapped in precisely machined concentric grooves that add textural interest without overwhelming clean contemporary lines. Includes the glass shelf and all installation hardware, and no assembly is required. A smart choice when you want brass and glass shelves that match the Waverly Place collection.

**Bing Title:** Oil Rubbed Bronze Bathroom Glass Shelf - Waverly Place Collection 16-Inch Double Wall Shelf with Gallery Rail - Allied Brass
**Bing Description** (922 chars):
> 16-inch double glass shelf for bathroom wall storage, with a gallery rail and concealed screw mounting for an easy wall-mount install. Finished in Oil Rubbed Bronze. Built with 3/8-inch thick tempered glass for safety and strength, plus solid brass hardware for a lasting fixture. The double-shelf format is an ideal use of space when you need bathroom shelves that keep daily items organized without taking up countertop room. Designed as part of the Waverly Place collection, it features cylindrical posts wrapped in precisely machined concentric grooves that create sophisticated textural interest without overwhelming clean contemporary lines. Use it as a single bathroom shelf or repeat it as matching bathroom wall shelves for a consistent look. Includes the glass shelf and all installation hardware, and no assembly is required—ideal when you’re choosing coordinated brass and glass shelves for a traditional bath.

**Shopify Title:** Waverly Place 16-Inch Double Glass Shelf with Gallery Rail

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: YES
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('glass', 11), ('shelf', 10), ('brass', 7)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 8 sentences, 133 words
- Opening words: ['Two', 'Finished', 'Built', 'The', 'Use']
- Claims density: 5.3 per 100 words
- Self-score: accuracy=9, specificity=8, engagement=7


### DMF-2/2X (Make-Up Mirrors) — Satin Brass [Representative]

#### A_Current

**Google Title:** Satin Brass 8-Inch 2X Floor Standing Makeup Mirror - Adjustable Height Solid Brass - Allied Brass
**Google Short Title:** Satin Brass 8-Inch 2X Floor Standing Makeup Mirror

**Google Description** (698 chars):
> In Satin Brass, this adjustable height floor standing makeup mirror brings close-up clarity and an all-around view to your bathroom without any wall mounting. The freestanding standing mirror is crafted from solid brass and features an 8-inch double-faced glass: 2X magnification on one side for detailed makeup or shaving, and 1X on the other for a quick check at any angle. A heavy solid brass base helps prevent tipping, and a felt pad helps protect countertops and floors from scratches. If you’ve been searching for a floor stand makeup mirror that looks traditional and feels substantial, this adjustable floor mirror is designed to be a lasting part of your daily routine. Assembly required.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: NO
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('brass', 6), ('mirror', 5), ('floor', 4)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 113 words
- Opening words: ['In', 'The', 'A', 'If', 'Assembly']
- Claims density: 3.5 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=10, platform_compliance=6, finish_integration=8, variety_score=6

#### B_Minimal

**Google Title:** Satin Brass 8-Inch 2X Floor Standing Makeup Mirror, Double-Faced - Solid Brass - Allied Brass
**Google Short Title:** 8-Inch 2X Floor Standing Makeup Mirror

**Google Description** (800 chars):
> Get close-up clarity without giving up full-face perspective: this Satin Brass floor standing makeup mirror pairs an 8-inch double-faced glass with solid brass construction and adjustable height for everyday grooming. One side offers 2X magnification for detail work; flip to the 1X mirror for an all-around check at any angle. The freestanding design needs no wall mounting, and a heavy solid brass base helps prevent tipping while a felt pad helps prevent scratching on surfaces. Traditional styling with classic accents makes it an easy fit with coordinated bath accessories. A smart pick when you want a standing mirror that stays put—ideal as an adjustable floor mirror, adjustable height floor mirror, or adjustable height floor standing makeup mirror for makeup and shaving. Assembly required.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: NO
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('mirror', 7), ('brass', 6), ('floor', 5)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 123 words
- Opening words: ['Get', 'One', 'The', 'Traditional', 'A']
- Claims density: 3.3 per 100 words
- Self-score: hook_quality=8, product_specificity=7, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=10, platform_compliance=7, finish_integration=8, variety_score=6

#### C_Optimized

**Google Title:** Satin Brass Floor Standing Makeup Mirror 8-Inch Diameter, 2X - Traditional Solid Brass Freestanding - Allied Brass
**Google Short Title:** Satin Brass 8-Inch Floor Standing Makeup Mirror, 2X

**Google Description** (887 chars):
> Bring close-up detail to eye level without leaning over the counter—this floor standing makeup mirror uses an 8-inch double-faced mirror glass for daily makeup or shaving. Finished in Satin Brass. Crafted from solid brass materials, it’s a freestanding standing makeup mirror with an adjustable height design so you can position the mirror where you need it. One side provides 2X magnification for detailed grooming, while the opposite side offers 1x magnification for a quick all-around check at any angle. A heavy solid brass base will help prevent tipping, and the felt pad will help prevent scratching on any surface. If you’re searching for an adjustable height floor standing makeup mirror, an adjustable floor mirror, or a floor stand makeup mirror that requires no wall mounting, the traditional profile and classic accents make this an easy, efficient solution for the bathroom.

**Bing Title:** Satin Brass Floor Standing Makeup Mirror 8-Inch Diameter, 2X - Traditional Solid Brass Standing Mirror - Allied Brass
**Bing Description** (886 chars):
> Freestanding adjustable height floor standing makeup mirror with 8-inch double-faced mirror glass: 2X magnification on one side and 1x on the other for a quick all-around check at any angle. Finished in Satin Brass. Crafted from solid brass materials, this traditional standing makeup mirror is designed as an easy solution for a daily make-up or shaving routine. The heavy solid brass base will help prevent tipping, while a felt pad will help prevent scratching on any surface. Because the freestanding design requires no wall mounting, it works well when you want a standing mirror you can place where it’s most useful near the sink. Popular searches like adjustable height floor mirror and adjustable floor mirror match the way this floor stand makeup mirror is meant to be used—close-up precision on one side, normal viewing on the other, with classic accents that finish the look.

**Shopify Title:** Adjustable Height Floor Standing Double-Faced Makeup Mirror – 8-Inch Diameter, 2X Magnification

**Analysis:**
- Finish in Google title: YES
- Finish in Bing title: YES
- Competitor brands in content: Clean
- Keyword stuffing: FLAGGED [('mirror', 17), ('brass', 12), ('floor', 10)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 140 words
- Opening words: ['Bring', 'Finished', 'Crafted', 'One', 'A']
- Claims density: 2.9 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=7

## Recommendation

### Validation Criteria

| Criterion | A_Current | B_Minimal | C_Optimized |
|-----------|-----------|-----------|-------------|
| Finish first in Google title | 3/3 | 3/3 | 3/3 |
| Finish first in Bing title | 1/3 | 1/3 | 3/3 |
| No competitor brands | 2/3 | 2/3 | 3/3 |
| No Robert's concerns | 3/3 | 3/3 | 3/3 |
| No filler words | 3/3 | 3/3 | 2/3 |

---
*Generated: 2026-02-24 00:59 UTC*
*Script: scripts/ab_prompt_test.py (v2.1 — variant-level)*
*All outputs available in /tmp/ab_test_outputs/*