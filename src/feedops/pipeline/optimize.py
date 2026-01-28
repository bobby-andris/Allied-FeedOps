"""Main optimization pipeline orchestrator."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from feedops.integrations.merchant_center import (
    DEFAULT_MC_METADATA_PATH,
    load_merchant_center_snapshot,
)
from feedops.loaders.unified_loader import load_parent_sku_unified_with_status
from feedops.models import Candidate
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.generator import build_prompt, generate_candidates
from feedops.pipeline.keyword_placement import build_keyword_placement_plan
from feedops.pipeline.reporter import (
    generate_all_variant_patches,
    generate_patch_preview,
    generate_report,
)
from feedops.pipeline.selection import (
    parse_candidate_weights,
    parse_num_candidates,
    select_best_candidate,
)
from feedops.pipeline.verifier import verify_claims
from feedops.providers import get_provider


@dataclass
class OptimizationResult:
    """Result of a single SKU optimization."""

    master_sku: str
    data_source: str | None
    candidate: Candidate
    verification_errors: list[str]
    report: str
    patch_previews: dict[str, dict]
    timestamp: str


def estimate_llm_cost(
    provider_name: str | None,
    token_usage: dict[str, int] | None,
) -> float | None:
    """Estimate LLM cost from usage and known model pricing."""
    if not provider_name or not token_usage:
        return None
    if not isinstance(token_usage, dict):
        return None

    prompt_tokens = token_usage.get("prompt_tokens")
    completion_tokens = token_usage.get("completion_tokens")
    if prompt_tokens is None or completion_tokens is None:
        return None

    model_name = provider_name.split("/", 1)[-1]
    pricing = {
        "gpt-5.2": {"input": 1.75, "output": 14.0},
        "gemini-3-flash-preview": {"input": 0.50, "output": 3.0},
    }
    rates = pricing.get(model_name)
    if not rates:
        return None

    return (prompt_tokens / 1_000_000) * rates["input"] + (
        completion_tokens / 1_000_000
    ) * rates["output"]


async def optimize_parent_sku(
    master_sku: str,
    catalog_path: Path | str,
    dry_run: bool = True,
    output_dir: Path | str = "reports",
    exports_dir: Path | str = "exports",
    num_candidates: int | None = None,
    candidate_weights: dict[str, float] | None = None,
    force_refresh: bool = False,
) -> OptimizationResult:
    """Run full optimization pipeline for a parent SKU.

    Pipeline steps:
    1. Load catalog and extract ParentSKU
    2. Generate candidate via LLM
    3. Validate customer-facing content
    4. Verify claims against source data
    5. Generate report and patch preview
    6. Save outputs to files
    7. Log to database

    Args:
        master_sku: The MasterSKU to optimize.
        catalog_path: Path to Product Catalog CSV.
        dry_run: If True, preview only (no MC updates).
        output_dir: Directory for output files.
        exports_dir: Directory for export patch JSON files.
        force_refresh: If True, bypass cache and refresh API data.

    Returns:
        OptimizationResult with candidate, report, and patch.
    """
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load ParentSKU with unified loader (cache → API → CSV fallback)
    parent_sku, load_status = load_parent_sku_unified_with_status(
        master_sku=master_sku,
        force_refresh=force_refresh,
        catalog_path=str(catalog_path),
    )
    if parent_sku is None:
        if load_status.csv_attempted and load_status.csv_error is None:
            raise ValueError(f"Product not found: {master_sku}")
        raise ValueError(f"API unavailable for {master_sku}")

    # Step 2: Generate candidates and select best
    provider = get_provider()
    if num_candidates is None:
        num_candidates = parse_num_candidates(os.environ.get("FEEDOPS_NUM_CANDIDATES"))
    if candidate_weights is None:
        candidate_weights = parse_candidate_weights(
            os.environ.get("FEEDOPS_CANDIDATE_WEIGHTS")
        )
    candidates, generation_errors = await generate_candidates(
        parent_sku, provider, num_candidates
    )
    if not candidates:
        detail = (
            "; ".join(generation_errors)
            if generation_errors
            else "No candidates generated"
        )
        raise ValueError(detail)

    evidence = build_evidence_table(parent_sku)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    selected_candidate, ranking = select_best_candidate(
        candidates,
        candidate_weights,
        keyword_plan=keyword_plan,
        category=parent_sku.category,
    )
    best_rank = ranking[0]
    selected_candidate = selected_candidate.model_copy(
        update={
            "heuristic_score": best_rank.heuristic.weighted_composite,
            "heuristic_score_breakdown": {
                "google": best_rank.heuristic.google.composite,
                "bing": best_rank.heuristic.bing.composite,
                "shopify": best_rank.heuristic.shopify.composite,
            },
            "selection_score_adjusted": best_rank.heuristic.adjusted_weighted_composite,
            "selection_weights": candidate_weights,
            "soft_gate_penalty": best_rank.heuristic.soft_gate_penalty,
            "soft_gate_warnings": (
                list(best_rank.heuristic.soft_gate_warnings)
                if best_rank.heuristic.soft_gate_warnings
                else None
            ),
            "soft_gate_miss_counts": best_rank.heuristic.soft_gate_miss_counts,
            "candidate_index": selected_candidate.candidate_index,
            "num_candidates": selected_candidate.num_candidates,
        }
    )

    # Step 3: Verify claims
    verified_candidate, errors = verify_claims(selected_candidate, parent_sku)

    # Step 4: Generate lifestyle images (if enabled)
    lifestyle_images_enabled = (
        os.environ.get("LIFESTYLE_IMAGES_ENABLED", "false").lower() == "true"
    )
    gemini_api_key = os.environ.get("GEMINI_API_KEY")

    if lifestyle_images_enabled and gemini_api_key:
        print(f"\n{'='*70}")
        print("Step 4: Generating lifestyle images...")
        print(f"{'='*70}")

        from feedops.pipeline.lifestyle_images import (
            LifestyleImageGenerator,
            get_customer_focused_scene,
            get_product_inventory,
            get_technical_specs,
        )

        # Get product image URLs
        product_image_urls = []
        if parent_sku.variants:
            variant = parent_sku.variants[0]

            def _append_url(url: str | None) -> None:
                if url and url not in product_image_urls:
                    product_image_urls.append(url)

            _append_url(variant.main_image_url)
            _append_url(variant.alt_image_1)
            _append_url(variant.alt_image_2)
            _append_url(variant.alt_image_3)
            _append_url(variant.alt_image_4)

        if product_image_urls:
            # Initialize generator
            lifestyle_output_dir = Path(
                os.environ.get("LIFESTYLE_IMAGES_OUTPUT_DIR", "data/lifestyle_images")
            )
            generator = LifestyleImageGenerator(
                api_key=gemini_api_key, output_dir=lifestyle_output_dir
            )

            # Build prompts with customer-focused context
            inventory = get_product_inventory(
                parent_sku.category, parent_sku.current_title
            )
            # Try to determine style from metadata or default to modern
            style = parent_sku.style or "modern"
            # Use customer-focused scene generation
            scene = get_customer_focused_scene(
                category=parent_sku.category,
                style=style,
                product_title=parent_sku.current_title,
            )
            technical = get_technical_specs(style)

            # Generate variations
            num_variations = int(os.environ.get("LIFESTYLE_IMAGES_NUM_VARIATIONS", "3"))
            lifestyle_results = generator.generate_for_product(
                product_image_urls=product_image_urls,
                master_sku=parent_sku.master_sku,
                inventory=inventory,
                scene=scene,
                technical=technical,
                category=parent_sku.category,
                num_variations=num_variations,
            )

            # Attach to candidate
            verified_candidate = verified_candidate.model_copy(
                update={"lifestyle_images": lifestyle_results}
            )

            print(f"✅ Lifestyle images attached to candidate")
        else:
            print("⚠️  No product image URL found - skipping lifestyle image generation")

    # Step 5: Generate outputs
    evidence_table = format_evidence_markdown(evidence)
    prompt = build_prompt(parent_sku)
    image_url = None
    if parent_sku.variants and parent_sku.variants[0].main_image_url:
        image_url = parent_sku.variants[0].main_image_url
    token_usage = getattr(provider, "last_usage", {})
    estimated_cost = estimate_llm_cost(provider.name, token_usage)
    mc_metadata = None
    mc_path = Path(
        os.environ.get("FEEDOPS_MC_METADATA_PATH", str(DEFAULT_MC_METADATA_PATH))
    )
    if mc_path.exists():
        try:
            mc_metadata = load_merchant_center_snapshot(mc_path)
        except Exception:
            mc_metadata = None

    report = generate_report(
        parent_sku,
        verified_candidate,
        errors,
        evidence_table=evidence_table,
        prompt=prompt,
        image_url=image_url,
        provider_name=provider.name,
        token_usage=token_usage,
        estimated_cost=estimated_cost,
        selection_ranking=ranking,
        generation_errors=generation_errors,
        mc_metadata=mc_metadata,
    )
    patch_previews = {
        "google": generate_patch_preview(
            parent_sku, verified_candidate, platform="google"
        ),
        "bing": generate_patch_preview(parent_sku, verified_candidate, platform="bing"),
        "shopify": generate_patch_preview(
            parent_sku, verified_candidate, platform="shopify"
        ),
    }

    # Step 6: Save outputs
    safe_sku = master_sku.replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    report_path = output_dir / f"sku-{safe_sku}-{timestamp}.md"
    report_path.write_text(report)

    # Save MasterSKU-level patches (for backward compatibility)
    google_patch_path = exports_dir / f"google-patch-{safe_sku}.json"
    bing_patch_path = exports_dir / f"bing-patch-{safe_sku}.json"
    shopify_patch_path = exports_dir / f"shopify-patch-{safe_sku}.json"
    google_patch_path.write_text(json.dumps(patch_previews["google"], indent=2))
    bing_patch_path.write_text(json.dumps(patch_previews["bing"], indent=2))
    shopify_patch_path.write_text(json.dumps(patch_previews["shopify"], indent=2))

    # Save per-variant patches (finish-specific descriptions)
    variants_dir = exports_dir / "variants" / safe_sku
    variants_dir.mkdir(parents=True, exist_ok=True)

    google_variant_patches = generate_all_variant_patches(
        parent_sku, verified_candidate, "google"
    )
    bing_variant_patches = generate_all_variant_patches(
        parent_sku, verified_candidate, "bing"
    )
    shopify_variant_patches = generate_all_variant_patches(
        parent_sku, verified_candidate, "shopify"
    )

    for patch in google_variant_patches:
        option_sku = patch.get("_meta", {}).get("option_sku", "unknown")
        safe_option = option_sku.replace("/", "-")
        path = variants_dir / f"google-{safe_option}.json"
        path.write_text(json.dumps(patch, indent=2))

    for patch in bing_variant_patches:
        option_sku = patch.get("_meta", {}).get("option_sku", "unknown")
        safe_option = option_sku.replace("/", "-")
        path = variants_dir / f"bing-{safe_option}.json"
        path.write_text(json.dumps(patch, indent=2))

    for patch in shopify_variant_patches:
        option_sku = patch.get("_meta", {}).get("option_sku", "unknown")
        safe_option = option_sku.replace("/", "-")
        path = variants_dir / f"shopify-{safe_option}.json"
        path.write_text(json.dumps(patch, indent=2))

    # Step 7: Sync lifestyle images for Streamlit dashboard outputs (if applicable)
    if (
        exports_dir.name == "lifestyle-eval-candidate"
        and exports_dir.parent.name == "dashboard_data"
    ):
        try:
            from feedops.quality.data_loader import sync_lifestyle_images

            repo_root = Path(__file__).resolve().parents[3]
            sync_lifestyle_images(
                exports_dir=exports_dir,
                images_subdir="images",
                repo_root=repo_root,
            )
        except Exception:
            pass

    # Step 8: Log to database
    db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    from feedops.db import init_db, log_keyword_intent_snapshot, log_optimization

    def _split_keywords(value: str | None) -> list[str] | None:
        if not value:
            return None
        parts = [p.strip() for p in value.split(",")]
        cleaned = [p for p in parts if p]
        return cleaned or None

    init_db(db_path)
    run_id = log_optimization(
        db_path=db_path,
        master_sku=master_sku,
        llm_provider=provider.name,
        quality_score=verified_candidate.final_score.composite,
        factual_accuracy=verified_candidate.final_score.factual_accuracy,
        approval_status=verified_candidate.final_score.approval_status,
        data_source=parent_sku.data_source,
        status="success",
    )
    # Store the keyword intent that was used to guide copy (if available).
    evidence_map = {e.field: e.value for e in evidence}
    log_keyword_intent_snapshot(
        db_path=db_path,
        master_sku=master_sku,
        item_group_id=parent_sku.item_group_id,
        item_ids=(
            [v.item_id for v in parent_sku.variants] if parent_sku.variants else None
        ),
        external_keywords=_split_keywords(evidence_map.get("external_keywords")),
        keyword_intent_master=_split_keywords(
            evidence_map.get("keyword_intent_master")
        ),
        optimization_run_id=run_id,
    )

    return OptimizationResult(
        master_sku=master_sku,
        data_source=parent_sku.data_source,
        candidate=verified_candidate,
        verification_errors=errors,
        report=report,
        patch_previews=patch_previews,
        timestamp=timestamp,
    )
