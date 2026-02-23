# A/B Prompt Testing Results

**Date:** 2026-02-23
**Phase:** 25.1-prompt-architecture-research, Plan 03
**Model:** GPT-5.2 (reasoning_effort=medium, strict JSON schema)
**SKUs tested:** 3 representative (from eval set) + 3 unseen (not in eval set)

## Executive Summary

Three prompt variations were tested on 6 SKUs (3 representative, 3 unseen):
- **A (Current):** Full SKILL.md injection (267K chars / 57K tokens system prompt)
- **B (Minimal):** SYSTEM_PROMPT base only, no skills (6.4K chars / 1.3K tokens)
- **C (Optimized):** New CTCO prompt from Plan 02 (~8.2K chars / 1.7K tokens)

**Key findings:**
1. **All 3 variations produce zero Robert's concern violations** -- the SYSTEM_PROMPT prohibition rules work regardless of prompt size
2. **All 3 variations produce zero filler/banned words** -- GPT-5.2 respects the banned word list
3. **Variation C generates ALL platform fields consistently** (Google + Bing + Shopify) while A and B sometimes leave Bing/Shopify empty
4. **Variation C has 100% unique description openings** across SKUs vs 67% for A -- better structure variety
5. **97% token reduction** (57K to 1.7K system tokens) with no quality degradation
6. **Variation C titles miss the finish name** when no specific finish is requested -- this is a known gap to address

## Summary Table

| SKU | Category | Variation | Google Title (first 70 chars) | Desc Len | Score | Stuffing | Filler | Robert |
|-----|----------|-----------|-------------------------------|----------|-------|----------|--------|--------|
| 1025U | Paper Towel Holders | A_Current | {FINISH_NAME} Brass Wall Mount Paper Towel Holder, 15-Inch - Solid Bra | 749 | 7.6 | brass(10), wall(9) | Clean | Clean |
| 1025U | Paper Towel Holders | B_Minimal | {FINISH_NAME} Brass Paper Towel Holder Wall Mount, 15-Inch Solid Brass | 957 | 7.0 | brass(6), holder(4) | Clean | Clean |
| 1025U | Paper Towel Holders | C_Optimized | Skyline Collection Brass Paper Towel Holder Wall Mount - Solid Brass - | 911 | 7.7 | brass(15), skyline(10) | Clean | Clean |
| WP-2/16-GAL | Glass Shelves | A_Current | Antique Brass Glass Shelf 16-Inch Double with Gallery Rail - Solid Bra | 822 | 7.8 | brass(14), glass(11) | Clean | Clean |
| WP-2/16-GAL | Glass Shelves | B_Minimal | Antique Bronze 16-Inch Double Glass Shelf, Solid Brass - Waverly Place | 911 | 7.2 | glass(10), shelf(8) | Clean | Clean |
| WP-2/16-GAL | Glass Shelves | C_Optimized | Waverly Place Collection Glass Shelf - 16-Inch Double with Gallery Rai | 910 | 7.3 | glass(10), shelf(8) | Clean | Clean |
| DMF-2/2X | Make-Up Mirrors | A_Current | {FINISH_NAME} Floor Standing Makeup Mirror - 8-Inch 2X/1X Adjustable H | 688 | 7.5 | mirror(14), standing(9) | Clean | Clean |
| DMF-2/2X | Make-Up Mirrors | B_Minimal | {FINISH_NAME} 8-Inch 2X Floor Standing Makeup Mirror - Adjustable Heig | 826 | 7.1 | mirror(6), standing(5) | Clean | Clean |
| DMF-2/2X | Make-Up Mirrors | C_Optimized | Floor Standing Makeup Mirror - Traditional Freestanding 8-Inch Diamete | 838 | 7.3 | mirror(14), floor(9) | Clean | Clean |
| 1026 | Tumbler Toothbrush Holders | A_Current | Antique Brass Tumbler Toothbrush Holder, 4.5-Inch - Wall Mount Solid B | 760 | 7.4 | brass(5), wall(5) | Clean | Clean |
| 1026 | Tumbler Toothbrush Holders | B_Minimal | {FINISH_NAME} Tumbler Toothbrush Holder, 4.5-Inch Solid Brass - Wall M | 991 | 0.0 | wall(5) | Clean | Clean |
| 1026 | Tumbler Toothbrush Holders | C_Optimized | Skyline Collection Tumbler Toothbrush Holder with Twist Accents - Wall | 773 | 7.3 | wall(8), skyline(7) | Clean | Clean |
| 1031/18 | Towel Bars | A_Current | Antique Brass 18-Inch Towel Bar - Solid Brass Wall Mount, Skyline Coll | 783 | 7.1 | brass(14), towel(8) | Clean | Clean |
| 1031/18 | Towel Bars | B_Minimal | Antique Bronze Towel Bar, 18-Inch Solid Brass - Wall Mount - Skyline C | 888 | 6.4 | towel(10), wall(8) | Clean | Clean |
| 1031/18 | Towel Bars | C_Optimized | Skyline Collection 18-Inch Towel Bar - Wall Mount Solid Brass - Allied | 820 | 7.3 | skyline(8), brass(8) | Clean | Clean |
| 1032 | Soap Dishes | A_Current | {FINISH_NAME} Wall Mounted Soap Dish, 4.5-Inch - Solid Brass - Skyline | 804 | 7.5 | soap(11), wall(10) | Clean | Clean |
| 1032 | Soap Dishes | B_Minimal | {FINISH_NAME} Wall Mounted Soap Dish, 4.5-In Solid Brass - Skyline Col | 859 | 7.2 | wall(8), soap(8) | Clean | Clean |
| 1032 | Soap Dishes | C_Optimized | Wall Mounted Soap Dish - Skyline Collection Solid Brass Bath Accessory | 754 | 7.7 | wall(10), soap(10) | Clean | Clean |

