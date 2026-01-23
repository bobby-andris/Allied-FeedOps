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
from feedops.pipeline.reporter import generate_report, generate_patch_preview


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

    Returns:
        OptimizationResult with candidate, report, and patch.
    """
    catalog_path = Path(catalog_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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

    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    google_patch_path = exports_dir / f"google-patch-{safe_sku}.json"
    bing_patch_path = exports_dir / f"bing-patch-{safe_sku}.json"
    shopify_patch_path = exports_dir / f"shopify-patch-{safe_sku}.json"
    google_patch_path.write_text(json.dumps(patch_previews["google"], indent=2))
    bing_patch_path.write_text(json.dumps(patch_previews["bing"], indent=2))
    shopify_patch_path.write_text(json.dumps(patch_previews["shopify"], indent=2))

    # Step 7: Log to database
    db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    from feedops.db import init_db, log_optimization

    init_db(db_path)
    log_optimization(
        db_path=db_path,
        master_sku=master_sku,
        llm_provider=provider.name,
        quality_score=verified_candidate.final_score.composite,
        factual_accuracy=verified_candidate.final_score.factual_accuracy,
        approval_status=verified_candidate.final_score.approval_status,
        status="success",
    )

    return OptimizationResult(
        master_sku=master_sku,
        candidate=verified_candidate,
        verification_errors=errors,
        report=report,
        patch_previews=patch_previews,
        timestamp=timestamp,
    )
