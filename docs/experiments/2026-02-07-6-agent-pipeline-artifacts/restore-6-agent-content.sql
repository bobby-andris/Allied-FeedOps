-- Restore 6-agent pipeline content from backup
-- Created: 2026-02-07
-- Purpose: Restore high-quality agent-generated content if overwritten by regenerate all

DO $$
BEGIN
  -- SKU 1016 (Quality: 87)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} 6-Inch Towel Ring - Solid Brass Construction, Commercial-Grade Mounting - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 87
  WHERE master_sku = '1016' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This 6-inch towel ring is crafted from solid brass—not hollow tubing or plated plastic—weighing 1.6 pounds to resist deflection when pulling wet bath towels. The concealed three-point mounting system distributes force across a 7-inch vertical span, preventing the single-screw failures common in budget alternatives. Installers report zero callbacks after 5+ years in high-traffic hotel environments, with commercial-grade engineering tested to 10 pounds. The perfectly circular 6-inch diameter prevents towel binding and fabric twisting, while the compact 1.5-inch projection minimizes pull-out stress by 60% compared to deeper designs. Homeowners appreciate how decorative hand towels drape beautifully without bunching, and the finish coordinates seamlessly with faucets and fixtures for a professionally designed look. Whether you're refreshing seasonal towels or need rock-solid durability for daily family use, this ring maintains structural integrity and finish quality year after year.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 87
  WHERE master_sku = '1016' AND platform = 'google' AND content_type = 'description';

  -- SKU 102 (Quality: 84)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} 1.5-Inch Cabinet Knob - Extended 2.25-Inch Projection, Solid Brass Construction - Cabinet Hardware - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 84
  WHERE master_sku = '102' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This 1.5-inch cubic knob extends 2.25 inches from the cabinet face—50% longer projection than standard knobs—providing clearance for thick doors or inset frames where standard hardware would bind against adjacent doors. The 0.375-inch diameter mounting post is 20% thicker than typical extended knobs, preventing the flexing and wobble contractors see in cheaper alternatives under repeated use. Rolled threads extending 1.875 inches provide 40% more engagement than cut-thread designs, preventing loosening across door thicknesses from 0.5 to 1.5 inches. At 0.8 pounds of solid brass concentrated at the grip, the knob provides substantial tactile feedback without straining cabinet hinges, and contractors report zero callbacks for thread stripping across 10+ years of kitchen installations. Homeowners who replace all their cabinet hardware with these knobs see immediate transformation: 24 dated brass knobs swapped for fresh coordinated finish, installed in one afternoon, completely updating the room''s aesthetic. The solid brass construction and consistent finish quality coordinate perfectly with bathroom faucets, towel bars, and light fixtures for that professionally designed cohesive look where every detail works together.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 84
  WHERE master_sku = '102' AND platform = 'google' AND content_type = 'description';

  -- SKU 1020 (Quality: 90)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} Robe Hook - 2.3-Inch Projection, 35-Degree Anti-Slip Curve - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 90
  WHERE master_sku = '1020' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This robe hook projects 2.3 inches from the wall with a 35-degree upward curve—shallow enough to prevent robe collars from catching during hanging, steep enough to keep garments from sliding off under the 5-pound weight of a wet bathrobe. The solid brass construction weighs 0.8 pounds concentrated at the wall mounting point, creating pendulum stability that resists tipping under asymmetric loads. Contractors report zero warranty claims for bent or broken hooks across 7+ years of installations, with commercial-grade engineering tested to 20 pounds—far exceeding typical use but providing safety margin for wet winter coats in mudroom applications. The 0.625-inch diameter shaft tapering to a 0.375-inch tip provides structural strength at the base while minimizing bulk at the garment contact point, and the 2.8-inch escutcheon plate distributes compression stress to prevent wallboard dimpling. Homeowners install these on bathroom doors to keep robes from dampening towels, or in mudrooms as multi-purpose catch-all hooks for jackets and bags. The compact projection won''t hit you when opening the door, and the finish coordinates with other fixtures for that subtle elegance that makes daily routines just a bit smoother.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 90
  WHERE master_sku = '1020' AND platform = 'google' AND content_type = 'description';

  -- SKU 1020-3 (Quality: 98 - GOLD STANDARD)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} 3 Position Multi Hook - 8-Inch Length, 6-Pound Total Capacity - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 98
  WHERE master_sku = '1020-3' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This 8-inch bar with three hooks provides 6 pounds total capacity—2 pounds per hook—tested with winter coats in mudroom applications without deflection or bending. Each hook projects 2.5 inches with a 35-degree upward angle optimized for robe collars and towel loops, spaced 2.5 inches apart on center to prevent garment overlap while maximizing wall span efficiency. The solid brass construction weighs 1 pound with mass concentrated at the mounting rail, creating a rigid backbone that prevents the flexing common in hollow zinc castings even when loads are applied asymmetrically to end hooks. Contractors report the same zero-callback record as single hooks across 7+ years—the engineering doesn''t compromise with increased hook count. Two concealed #8 x 1.25-inch screws spaced 6 inches apart keep fastener shear stress below 100 pounds even at maximum load. Homeowners install these next to showers for his-and-hers towel organization, in mudrooms for coats and bags, in laundry rooms for cleaning cloths—the traditional styling works in any room. Kids actually hang up their towels now because each hook is clearly designated, and wet towels stay put without sagging or wobbling thanks to commercial-grade solid brass durability.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 98
  WHERE master_sku = '1020-3' AND platform = 'google' AND content_type = 'description';

  -- SKU 1024 (Quality: 83)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} 8-Inch Two Post Toilet Tissue Holder - No Spring Mechanism, Dual-Post Stability - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 83
  WHERE master_sku = '1024' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'Spring-loaded tissue holders fail after 6-12 months, leaving empty cardboard tubes sitting there because nobody wants to fight the spring. This dual-post holder eliminates that frustration entirely with a solid bar design that makes roll changes effortless—your family will actually replace the roll now. The 8-inch span between posts distributes 1.6 pounds of solid brass weight across two independent mounting points, preventing the cantilever failure and bending common in single-post zinc alternatives. Contractors report zero callbacks across 5+ years in commercial office buildings, with concealed #8 x 1.25-inch screws providing clean aesthetics architects appreciate. The 3.5-inch projection provides knuckle clearance during dispensing, while the 2.8-inch height accommodates mega rolls up to 5.5 inches in diameter without floor contact. Homeowners love how the finish coordinates perfectly with sink faucets and vanity hardware, creating that pulled-together spa feeling where every detail feels intentional rather than pieced together.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 83
  WHERE master_sku = '1024' AND platform = 'google' AND content_type = 'description';

  -- SKU 1024E (Quality: 85)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} Euro Style Toilet Tissue Holder - Quick-Release Hook, 2-Second Roll Changes - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 85
  WHERE master_sku = '1024E' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'Traditional spring-loaded bars make roll changes an 8-second wrestling match. This Euro-style hook design reduces that to 2 seconds—lift the cantilever arm, drop the new roll on, done. Inspired by European hotel bathrooms where changing rolls is effortless, the quick-release mechanism uses oil-impregnated bronze bushings rated for 10,000 cycles, eliminating the metal-on-metal squeaking that plagues cheaper alternatives. The 5-inch cantilever projection—40% deeper than standard holders—enables single-handed loading without wall interference, while the ball-detent mechanism requires just 3 pounds of lift force to release. Contractors report 8-year-old units still operating smoothly in residential bathrooms, with 1.6 pounds of solid brass balanced across an 8-inch span to prevent single-screw failure. Homeowners who switch to this style never go back: when your teenage daughter burns through rolls daily, ease of replacement becomes a genuine quality-of-life improvement. The concealed mounting and finish coordination with vanity hardware create that spa-like aesthetic where function and beauty align perfectly.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 85
  WHERE master_sku = '1024E' AND platform = 'google' AND content_type = 'description';

  -- SKU 1025U (Quality: 88)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} Wall Mounted Paper Towel Holder - 15-Inch Vertical Post, One-Handed Tearing - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 88
  WHERE master_sku = '1025U' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This wall-mounted vertical holder frees up valuable counter space while enabling one-handed paper dispensing—critical when your hands are messy from cooking or cleaning. The 15-inch tall post with 2.75-inch square base geometry creates a low center of gravity and wide stability footprint, with 2.4 pounds of solid brass at the base counterbalancing full mega rolls weighing up to 1.5 pounds at the 5-inch cantilever. The solid construction means you can tear off paper one-handed without the holder spinning or tilting, and the spring-loaded ball-detent spindle requires just 2 pounds of axial force to release for quick roll changes while preventing accidental drops. Contractors report zero callbacks for tipping or bending across 4+ years of installations in kitchens, bathrooms, laundry rooms, and workshops—the multi-room versatility reduces the SKU count needed. Homeowners mount these right next to the kitchen sink where paper towels are needed most, and the finish coordinates with cabinet hardware for that cohesive updated look. The square post geometry resists torsional twisting under aggressive tearing better than round posts, maintaining alignment throughout the roll.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 88
  WHERE master_sku = '1025U' AND platform = 'google' AND content_type = 'description';

  -- SKU 1026 (Quality: 89)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} Wall Mounted Tumbler and Toothbrush Holder - Counter Space Saving, Twist Accents - Skyline Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 89
  WHERE master_sku = '1026' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'Wall-mounting your toothbrush holder frees up 35-40 square inches of vanity counter space, eliminating the water and toothpaste splatter that collects underneath countertop holders. This dual-zone design combines a 3.5-inch diameter tumbler well with four individual 0.75-inch toothbrush wells—each with drainage holes to prevent water pooling and bacterial growth—all extending just 5 inches from the wall. The triangulated two-screw mounting pattern converts the 5-inch cantilever into manageable shear forces, while 2.4 pounds of solid brass provides stability without requiring heavy-duty wall anchors. Contractors report 6+ years of reliable performance in hotel applications with daily guest use and housekeeping cleaning, and the twist accent decorative elements provide 25% more torsional rigidity than smooth cylinders. Homeowners love clearing out the clutter of electric toothbrush bases and countertop cups: your morning routine becomes more organized, your vanity looks intentional, and cleaning becomes easier when there''s nothing underneath to collect grime. The finish with twist accents coordinates perfectly with other Skyline fixtures for that classic look that won''t go out of style.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 89
  WHERE master_sku = '1026' AND platform = 'google' AND content_type = 'description';

  -- SKU MC-60 (Quality: 86)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} Wall Mounted Soap Dispenser - 5-Ounce Capacity, Counter Space Saving - Monte Carlo Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 86
  WHERE master_sku = 'MC-60' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'Wall-mounting your soap dispenser eliminates the plastic bottle clutter and ring stains from condensation that plague bathroom counters. This 5-ounce capacity vertical cylinder—3 inches diameter by 7 inches tall—provides 300 pumps between refills, roughly 2 weeks for a family bathroom, while projecting just 4 inches from the wall. The 304 stainless steel pump mechanism is rated for 50,000 cycles, outlasting plastic assemblies by 10x with consistent 0.5ml per stroke dispensing, and the threaded bottle interface with EPDM O-ring sealing enables refills without removing the wall bracket. Contractors install 50-60 units monthly and report zero callbacks for leaks or pump failures, even in commercial office bathrooms after 5+ years of daily use. The 2.4-pound solid brass mounting bracket creates a center of gravity below midpoint even when full, reducing cantilever stress on mounting screws and resisting the corrosion common in chrome-plated plastic dispensers. Homeowners appreciate the weekly refill convenience and how teenagers actually use soap now that it''s so easy to access right by the sink. The Monte Carlo styling brings classic elegance to daily tasks, and the finish coordinates with other fixtures for that refined, intentional look.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 86
  WHERE master_sku = 'MC-60' AND platform = 'google' AND content_type = 'description';

  -- SKU WP-1/16 (Quality: 82)
  UPDATE generated_content
  SET candidate_content = '{FINISH_NAME} 16-Inch Glass Vanity Shelf - 3/8-Inch Tempered Glass, Beveled Edges - Waverly Place Collection - Allied Brass',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 82
  WHERE master_sku = 'WP-1/16' AND platform = 'google' AND content_type = 'title';

  UPDATE generated_content
  SET candidate_content = 'This 16-inch glass shelf uses 3/8-inch thick tempered glass—50% thicker than standard shelving—to achieve a deflection limit of 0.125 inches at maximum 2-pound load, preventing the visible sag that undermines perceived quality. The 1-inch wide beveled edge treatment at 45 degrees creates prismatic light refraction that adds visual depth, catching light beautifully throughout the day. Solid brass mounting brackets extend 5 inches from the wall with a 2.5-inch vertical face, distributing compressive force across 12.5 square inches of glass contact area to stay below the 200 PSI fracture threshold. Contractors report zero cracked or chipped shelves across 200+ installations in residential and commercial bathrooms, even in high-traffic hotel environments. The concealed two-piece bracket design enables tool-free glass removal for cleaning while eliminating visible clips for that clean aesthetic. Homeowners install these above powder room sinks to display curated items—everyday hand soap, a small succulent, a decorative candle—transforming small spaces from functional to spa-like. The installation takes 15 minutes, and guests always comment on how organized and intentional the space feels.',
      generation_model = '6-agent-pipeline-gpt-4',
      quality_score = 82
  WHERE master_sku = 'WP-1/16' AND platform = 'google' AND content_type = 'description';

  RAISE NOTICE 'Restored 6-agent pipeline content for 10 SKUs (20 rows total)';
END $$;

-- Verify restoration
SELECT
  master_sku,
  content_type,
  generation_model,
  quality_score,
  LENGTH(candidate_content) as content_length
FROM generated_content
WHERE master_sku IN ('1016', '1024', '1024E', '102', '1020', '1026', 'MC-60', 'WP-1/16', '1020-3', '1025U')
  AND platform = 'google'
ORDER BY master_sku, content_type;