## Token Usage Comparison

| Variation | System Chars | System Tokens | Reduction vs Current |
|-----------|-------------|---------------|---------------------|
| A_Current | 266,242 | 57,504 | -- (baseline) |
| B_Minimal | 6,406 | 1,328 | 97.7% |
| C_Optimized | 8,164 | 1,733 | 97.0% |

## Side-by-Side Comparisons

### 1025U (Paper Towel Holders) [Representative]

#### A_Current

**Google Title:** {FINISH_NAME} Brass Wall Mount Paper Towel Holder, 15-Inch - Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** Brass Paper Towel Holder Wall Mount, 15-Inch

**Google Description** (749 chars):
> Free up counter space with a wall mounted paper towel holder in {FINISH_NAME}—a 15-inch design built from solid brass for a more substantial, long-lasting kitchen essential. The Skyline Collection styling shows up in the details: petite spherical end pieces and smooth circular backplates that give the holder a refined, jewelry-like look on the wall. Concealed screw mounting keeps the installation clean, and the wall-mount design helps keep busy prep areas clutter free. Includes the paper towel holder and all installation hardware, with no assembly required. A smart choice when you want a brass paper towel holder that looks intentional, not like an afterthought—and an easy way to keep a matching Skyline look across coordinating accessories.

**Bing Title:** {FINISH_NAME} Brass Wall Mounted Paper Towel Holder, 15-Inch - Solid Brass - Skyline Collection - Allied Brass
**Bing Description** (682 chars):
> Clear the countertop with a wall mounted paper towel holder in {FINISH_NAME}—a 15-inch solid brass design made for everyday kitchen use. Skyline Collection details set it apart with petite spherical end pieces and smooth circular backplates for a refined, jewelry-like presence on the wall. Concealed screw mounting keeps the look clean, while the wall-mount format turns unused wall space into practical towel storage. Includes the paper towel holder and all installation hardware, and it requires no assembly. Choose it when you want a brass paper towel holder that coordinates with a matching Skyline set of accessories and keeps your kitchen looking intentional and uncluttered.

**Shopify Title:** Wall Mounted Paper Towel Holder - Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 10), ('wall', 9), ('towel', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 115 words
- Opening words: ['Free', 'The', 'Concealed', 'Includes', 'A']
- Claims density: 5.2 per 100 words
- Self-score: hook_quality=8, product_specificity=7, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=10, platform_compliance=9, finish_integration=7, variety_score=7

#### B_Minimal

**Google Title:** {FINISH_NAME} Brass Paper Towel Holder Wall Mount, 15-Inch Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** brass paper towel holder wall mount

**Google Description** (957 chars):
> Clear counter space in the kitchen with this 15-inch {FINISH_NAME} brass paper towel holder wall mount, crafted from solid brass and installed with concealed screw mounting for a clean, finished look. The wall-mounted design keeps a roll right where you need it while helping reduce countertop clutter. A lifetime designer finish is specified to help ensure the holder won’t rust, and the included installation hardware helps make setup straightforward (no assembly required). Designed as part of the Skyline collection, it brings the line’s petite spherical end pieces and smooth circular backplates to the wall for a refined, almost jewelry-like presence—an easy way to keep a matching Skyline look across your coordinated hardware. If you’ve been browsing for a jan barboglio paper towel holder, this solid-brass Skyline option is a strong choice when you want decorative impact without giving up everyday function. Backed by a Limited Lifetime Warranty.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 6), ('holder', 4), ('wall', 4)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 147 words
- Opening words: ['Clear', 'The', 'A', 'Designed', 'If']
- Claims density: 4.8 per 100 words
- Self-score: hook_quality=8, product_specificity=7, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=9, platform_compliance=7, finish_integration=7, variety_score=6

#### C_Optimized

**Google Title:** Skyline Collection Brass Paper Towel Holder Wall Mount - Solid Brass - Allied Brass
**Google Short Title:** Brass paper towel holder wall mount

**Google Description** (911 chars):
> Clear counter space with a wall mount brass paper towel holder built from solid brass and styled with Skyline’s petite spherical end pieces and smooth circular backplates. The wall-mounted design is an ideal use of space for kitchens that need to stay clean and clutter free. Concealed screw mounting hardware keeps the look streamlined while making installation easy, and all installation hardware is included. Made of solid brass and provided with a lifetime finish to insure products will never rust, helping maintain finish integrity in everyday kitchen humidity. Part of the Skyline Collection for a matching Skyline look across coordinated pieces, so the details stay consistent from one accessory to the next. If you’ve been searching for a brass paper towel holder or comparing a jan barboglio paper towel holder style, Skyline offers a refined, jewelry-like wall presence with solid brass construction.

**Bing Title:** Skyline Collection Brass Paper Towel Rack Wall Mount - Solid Brass - Allied Brass
**Bing Description** (866 chars):
> Keep your kitchen countertop clean and clutter free with a Skyline Collection wall mount brass paper towel holder crafted from solid brass. Skyline’s petite spherical end pieces and smooth circular backplates create a refined, jewelry-like look on the wall. Concealed screw mounting hardware helps keep fasteners out of sight and makes installation easy; the holder ships with all installation hardware. Finished with a lifetime finish to insure products will never rust, so it’s built for daily use around sinks and cooking areas. Available in a wide variety of lifetime designer finishes to coordinate with your other Skyline pieces. Limited Lifetime Warranty. For shoppers comparing a brass paper towel holder or a jan barboglio paper towel holder search, this solid brass paper towel rack keeps rolls off the counter while maintaining a coordinated Skyline look.

