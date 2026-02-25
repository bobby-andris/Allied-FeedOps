#!/usr/bin/env python3
"""
Seed script for Phase 31 E2E validation of KEEP'd table pages.

Populates term_intent_state, search_buildout_recommendations, and experiment_registry
with test data tagged SEED_V31 for easy cleanup.

Usage:
    python scripts/seed_intent_state.py --seed      # Populate seed data
    python scripts/seed_intent_state.py --cleanup    # Remove seed data
    python scripts/seed_intent_state.py --verify     # Check seed data exists
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from feedops.db.supabase_client import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SEED_TAG = "SEED_V31"


def classify_intent(term: str) -> str:
    """Classify a search term into an intent class using simple rules."""
    lower = term.lower()
    if "allied brass" in lower or "allied" in lower:
        return "BRAND_CORE"
    if any(kw in lower for kw in ["towel bar", "soap dish", "toilet paper holder", "grab bar",
                                   "towel ring", "towel rack", "robe hook"]):
        return "PRODUCT_HIGH"
    if any(kw in lower for kw in ["bathroom accessories", "bath hardware", "bathroom",
                                   "bath accessories"]):
        return "CATEGORY_MID"
    return "DISCOVERY_LOW"


def route_for_intent(intent_class: str) -> str:
    """Map intent class to route action."""
    mapping = {
        "BRAND_CORE": "branded",
        "PRODUCT_HIGH": "funnel",
        "CATEGORY_MID": "search_discovery",
        "DISCOVERY_LOW": "observe_only",
    }
    return mapping.get(intent_class, "observe_only")


def seed(supabase) -> None:
    """Populate seed data in KEEP'd tables."""
    logger.info("--- Seeding term_intent_state ---")

    # Fetch real search terms from search_queries (query_text + master_sku per SCHEMA.md)
    result = supabase.table("search_queries") \
        .select("query_text, master_sku, impressions, clicks") \
        .order("impressions", desc=True) \
        .limit(50) \
        .execute()

    # Normalize to use "search_term" key internally, map master_sku to custom_label_0
    raw_terms = result.data if result.data else []
    terms = [
        {"search_term": t["query_text"], "custom_label_0": t.get("master_sku"),
         "impressions": t.get("impressions", 0), "clicks": t.get("clicks", 0)}
        for t in raw_terms if t.get("query_text")
    ]
    logger.info(f"Found {len(terms)} search terms from search_queries")

    if not terms:
        # Fallback: use synthetic terms if no search_queries data
        terms = [
            {"search_term": "allied brass towel bar", "custom_label_0": "TOWEL-BARS", "impressions": 100, "clicks": 10},
            {"search_term": "bathroom accessories brass", "custom_label_0": "ACCESSORIES", "impressions": 80, "clicks": 5},
            {"search_term": "soap dish wall mount", "custom_label_0": "SOAP-DISHES", "impressions": 60, "clicks": 3},
            {"search_term": "grab bar polished chrome", "custom_label_0": "GRAB-BARS", "impressions": 50, "clicks": 4},
            {"search_term": "toilet paper holder oil rubbed bronze", "custom_label_0": "TP-HOLDERS", "impressions": 40, "clicks": 2},
        ]
        logger.info("Using synthetic fallback terms")

    # Deduplicate by normalized search term
    seen = set()
    rows = []
    for t in terms:
        term = t["search_term"]
        normalized = term.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        intent_class = classify_intent(term)
        rows.append({
            "search_term": term,
            "normalized_search_term": normalized,
            "custom_label_0": t.get("custom_label_0"),
            "intent_class": intent_class,
            "intent_subclasses": [],
            "route_action": route_for_intent(intent_class),
            "confidence": 0.85,
            "requires_review": False,
            "policy_version": SEED_TAG,
            "source_window_start": "2026-02-01",
            "source_window_end": "2026-02-25",
            "metadata": {},
        })

    if rows:
        # Clean up any prior seed data first to avoid duplicates
        supabase.table("term_intent_state") \
            .delete().eq("policy_version", SEED_TAG).execute()
        # Use insert (functional unique index prevents PostgREST upsert)
        result = supabase.table("term_intent_state").insert(rows).execute()
        logger.info(f"Inserted {len(rows)} rows into term_intent_state")

    # --- search_buildout_recommendations ---
    logger.info("--- Seeding search_buildout_recommendations ---")
    reco_terms = rows[:8] if len(rows) >= 8 else rows
    reco_rows = []
    tiers = ["broad", "phrase", "exact"]
    for i, r in enumerate(reco_terms):
        reco_rows.append({
            "search_term": f"SEED_{r['search_term']}",
            "custom_label_0": r.get("custom_label_0"),
            "recommended_search_tier": tiers[i % 3],
            "status": "candidate",
            "confidence": 0.75 + (i * 0.02),
            "metadata": {"source": SEED_TAG},
        })

    if reco_rows:
        # Clean up any prior seed data first
        supabase.table("search_buildout_recommendations") \
            .delete().like("search_term", "SEED_%").execute()
        result = supabase.table("search_buildout_recommendations").insert(reco_rows).execute()
        logger.info(f"Inserted {len(reco_rows)} rows into search_buildout_recommendations")

    # --- experiment_registry ---
    logger.info("--- Seeding experiment_registry ---")
    supabase.table("experiment_registry").upsert({
        "experiment_key": "SEED_V31_test_experiment",
        "name": "Phase 31 Validation Experiment",
        "initiative": "v1.3b validation",
        "hypothesis": "Seed data validates page rendering",
        "decision_rule": "Manual review",
        "status": "draft",
        "start_date": "2026-02-25",
        "created_by": "seed_script",
        "metadata": {"source": SEED_TAG},
    }, on_conflict="experiment_key").execute()
    logger.info("Upserted 1 row into experiment_registry")

    logger.info("=== Seeding complete ===")


