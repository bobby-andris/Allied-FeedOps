"""Main optimization pipeline orchestrator."""
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from feedops.models import Candidate
from feedops.loaders import load_catalog, get_parent_sku
from feedops.providers import get_provider
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.validators import validate_candidate_content
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.reporter import (
    generate_report,
    generate_patch_preview,
    generate_all_variant_patches,
)


@dataclass
class OptimizationResult:
    """Result of a single SKU optimization."""
    master_sku: str
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

    return (
        (prompt_tokens / 1_000_000) * rates["input"]
        + (completion_tokens / 1_000_000) * rates["output"]
    )


async def optimize_parent_sku(
    master_sku: str,
    catalog_path: Path | str,
    dry_run: bool = True,
    output_dir: Path | str = "reports",
    exports_dir: Path | str = "exports",
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

    Returns:
        OptimizationResult with candidate, report, and patch.
    """
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load catalog and extract ParentSKU
    df = load_catalog(catalog_path)
    parent_sku = get_parent_sku(df, master_sku)
    if parent_sku is None:
        raise ValueError(f"MasterSKU not found: {master_sku}")

    # Step 2: Generate candidate
    provider = get_provider()
    candidate = await generate_candidate(parent_sku, provider)

    # Step 3: Validate customer-facing content
    content_errors = validate_candidate_content(candidate)
    if content_errors:
        raise ValueError(
            "Candidate content validation failed: " + "; ".join(content_errors)
        )

    # Step 4: Verify claims
    verified_candidate, errors = verify_claims(candidate, parent_sku)

    # Step 5: Generate outputs
    evidence = build_evidence_table(parent_sku)
    evidence_table = format_evidence_markdown(evidence)
    prompt = build_prompt(parent_sku)
    image_url = None
    if parent_sku.variants and parent_sku.variants[0].main_image_url:
        image_url = parent_sku.variants[0].main_image_url
    token_usage = getattr(provider, "last_usage", {})
    estimated_cost = estimate_llm_cost(provider.name, token_usage)
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
    )
    patch_previews = {
        "google": generate_patch_preview(parent_sku, verified_candidate, platform="google"),
        "bing": generate_patch_preview(parent_sku, verified_candidate, platform="bing"),
        "shopify": generate_patch_preview(parent_sku, verified_candidate, platform="shopify"),
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
    
    google_variant_patches = generate_all_variant_patches(parent_sku, verified_candidate, "google")
    bing_variant_patches = generate_all_variant_patches(parent_sku, verified_candidate, "bing")
    shopify_variant_patches = generate_all_variant_patches(parent_sku, verified_candidate, "shopify")
    
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

    # Step 7: Log to database
    db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    from feedops.db import init_db, log_optimization, log_keyword_intent_snapshot

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
        status="success",
    )
    # Store the keyword intent that was used to guide copy (if available).
    evidence_map = {e.field: e.value for e in evidence}
    log_keyword_intent_snapshot(
        db_path=db_path,
        master_sku=master_sku,
        item_group_id=parent_sku.item_group_id,
        item_ids=[v.item_id for v in parent_sku.variants] if parent_sku.variants else None,
        external_keywords=_split_keywords(evidence_map.get("external_keywords")),
        keyword_intent_master=_split_keywords(evidence_map.get("keyword_intent_master")),
        optimization_run_id=run_id,
    )

    return OptimizationResult(
        master_sku=master_sku,
        candidate=verified_candidate,
        verification_errors=errors,
        report=report,
        patch_previews=patch_previews,
        timestamp=timestamp,
    )