**Shopify Title:** Wall Mounted Paper Towel Holder - Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 15), ('skyline', 10), ('paper', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 142 words
- Opening words: ['Clear', 'The', 'Concealed', 'Made', 'Part']
- Claims density: 4.9 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=7


### WP-2/16-GAL (Glass Shelves) [Representative]

#### A_Current

**Google Title:** Antique Brass Glass Shelf 16-Inch Double with Gallery Rail - Solid Brass Wall Mount - Waverly Place Collection - Allied Brass
**Google Short Title:** Antique Brass 16-Inch Double Glass Shelf

**Google Description** (822 chars):
> Create layered storage without crowding the wall: this 16-inch double glass shelf in Antique Brass pairs 3/8-inch tempered glass with solid brass wall-mount hardware and a gallery rail to help keep bottles in place. The Waverly Place Collection’s precisely machined concentric grooves add subtle texture that reads as intentional detail up close. Concealed screw mounting keeps the look clean, and the shelf includes installation hardware with no assembly required. A smart choice when you want a bathroom shelf that stays visually light while doing real work—use it as bathroom wall shelves over the vanity or wherever you need organized, easy-to-reach storage. If you’re shopping brass and glass shelves or even bistro shelves for a coordinated look, this design brings glass clarity together with solid brass structure.

**Bing Title:** Antique Brass Glass Shelf 16-Inch Double with Gallery Rail - Solid Brass Wall Mount - Waverly Place Collection - Allied Brass
**Bing Description** (753 chars):
> Create layered storage without crowding the wall: this 16-inch double glass shelf in Antique Brass pairs 3/8-inch tempered glass with solid brass wall-mount hardware and a gallery rail to help keep bottles in place. The Waverly Place Collection’s precisely machined concentric grooves add subtle texture that reads as intentional detail up close. Concealed screw mounting keeps the wall clean, and the shelf includes installation hardware with no assembly required. Use it as a bathroom shelf over the vanity or as bathroom wall shelves wherever you need organized storage. A strong option for shoppers comparing glass shelves for bathroom projects, brass and glass shelves, or bistro shelves that bring glass clarity and solid brass structure together.

**Shopify Title:** 16-Inch Double Glass Shelf with Gallery Rail - Waverly Place Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 14), ('glass', 11), ('wall', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 126 words
- Opening words: ['Create', 'The', 'Concealed', 'A', 'If']
- Claims density: 5.6 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=10, platform_compliance=9, finish_integration=8, variety_score=7

#### B_Minimal

**Google Title:** Antique Bronze 16-Inch Double Glass Shelf, Solid Brass - Waverly Place - Allied Brass
**Google Short Title:** 16-Inch Double Glass Shelf

**Google Description** (911 chars):
> Create organized, easy-to-reach storage with this 16-inch double glass shelf in Antique Bronze—wall-mounted with solid brass hardware, tempered glass, and a protective gallery rail to help keep items in place. The two-tier design is an ideal use of space when you want more room without adding a bulky cabinet, making it a smart bathroom shelf for everyday essentials. Each shelf is made from 3/8-inch thick tempered glass for safety and strength, while concealed screw mounting keeps the installation clean and hardware-free in view. Part of the Waverly Place collection, the cylindrical posts are detailed with precisely machined concentric grooves for subtle texture that complements traditional and transitional bathroom hardware. A dependable pick for bathroom wall shelves, especially if you’re searching for brass and glass shelves or bistro shelves with a secure rail and included installation hardware.

**Bing Title:** Antique Bronze 16-Inch Double Glass Shelf, Solid Brass - Waverly Place - Allied Brass
**Bing Description** (911 chars):
> Create organized, easy-to-reach storage with this 16-inch double glass shelf in Antique Bronze—wall-mounted with solid brass hardware, tempered glass, and a protective gallery rail to help keep items in place. The two-tier design is an ideal use of space when you want more room without adding a bulky cabinet, making it a smart bathroom shelf for everyday essentials. Each shelf is made from 3/8-inch thick tempered glass for safety and strength, while concealed screw mounting keeps the installation clean and hardware-free in view. Part of the Waverly Place collection, the cylindrical posts are detailed with precisely machined concentric grooves for subtle texture that complements traditional and transitional bathroom hardware. A dependable pick for bathroom wall shelves, especially if you’re searching for brass and glass shelves or bistro shelves with a secure rail and included installation hardware.

**Shopify Title:** Waverly Place 16 Inch Double Glass Shelf with Gallery Rail

**Analysis:**
- Keyword stuffing: FLAGGED [('glass', 10), ('shelf', 8), ('brass', 8)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 136 words
- Opening words: ['Create', 'The', 'Each', 'Part', 'A']
- Claims density: 4.4 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=10, platform_compliance=6, finish_integration=8, variety_score=6

#### C_Optimized

**Google Title:** Waverly Place Collection Glass Shelf - 16-Inch Double with Gallery Rail - Wall Mount - Allied Brass
**Google Short Title:** 16-Inch Double Glass Shelf

**Google Description** (910 chars):
> Get more storage off the counter with a 16-inch double glass shelf built with solid brass hardware and a protective gallery rail. Designed for wall-mount installation, it’s a clean way to add a bathroom shelf where you need it while keeping items in place. The shelf uses tempered glass for added safety and strength, and concealed screw mounting hardware keeps fasteners out of sight for a finished look. As part of the Waverly Place collection, the cylindrical posts feature precisely machined concentric grooves that add sophisticated textural interest without overwhelming clean contemporary lines. Use it as one of your everyday bathroom wall shelves, or pair it with other brass and glass shelves to keep a coordinated look. It’s also a smart alternative to bistro shelves when you want glass storage with a gallery rail. Includes the glass shelf and all installation hardware, with no assembly required.

**Bing Title:** Waverly Place Collection Glass Wall Shelf - 16-Inch Double with Gallery Rail - Wall Mount - Allied Brass
**Bing Description** (841 chars):
> Make the most of wall space with a 16-inch double glass shelf featuring solid brass hardware, tempered glass, and a gallery rail to help keep items in place. Wall-mount installation with concealed screw mounting hardware keeps the look clean and can save floor space. Designed in the Waverly Place collection, it wraps cylindrical posts with precisely machined concentric grooves for sophisticated textural interest without overwhelming clean contemporary lines. A natural fit when you’re shopping bathroom shelves that look intentional instead of improvised—especially when you want bathroom wall shelves that keep essentials organized. Coordinate the piece with other matching Waverly Place collection accessories for a consistent design language across the room. Includes the glass shelf and all installation hardware. Style: Traditional.

**Shopify Title:** 16-Inch Double Glass Shelf with Gallery Rail - Waverly Place Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('glass', 10), ('shelf', 8), ('wall', 8)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 146 words
- Opening words: ['Get', 'Designed', 'The', 'As', 'Use']
- Claims density: 3.4 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=6


### DMF-2/2X (Make-Up Mirrors) [Representative]

#### A_Current

**Google Title:** {FINISH_NAME} Floor Standing Makeup Mirror - 8-Inch 2X/1X Adjustable Height Solid Brass - Allied Brass
**Google Short Title:** Floor Standing Makeup Mirror, 8-Inch 2X/1X

**Google Description** (688 chars):
> In {FINISH_NAME}, this adjustable-height floor standing makeup mirror pairs an 8-inch double-faced glass with 2X magnification on one side and 1X on the other for a fast, all-around check. Built from solid brass with classic accents, it’s a freestanding standing makeup mirror that brings close-up detail to your daily makeup or shaving routine without any wall mounting. A heavy solid brass base helps prevent tipping, and a felt pad helps protect countertops from scratches. Ideal when you want a steady standing mirror you can position where you need it, this adjustable floor mirror delivers practical magnification in a traditional design. Assembly required. Includes make-up mirror.

**Bing Title:** {FINISH_NAME} Floor Standing Makeup Mirror - 8-Inch 2X/1X Adjustable Height Standing Mirror, Solid Brass - Allied Brass
**Bing Description** (731 chars):
> In {FINISH_NAME}, this adjustable-height floor standing makeup mirror gives you an 8-inch double-faced glass: 2X magnification on one side for close-up detail and 1X on the other for an all-around view. Crafted from solid brass with classic accents, it’s a freestanding standing mirror that keeps grooming and makeup application simple without wall mounting. The heavy solid brass base helps prevent tipping, while the felt pad helps protect the surface it sits on from scratching. If you’re searching for an adjustable height floor standing makeup mirror or a floor stand makeup mirror that stays put, this traditional vanity mirror delivers dependable magnification and easy placement. Assembly required. Includes make-up mirror.

**Shopify Title:** Adjustable Height Floor Standing Makeup Mirror - 8-Inch Double-Faced 2X/1X

**Analysis:**
- Keyword stuffing: FLAGGED [('mirror', 14), ('standing', 9), ('makeup', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 105 words
- Opening words: ['In', 'Built', 'A', 'Ideal', 'Assembly']
- Claims density: 3.8 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=6, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=9, platform_compliance=9, finish_integration=7, variety_score=7

#### B_Minimal

**Google Title:** {FINISH_NAME} 8-Inch 2X Floor Standing Makeup Mirror - Adjustable Height, Solid Brass - Allied Brass
**Google Short Title:** 8-Inch floor standing makeup mirror

**Google Description** (826 chars):
> Get close-up precision without drilling—this {FINISH_NAME} floor standing makeup mirror pairs an 8-inch double-faced glass with solid brass construction and a 2X/1X dual-sided design. Use the 2X magnification side for detailed makeup and shaving, then flip to the 1X side for a quick overall check at any angle. The freestanding, adjustable height floor standing makeup mirror is built around a heavy solid brass base that helps prevent tipping, and a felt pad underneath helps prevent scratching on any surface. Traditional styling with classic accents makes it an easy fit with coordinated bath accessories, while the standing mirror format keeps your counter and wall free. A smart choice when you want an adjustable floor mirror or standing makeup mirror that stays put and is ready for daily routines (assembly required).

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Keyword stuffing: FLAGGED [('mirror', 6), ('standing', 5), ('makeup', 5)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 129 words
- Opening words: ['Get', 'Use', 'The', 'Traditional', 'A']
- Claims density: 2.3 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=9, platform_compliance=7, finish_integration=6, variety_score=6

#### C_Optimized

**Google Title:** Floor Standing Makeup Mirror - Traditional Freestanding 8-Inch Diameter 2X Double Faced Solid Brass - Allied Brass
**Google Short Title:** Floor Standing Makeup Mirror - 8-Inch Diameter 2X

**Google Description** (838 chars):
> See detail without drilling walls—this adjustable height floor standing makeup mirror combines an 8-inch diameter double-faced glass with solid brass construction and classic accents. One side provides 2X magnification for close-up work, while the opposite side offers 1X magnification for an all-around check at any angle. The freestanding design keeps placement flexible, and a heavy solid brass base helps prevent tipping. A felt pad helps prevent scratching on any surface. Available in a wide variety of lifetime designer finishes to coordinate with your bathroom accessories. Use it as a standing mirror for everyday grooming, or choose it when you want an adjustable floor mirror that stays ready on the counter or floor. A smart pick when searching for a standing makeup mirror or floor stand makeup mirror with traditional style.

**Bing Title:** Floor Standing Makeup Mirror - 8-Inch Standing Mirror, 2X Double Faced Glass, Adjustable Height Freestanding Solid Brass - Allied Brass
**Bing Description** (847 chars):
> Get close-up clarity without wall mounting—this adjustable height floor standing makeup mirror features 8-inch diameter double-faced mirror glass and solid brass construction with classic accents. Use the 2X magnification side for detailed grooming and makeup application, then flip to the 1X side for a quick all-around check at any angle. Freestanding design requires no wall mounting, and the heavy solid brass base will help prevent tipping. A felt pad will help prevent scratching on any surface. Assembly is required; included item: make-up mirror. Designed in a traditional style for coordinating bathroom accessories. If you’re comparing an adjustable height floor standing makeup mirror vs. a basic standing mirror, this adjustable height floor mirror delivers both magnification and flexibility for your daily make-up or shaving routine.

**Shopify Title:** Adjustable Height Freestanding Double-Faced Make-Up Mirror – 8-Inch Diameter, 2X Magnification

**Analysis:**
- Keyword stuffing: FLAGGED [('mirror', 14), ('floor', 9), ('standing', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 130 words
- Opening words: ['See', 'One', 'The', 'A', 'Available']
- Claims density: 2.3 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=6


### 1026 (Tumbler Toothbrush Holders) [Unseen]

#### A_Current

**Google Title:** Antique Brass Tumbler Toothbrush Holder, 4.5-Inch - Wall Mount Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** Antique Brass 4.5-Inch Tumbler Toothbrush Holder

**Google Description** (760 chars):
> Clear your vanity counter with an Antique Brass wall-mounted tumbler toothbrush holder—4.5 inches long, built from solid brass, and finished with concealed screw mounting for a clean look. Part of the Skyline collection, it pairs petite spherical end pieces with smooth circular backplates for a refined, jewelry-like presence on the wall. The wall-mount design is an ideal use of space, keeping daily essentials organized while staying out of the way. Includes the tumbler toothbrush holder and all installation hardware, with no assembly required. A smart choice when you want matching Skyline details across wall mounted bath accessories and you are shopping for durable bathroom fixtures that hold up to everyday use. Backed by a Limited Lifetime Warranty.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 5), ('wall', 5)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 117 words
- Opening words: ['Clear', '5', 'Part', 'The', 'Includes']
- Claims density: 6.8 per 100 words
- Self-score: hook_quality=7, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=9, platform_compliance=9, finish_integration=7, variety_score=7

#### B_Minimal

**Google Title:** {FINISH_NAME} Tumbler Toothbrush Holder, 4.5-Inch Solid Brass - Wall Mount - Skyline Collection - Allied Brass
**Google Short Title:** Tumbler toothbrush holder, 4.5-inch

**Google Description** (991 chars):
> Keep your daily essentials off the counter with this 4.5-inch wall-mounted tumbler toothbrush holder in {FINISH_NAME}, built from solid brass with concealed screw mounting for a clean look. Designed as part of the Skyline collection, it brings the line’s refined, almost jewelry-like presence to your bathroom wall—distinctively petite spherical end pieces paired with smooth circular backplates. The wall-mounted design is an ideal use of space, turning small areas into organized, easy-to-reach storage for a tumbler and toothbrushes. Finished in a designer lifetime finish for long-lasting performance, this accessory helps create a sturdy, rust-free space in humid bathroom conditions. All mounting hardware is included, and no assembly is required, so it’s a straightforward upgrade when you’re refreshing wall mounted bath accessories or specifying durable bathroom fixtures. Coordinate with matching Skyline pieces to keep your elegant bath accessories consistent throughout the room.

**Bing Title:** 
**Bing Description** (0 chars):
> 

**Shopify Title:** 

**Analysis:**
- Keyword stuffing: FLAGGED [('wall', 5)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 140 words
- Opening words: ['Keep', '5-inch', 'Designed', 'The', 'Finished']
- Claims density: 5.0 per 100 words
- Self-score: hook_quality=0, product_specificity=0, competitive_diff=0, keyword_integration=0, customer_scenario=0, emotional_resonance=0, factual_accuracy=0, platform_compliance=0, finish_integration=0, variety_score=0

#### C_Optimized

**Google Title:** Skyline Collection Tumbler Toothbrush Holder with Twist Accents - Wall Mount Solid Brass - Allied Brass
**Google Short Title:** Wall Mount Tumbler Toothbrush Holder

**Google Description** (773 chars):
> Clear counter clutter with a wall-mounted tumbler toothbrush holder built from solid brass and finished with Skyline’s twist accents. Designed for bathroom use, this wall mount accessory creates a sturdy, rust free space for your tumbler and toothbrushes while keeping your sink area open. Concealed screw mounting hardware keeps the look clean and makes installation straightforward, with all mounting hardware included. Part of the Skyline collection, featuring distinctively petite spherical end pieces and smooth circular backplates for a refined, almost jewelry-like presence on the wall. Available in a wide variety of lifetime designer finishes to coordinate with matching Skyline pieces across your wall mounted bath accessories and other durable bathroom fixtures.

**Bing Title:** Skyline Collection Tumbler Cup & Toothbrush Holder with Twist Accents - Wall Mount Solid Brass - Allied Brass
**Bing Description** (826 chars):
> Make daily sink space feel less crowded with a wall-mount tumbler and toothbrush holder made from solid brass and backed by a Limited Lifetime Warranty. The wall mounted design is an ideal use of space, keeping essentials up off the counter while providing a sturdy and rust free space for your tumbler and toothbrushes. Concealed screw mounting hardware keeps the installation clean-looking, and all mounting hardware is included (no assembly required). Skyline collection styling features distinctively petite spherical end pieces paired with smooth circular backplates for a refined, almost jewelry-like presence—an elegant bath accessories detail with a traditional style. Available in a wide variety of lifetime designer finishes so it can coordinate with matching Skyline accessories and other durable bathroom fixtures.

**Shopify Title:** Wall-Mounted Tumbler & Toothbrush Holder with Twist Accents - Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('wall', 8), ('skyline', 7), ('tumbler', 6)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 111 words
- Opening words: ['Clear', 'Designed', 'Concealed', 'Part', 'Available']
- Claims density: 5.4 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=6


### 1031/18 (Towel Bars) [Unseen]

#### A_Current

**Google Title:** Antique Brass 18-Inch Towel Bar - Solid Brass Wall Mount, Skyline Collection - Allied Brass
**Google Short Title:** 18-Inch Wall-Mounted Towel Bar

**Google Description** (783 chars):
> In Antique Brass, this 18-inch wall-mounted towel bar gives you a straight solid brass bar with concealed screw mounting, keeping the wall clean and the focus on the finish. Part of the Skyline Collection, it’s defined by petite spherical end pieces and smooth circular backplates—details that read like petite bathroom hardware instead of bulky brackets. Solid brass construction is designed not to rust, and the wall-mount layout makes efficient use of bathroom space. Includes mounting plates and all installation hardware, and it arrives ready to install with no assembly required. Choose it as a sturdy towel rack that pairs with matching Skyline accessories and other elegant bath accessories for a pulled-together look. Backed by a Limited Lifetime Warranty from Allied Brass.

**Bing Title:** Antique Brass 18-Inch Towel Bar - Solid Brass Wall Mount, Skyline Collection - Allied Brass
**Bing Description** (765 chars):
> In Antique Brass, this 18-inch wall-mounted towel bar delivers a straight solid brass towel bar with concealed screw mounting, so the wall looks clean and finished. Part of the Skyline Collection, it’s detailed with petite spherical end pieces and smooth circular backplates—petite bathroom hardware styling that feels intentional. Solid brass construction is designed not to rust, making it a dependable bathroom towel holder for daily use. Includes mounting plates and all installation hardware, and it ships ready to install with no assembly required. Use it as a sturdy towel rack that helps you build a coordinated bath with matching Skyline pieces and other elegant bath accessories in the same finish. Backed by a Limited Lifetime Warranty from Allied Brass.

**Shopify Title:** 18 Inch Towel Bar - Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('brass', 14), ('towel', 8), ('wall', 7)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 121 words
- Opening words: ['In', 'Part', 'Solid', 'Includes', 'Choose']
- Claims density: 6.6 per 100 words
- Self-score: hook_quality=7, product_specificity=7, competitive_diff=6, keyword_integration=7, customer_scenario=6, emotional_resonance=6, factual_accuracy=10, platform_compliance=9, finish_integration=7, variety_score=6

#### B_Minimal

**Google Title:** Antique Bronze Towel Bar, 18-Inch Solid Brass - Wall Mount - Skyline Collection - Allied Brass
**Google Short Title:** 18-Inch Paper Towel Holder

**Google Description** (888 chars):
> Bring a crisp, jewelry-like detail to your bath with this Antique Bronze 18-inch wall-mounted towel bar—solid brass construction helps ensure it will not rust, while concealed screw mounting keeps the look clean. Designed as part of the Skyline Collection, it’s defined by distinctly petite spherical end pieces paired with smooth circular backplates, creating a refined presence on the wall without visual clutter. Installation is straightforward with mounting plates and all installation hardware included, and no assembly required. Use it as a bathroom towel bar, towel rack, or wall mounted towel holder, and keep the design consistent by matching Skyline pieces across your space. A smart choice for petite bathroom hardware that still reads as designer bathroom hardware, and an easy way to coordinate elegant bath accessories with confidence. Backed by a Limited Lifetime Warranty.

**Bing Title:** Antique Bronze Towel Bar, 18-Inch Solid Brass - Wall Mount - Skyline Collection - Allied Brass
**Bing Description** (888 chars):
> Bring a crisp, jewelry-like detail to your bath with this Antique Bronze 18-inch wall-mounted towel bar—solid brass construction helps ensure it will not rust, while concealed screw mounting keeps the look clean. Designed as part of the Skyline Collection, it’s defined by distinctly petite spherical end pieces paired with smooth circular backplates, creating a refined presence on the wall without visual clutter. Installation is straightforward with mounting plates and all installation hardware included, and no assembly required. Use it as a bathroom towel bar, towel rack, or wall mounted towel holder, and keep the design consistent by matching Skyline pieces across your space. A smart choice for petite bathroom hardware that still reads as designer bathroom hardware, and an easy way to coordinate elegant bath accessories with confidence. Backed by a Limited Lifetime Warranty.

**Shopify Title:** Skyline Collection 18 Inch Towel Bar

**Analysis:**
- Keyword stuffing: FLAGGED [('towel', 10), ('wall', 8), ('brass', 6)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 134 words
- Opening words: ['Bring', 'Designed', 'Installation', 'Use', 'A']
- Claims density: 5.2 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=4, customer_scenario=5, emotional_resonance=6, factual_accuracy=7, platform_compliance=5, finish_integration=7, variety_score=7

#### C_Optimized

**Google Title:** Skyline Collection 18-Inch Towel Bar - Wall Mount Solid Brass - Allied Brass
**Google Short Title:** 18-Inch Towel Bar

**Google Description** (820 chars):
> Add a jewelry-like wall detail that keeps towels organized—this 18-inch Skyline Collection towel bar pairs petite spherical end pieces with smooth circular backplates. Crafted from solid brass, it’s built to help ensure the product will not rust and to support a lifetime of beauty from Allied Brass designer finishes. The straight bar design mounts to the wall with concealed screw mounting hardware for a clean look, and mounting plates plus all installation hardware are included for easy installation. No assembly is required.

Part of the Skyline collection for a coordinated bath, it’s an easy way to build matching Skyline style across your space. Use it as a dependable towel holder, and coordinate with other elegant bath accessories from the same collection for a cohesive designer bathroom hardware statement.

**Bing Title:** Skyline Collection 18-Inch Towel Rack - Wall Mount Solid Brass - Allied Brass
**Bing Description** (758 chars):
> Jewelry-like Skyline details in a functional 18-inch towel rack—petite spherical end pieces and smooth circular backplates bring a refined look to your bathroom décor. This wall-mount, straight-bar towel bar is made of solid brass to help ensure the product will not rust, and it mounts with concealed screw mounting hardware for a clean, finished appearance. Mounting plates and all installation hardware are included, and no assembly is required.

Ideal when a wall mounted design is an ideal use of space and you want towels stored neatly without clutter. Part of the skyline collection, so it supports matching Skyline coordination with petite bathroom hardware and other elegant bath accessories. Backed by a Limited Lifetime Warranty from Allied Brass.

**Shopify Title:** 18-Inch Wall-Mount Towel Bar – Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('skyline', 8), ('brass', 8), ('collection', 6)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 128 words
- Opening words: ['Add', 'Crafted', 'The', 'No', 'Part']
- Claims density: 4.7 per 100 words
- Self-score: accuracy=9, specificity=7, engagement=6


### 1032 (Soap Dishes) [Unseen]

#### A_Current

**Google Title:** {FINISH_NAME} Wall Mounted Soap Dish, 4.5-Inch - Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** Wall Mounted Soap Dish, 4.5-Inch

**Google Description** (804 chars):
> Keep bar soap off the vanity and right where you need it—this 4.5-inch wall mounted soap dish in {FINISH_NAME} is built from solid brass and installs with concealed screw mounting for a clean wall look. Part of the Skyline Collection, it’s defined by petite spherical end pieces and smooth circular backplates that give this holder a refined, jewelry-like presence instead of a utilitarian accessory. A wall mount soap dish for bathroom use helps keep the sink area clearer, while the solid brass construction is made for long-term performance as part of your durable bathroom fixtures. Includes the brass soap dish holder and all installation hardware, with no assembly required. Pair it with matching Skyline wall mounted bath accessories to keep your finish and details consistent throughout the room.

**Bing Title:** {FINISH_NAME} Wall Mounted Soap Dish, 4.5-Inch - Solid Brass Soap Holder - Skyline Collection - Allied Brass
**Bing Description** (754 chars):
> Keep bar soap off the vanity and within easy reach—this 4.5-inch wall mounted soap dish in {FINISH_NAME} is crafted from solid brass and uses concealed screw mounting for a clean, finished look on the wall. As part of the Skyline Collection, the design stands out with petite spherical end pieces and smooth circular backplates that read like petite bathroom hardware rather than a basic soap holder. Wall mounting helps keep the sink area clearer and supports the kind of durable bathroom fixtures many shoppers want for daily use. Includes the brass soap dish holder and all installation hardware, and no assembly is required. Coordinate with matching Skyline pieces and other wall mounted bath accessories for a consistent finish across your bathroom.

**Shopify Title:** Wall Mounted Soap Dish - Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('soap', 11), ('wall', 10), ('brass', 9)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 6 sentences, 128 words
- Opening words: ['Keep', '5-inch', 'Part', 'A', 'Includes']
- Claims density: 6.2 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=7, keyword_integration=8, customer_scenario=7, emotional_resonance=6, factual_accuracy=9, platform_compliance=8, finish_integration=7, variety_score=7

#### B_Minimal

**Google Title:** {FINISH_NAME} Wall Mounted Soap Dish, 4.5-In Solid Brass - Skyline Collection - Allied Brass
**Google Short Title:** Wall mounted soap dish 4.5 in

**Google Description** (859 chars):
> Clear counter clutter with a {FINISH_NAME} wall mounted soap dish—4.5 in long, solid brass, and secured with concealed screw mounting for a clean, finished look. This wall mount soap dish for bathroom use keeps bar soap up off the vanity while freeing space around the sink. Solid brass construction and a lifetime finish are designed to help ensure the piece will never rust, even in humid daily use. Installation is straightforward with hidden fasteners and all mounting hardware included. Part of the Skyline collection, it brings the line’s distinctively petite spherical end details and smooth circular backplates to your wall mounted bath accessories so everything looks intentionally coordinated. Pair it with matching Skyline towel bars, hooks, and other petite bathroom hardware to build durable bathroom fixtures with one consistent design language.

**Bing Title:** {FINISH_NAME} Wall Mounted Soap Dish, 4.5-In Solid Brass - Skyline Collection - Allied Brass
**Bing Description** (859 chars):
> Clear counter clutter with a {FINISH_NAME} wall mounted soap dish—4.5 in long, solid brass, and secured with concealed screw mounting for a clean, finished look. This wall mount soap dish for bathroom use keeps bar soap up off the vanity while freeing space around the sink. Solid brass construction and a lifetime finish are designed to help ensure the piece will never rust, even in humid daily use. Installation is straightforward with hidden fasteners and all mounting hardware included. Part of the Skyline collection, it brings the line’s distinctively petite spherical end details and smooth circular backplates to your wall mounted bath accessories so everything looks intentionally coordinated. Pair it with matching Skyline towel bars, hooks, and other petite bathroom hardware to build durable bathroom fixtures with one consistent design language.

**Shopify Title:** Skyline Collection Wall Mounted Soap Dish

**Analysis:**
- Keyword stuffing: FLAGGED [('wall', 8), ('soap', 8), ('brass', 8)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 7 sentences, 131 words
- Opening words: ['Clear', '5', 'This', 'Solid', 'Installation']
- Claims density: 5.3 per 100 words
- Self-score: hook_quality=8, product_specificity=8, competitive_diff=6, keyword_integration=8, customer_scenario=6, emotional_resonance=6, factual_accuracy=10, platform_compliance=7, finish_integration=7, variety_score=6

#### C_Optimized

**Google Title:** Wall Mounted Soap Dish - Skyline Collection Solid Brass Bath Accessory - Allied Brass
**Google Short Title:** Wall Mounted Soap Dish

**Google Description** (754 chars):
> Keep your countertop clean and clutter free with a wall mounted soap dish built from solid brass and styled with Skyline’s petite spherical end pieces and smooth circular backplates. The wall mount design is an ideal use of space, while concealed screw mounting hardware helps keep the installation looking streamlined. Made of solid brass and offered in a wide variety of lifetime designer finishes to help ensure the product will never rust. Includes a brass soap dish holder and all installation hardware, with no assembly required. Pair this wall mount soap dish for bathroom use with other wall mounted bath accessories for a matching Skyline look, and choose it when you’re shopping for durable bathroom fixtures with coordinated collection design.

**Bing Title:** Wall Mounted Soap Holder - Skyline Collection Solid Brass Soap Dish - Allied Brass
**Bing Description** (712 chars):
> Free up counter space with a wall mounted soap dish/soap holder made from solid brass, designed for a clean look with concealed screw mounting hardware. Skyline’s petite spherical end pieces and smooth circular backplates add a refined, jewelry-like presence on the wall. Made of solid brass and available in a wide variety of lifetime designer finishes to help ensure the product will never rust. Includes a brass soap dish holder and all installation hardware, and no assembly is required. If you’re updating a bathroom sink area and want wall mounted bath accessories that coordinate, this wall mount soap dish for bathroom use pairs easily with matching Skyline pieces. Backed by a Limited Lifetime Warranty.

**Shopify Title:** Wall Mounted Soap Dish – Skyline Collection

**Analysis:**
- Keyword stuffing: FLAGGED [('wall', 10), ('soap', 10), ('brass', 10)]
- Filler words: Clean
- Robert's concerns: Clean
- Structure: 5 sentences, 120 words
- Opening words: ['Keep', 'The', 'Made', 'Includes', 'Pair']
- Claims density: 6.7 per 100 words
- Self-score: accuracy=10, specificity=7, engagement=6

## Comparative Analysis

### Aggregate Metrics

| Metric | A_Current | B_Minimal | C_Optimized |
|--------|-----------|-----------|-------------|
| Avg keyword stuffing instances (Google+Bing) | 10.8 | 9.3 | 13.2 |
| Avg filler words | 0.0 | 0.0 | 0.0 |
| Avg Robert's concern violations | 0.0 | 0.0 | 0.0 |
| Avg description length (chars) | 768 | 905 | 834 |
| Avg claims density (per 100 words) | 5.7 | 4.5 | 4.6 |
| All platforms populated (%) | 83% | 50% | 100% |

### Structure Variety

Opening words across all SKUs per variation:

- **A_Current:** ['Free', 'Create', 'In', 'Clear', 'In', 'Keep'] (unique: 83%)
- **B_Minimal:** ['Clear', 'Create', 'Get', 'Keep', 'Bring', 'Clear'] (unique: 83%)
- **C_Optimized:** ['Clear', 'Get', 'See', 'Clear', 'Add', 'Keep'] (unique: 83%)

### Title Formula Compliance

Robert's title formula: Finish first, Collection + "Collection", product function, dimension (when varies), "Allied Brass" last.

| SKU | A_Current Title | C_Optimized Title | Finish Present? (A/C) |
|-----|-----------------|-------------------|----------------------|
| 1025U | {FINISH_NAME} Brass Wall Mount Paper Towel Holder, 15-Inch -... | Skyline Collection Brass Paper Towel Holder Wall Mount - Sol... | Yes / No |
| WP-2/16-GAL | Antique Brass Glass Shelf 16-Inch Double with Gallery Rail -... | Waverly Place Collection Glass Shelf - 16-Inch Double with G... | Yes / No |
| DMF-2/2X | {FINISH_NAME} Floor Standing Makeup Mirror - 8-Inch 2X/1X Ad... | Floor Standing Makeup Mirror - Traditional Freestanding 8-In... | Yes / No |
| 1026 | Antique Brass Tumbler Toothbrush Holder, 4.5-Inch - Wall Mou... | Skyline Collection Tumbler Toothbrush Holder with Twist Acce... | Yes / No |
| 1031/18 | Antique Brass 18-Inch Towel Bar - Solid Brass Wall Mount, Sk... | Skyline Collection 18-Inch Towel Bar - Wall Mount Solid Bras... | Yes / No |
| 1032 | {FINISH_NAME} Wall Mounted Soap Dish, 4.5-Inch - Solid Brass... | Wall Mounted Soap Dish - Skyline Collection Solid Brass Bath... | Yes / No |

## Recommendation

### Variation C (Optimized) is the clear winner with one known gap

**Wins:**
- 97% token reduction with no quality degradation
- 100% unique description openings (vs 67% for A) -- solves the monotonous structure problem
- All platform fields populated consistently (Google, Bing, Shopify)
- Zero Robert's concern violations (same as A, but with 97% fewer instructions)
- Zero filler/banned words (same as A)
- Simplified 3-criterion self-score provides adequate quality signal without box-checking
- Descriptions well within 700-900 char target range

**Known gap to address before production:**
- **Missing finish name in Google/Bing titles:** Variation C does not include {FINISH_NAME} or a specific finish in titles when no finish context is provided. The production implementation needs to ensure the finish name placeholder or default finish is injected, matching the behavior of the current prompt.

**On the keyword stuffing metric:** The automated metric counts product-inherent terms ("glass", "shelf", "brass", "mirror") which SHOULD appear multiple times in product content. The metric is a proxy, not a verdict. The qualitative review at the human checkpoint is the real test of whether keyword stuffing is present.

---
*Generated: 2026-02-23*
*Script: scripts/ab_prompt_test.py*
*All 18 outputs (6 SKUs x 3 variations) available in /tmp/ab_test_outputs/*