def verify(supabase) -> bool:
    """Verify seed data exists in all tables."""
    ok = True

    r1 = supabase.table("term_intent_state") \
        .select("id", count="exact") \
        .eq("policy_version", SEED_TAG) \
        .execute()
    count1 = r1.count if r1.count is not None else len(r1.data)
    logger.info(f"term_intent_state SEED_V31 rows: {count1}")
    if count1 == 0:
        ok = False

    r2 = supabase.table("search_buildout_recommendations") \
        .select("id", count="exact") \
        .like("search_term", "SEED_%") \
        .execute()
    count2 = r2.count if r2.count is not None else len(r2.data)
    logger.info(f"search_buildout_recommendations SEED rows: {count2}")
    if count2 == 0:
        ok = False

    r3 = supabase.table("experiment_registry") \
        .select("id", count="exact") \
        .eq("experiment_key", "SEED_V31_test_experiment") \
        .execute()
    count3 = r3.count if r3.count is not None else len(r3.data)
    logger.info(f"experiment_registry SEED rows: {count3}")
    if count3 == 0:
        ok = False

    if ok:
        logger.info("=== VERIFY: All seed data present ===")
    else:
        logger.warning("=== VERIFY: Some seed data missing ===")
    return ok


def cleanup(supabase) -> None:
    """Remove all SEED_V31 data from production tables."""
    logger.info("--- Cleaning up term_intent_state ---")
    supabase.table("term_intent_state") \
        .delete() \
        .eq("policy_version", SEED_TAG) \
        .execute()

    logger.info("--- Cleaning up search_buildout_recommendations ---")
    supabase.table("search_buildout_recommendations") \
        .delete() \
        .like("search_term", "SEED_%") \
        .execute()

    logger.info("--- Cleaning up experiment_registry ---")
    supabase.table("experiment_registry") \
        .delete() \
        .eq("experiment_key", "SEED_V31_test_experiment") \
        .execute()

    logger.info("=== Cleanup complete ===")

    # Verify cleanup
    logger.info("--- Verifying cleanup ---")
    remaining = verify(supabase)
    if not remaining:
        logger.info("=== CLEANUP VERIFIED: Zero SEED_V31 rows remain ===")
    else:
        logger.error("=== CLEANUP FAILED: Some SEED_V31 rows still exist ===")


def main():
    parser = argparse.ArgumentParser(
        description="Seed/cleanup KEEP'd table data for Phase 31 E2E validation"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", action="store_true", help="Populate seed data")
    group.add_argument("--cleanup", action="store_true", help="Remove seed data")
    group.add_argument("--verify", action="store_true", help="Check seed data exists")
    args = parser.parse_args()

    supabase = get_client()

    if args.seed:
        seed(supabase)
        verify(supabase)
    elif args.cleanup:
        cleanup(supabase)
    elif args.verify:
        verify(supabase)


if __name__ == "__main__":
    main()
