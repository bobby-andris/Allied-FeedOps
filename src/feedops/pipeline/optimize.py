"""Main optimization pipeline orchestrator."""
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from feedops.models import Candidate
from feedops.loaders import load_catalog, get_parent_sku
from feedops.providers import get_provider
from feedops.pipeline.generator import generate_candidate
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.reporter import generate_report, generate_patch_preview


@dataclass
class OptimizationResult:
    """Result of a single SKU optimization."""
    master_sku: str
    candidate: Candidate
    verification_errors: list[str]
    report: str
    patch_preview: dict
    timestamp: str


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
    3. Verify claims against source data
    4. Generate report and patch preview
    5. Save outputs to files
    6. Log to database

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

    # Step 3: Verify claims
    verified_candidate, errors = verify_claims(candidate, parent_sku)

    # Step 4: Generate outputs
    report = generate_report(parent_sku, verified_candidate, errors)
    patch = generate_patch_preview(parent_sku, verified_candidate)

    # Step 5: Save outputs
    safe_sku = master_sku.replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    report_path = output_dir / f"sku-{safe_sku}-{timestamp}.md"
    report_path.write_text(report)

    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    patch_path = exports_dir / f"merchant-center-patch-{safe_sku}.json"
    patch_path.write_text(json.dumps(patch, indent=2))

    # Step 6: Log to database
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
        patch_preview=patch,
        timestamp=timestamp,
    )
