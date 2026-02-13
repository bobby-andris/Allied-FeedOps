#!/usr/bin/env python3
"""Phase 3 Keyword Gap Analysis - SAMP-03 & SAMP-04

Generates Keyword Planner ideas for sample SKUs and calculates opportunity gaps
against current Google Ads search term coverage.

Tasks:
- SAMP-03: Generate Keyword Planner ideas using product titles as seeds
- SAMP-04: Calculate opportunity gap (KP ideas NOT in current search terms)

Input:
- .planning/phases/03-sample-testing-analysis/sample-skus.json
- .planning/phases/03-sample-testing-analysis/search-terms-by-sku.json

Output:
- .planning/phases/03-sample-testing-analysis/keyword-ideas-by-sku.json
- .planning/phases/03-sample-testing-analysis/opportunity-gaps.json
"""
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> str | None:
    """Get environment variable, returning None if empty."""
    val = os.getenv(name)
    if not val:
        return None
    val = val.strip()
    return val or None


def _load_google_ads_client():
    """Load Google Ads API client from environment variables."""
    from google.ads.googleads.client import GoogleAdsClient

    developer_token = _truthy_env("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = _truthy_env("GOOGLE_ADS_CLIENT_ID")
    client_secret = _truthy_env("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = _truthy_env("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = _truthy_env("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if not all([developer_token, client_id, client_secret, refresh_token]):
        raise ValueError("Missing required Google Ads credentials in environment")

    config = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    if login_customer_id:
        config["login_customer_id"] = login_customer_id

    return GoogleAdsClient.load_from_dict(config)


def extract_generic_category_term(title: str, category: str) -> str:
    """Extract generic product category term from title for better KP results.

    Product titles are too specific (brand + model). Use category + generic terms.
    Examples:
    - "Pipeline Collection 16 Inch Grab Bar" -> "grab bar"
    - "Waverly Place 16 Inch Double Glass Shelf with Gallery Rail" -> "glass shelf"
    """
    # Map known categories to searchable terms
    category_map = {
        "grab bar": "grab bar",
        "glass shelves": "glass shelf",
        "multi hooks": "bathroom hooks",
        "retractable hooks and garment rods": "garment rod",
        "assorted wall accessories": "towel rail",
    }

    category_lower = category.lower()
    for key, value in category_map.items():
        if key in category_lower:
            return value

    # Fallback: extract last 2-3 meaningful words from title
    words = title.lower().split()
    # Filter out collection names, sizes, numbers
    meaningful = [w for w in words if not any(x in w for x in ['collection', 'inch', 'place', 'traditional', 'waverly', 'pipeline', 'carolina'])]
    if len(meaningful) >= 2:
        return ' '.join(meaningful[-2:])

    return category.lower()


def generate_keyword_ideas(
    client,
    customer_id: str,
    seed_keyword: str,
    language_id: str = "1000",
    geo_target_id: str = "2840",
    limit: int = 100,
) -> list[dict]:
    """Generate keyword ideas from a seed keyword using Keyword Planner.

    Args:
        client: Google Ads client
        customer_id: Google Ads customer ID
        seed_keyword: Keyword to seed the generator (e.g., product title)
        language_id: Language constant ID (1000 = English)
        geo_target_id: Geo target constant ID (2840 = USA)
        limit: Max ideas to return

    Returns:
        List of keyword ideas with metrics
    """
    service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = f"languageConstants/{language_id}"
    request.geo_target_constants.append(f"geoTargetConstants/{geo_target_id}")
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    )

    # Use keyword seed (can include multiple seed keywords for better results)
    request.keyword_seed.keywords.append(seed_keyword)

    try:
        response = service.generate_keyword_ideas(request=request)

        ideas = []
        for idea in response.results[:limit]:
            metrics = idea.keyword_idea_metrics

            # Handle competition - can be enum or int
            competition = "UNSPECIFIED"
            if hasattr(metrics, 'competition') and metrics.competition:
                if hasattr(metrics.competition, 'name'):
                    competition = metrics.competition.name
                else:
                    # Map int to enum values: 0=UNSPECIFIED, 1=LOW, 2=MEDIUM, 3=HIGH
                    comp_map = {0: "UNSPECIFIED", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}
                    competition = comp_map.get(int(metrics.competition), "UNSPECIFIED")

            ideas.append({
                "text": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                "competition": competition,
                "competition_index": metrics.competition_index or 0,
                "low_cpc_micros": metrics.low_top_of_page_bid_micros or 0,
                "high_cpc_micros": metrics.high_top_of_page_bid_micros or 0,
            })

        return ideas

    except Exception as e:
        logger.error(f"Error generating keyword ideas for '{seed_keyword}': {e}")
        return []


def calculate_opportunity_gap(
    kp_ideas: list[dict],
    current_search_terms: list[dict],
    min_monthly_searches: int = 100,
    top_n: int = 20,
) -> dict:
    """Calculate opportunity gap between KP ideas and current search terms.

    Args:
        kp_ideas: Keyword Planner ideas
        current_search_terms: Current Google Ads search terms
        min_monthly_searches: Minimum monthly searches to consider
        top_n: Number of top gap keywords to include

    Returns:
        Gap analysis dict
    """
    # Normalize search terms to lowercase for comparison
    current_terms_set = set(
        term["search_term"].strip().lower()
        for term in current_search_terms
    )

    # Filter to high-volume KP ideas
    high_volume_ideas = [
        idea for idea in kp_ideas
        if idea["avg_monthly_searches"] >= min_monthly_searches
    ]

    # Find gaps
    gap_keywords = []
    for idea in high_volume_ideas:
        keyword_normalized = idea["text"].strip().lower()
        if keyword_normalized not in current_terms_set:
            gap_keywords.append(idea)

    # Sort by search volume descending
    gap_keywords.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)

    # Calculate metrics
    gap_count = len(gap_keywords)
    gap_volume = sum(k["avg_monthly_searches"] for k in gap_keywords)
    coverage_rate = 1 - (gap_count / len(high_volume_ideas)) if high_volume_ideas else 0

    return {
        "current_search_terms": len(current_search_terms),
        "kp_high_volume_ideas": len(high_volume_ideas),
        "gap_count": gap_count,
        "gap_volume": gap_volume,
        "coverage_rate": round(coverage_rate, 3),
        "top_gaps": gap_keywords[:top_n],
    }


def main():
    # Setup paths
    project_root = Path(__file__).parent.parent
    phase_dir = project_root / ".planning" / "phases" / "03-sample-testing-analysis"

    sample_skus_file = phase_dir / "sample-skus.json"
    search_terms_file = phase_dir / "search-terms-by-sku.json"
    output_ideas_file = phase_dir / "keyword-ideas-by-sku.json"
    output_gaps_file = phase_dir / "opportunity-gaps.json"

    # Load sample SKUs
    logger.info(f"Loading sample SKUs from {sample_skus_file}")
    with open(sample_skus_file, "r") as f:
        sample_skus = json.load(f)

    # Deduplicate SKUs by master_sku
    sku_map = {}
    for sku in sample_skus:
        master_sku = sku["master_sku"]
        if master_sku not in sku_map:
            sku_map[master_sku] = sku

    unique_skus = list(sku_map.values())
    logger.info(f"Found {len(unique_skus)} unique SKUs")

    # Load search terms
    logger.info(f"Loading search terms from {search_terms_file}")
    with open(search_terms_file, "r") as f:
        search_terms_data = json.load(f)

    # Initialize Google Ads client
    logger.info("Initializing Google Ads client")
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")
    client = _load_google_ads_client()

    # SAMP-03: Generate Keyword Planner ideas for each SKU
    logger.info("\n" + "="*80)
    logger.info("SAMP-03: Generating Keyword Planner Ideas")
    logger.info("="*80)

    keyword_ideas_by_sku = {
        "metadata": {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "language": "English",
            "geo": "USA",
        },
        "skus": {}
    }

    for idx, sku in enumerate(unique_skus, 1):
        master_sku = sku["master_sku"]
        title = sku["title"]
        category = sku["category"]

        # Extract generic category term for better Keyword Planner results
        # Full product titles (with brand + model) return only the exact match
        seed_keyword = extract_generic_category_term(title, category)

        logger.info(f"\n[{idx}/{len(unique_skus)}] Processing {master_sku} ({category})")
        logger.info(f"  Product title: '{title}'")
        logger.info(f"  Seed keyword: '{seed_keyword}'")

        ideas = generate_keyword_ideas(
            client=client,
            customer_id=customer_id,
            seed_keyword=seed_keyword,
            limit=100,
        )

        if ideas:
            logger.info(f"  Generated {len(ideas)} keyword ideas")
            logger.info(f"  Top ideas: {', '.join(idea['text'] for idea in ideas[:5])}")

            keyword_ideas_by_sku["skus"][master_sku] = {
                "product_title": title,
                "seed_keyword": seed_keyword,
                "category": category,
                "idea_count": len(ideas),
                "ideas": ideas,
            }
        else:
            logger.warning(f"  No ideas generated (API error or rate limit)")
            keyword_ideas_by_sku["skus"][master_sku] = {
                "product_title": title,
                "seed_keyword": seed_keyword,
                "category": category,
                "idea_count": 0,
                "ideas": [],
            }

        # Rate limiting: 1-2 second delay between requests
        if idx < len(unique_skus):
            time.sleep(1.5)

    # Save keyword ideas
    logger.info(f"\nSaving keyword ideas to {output_ideas_file}")
    with open(output_ideas_file, "w") as f:
        json.dump(keyword_ideas_by_sku, f, indent=2)

    # SAMP-04: Calculate opportunity gaps
    logger.info("\n" + "="*80)
    logger.info("SAMP-04: Calculating Opportunity Gaps")
    logger.info("="*80)

    opportunity_gaps = {
        "metadata": {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "min_monthly_searches": 100,
        },
        "summary": {
            "total_skus": 0,
            "avg_coverage_rate": 0.0,
            "total_gap_volume": 0,
            "total_gap_keywords": 0,
        },
        "skus": {}
    }

    total_coverage = 0.0
    total_gap_volume = 0
    total_gap_keywords = 0

    for master_sku, sku_data in keyword_ideas_by_sku["skus"].items():
        logger.info(f"\nAnalyzing gap for {master_sku}")

        kp_ideas = sku_data["ideas"]
        current_terms = search_terms_data["skus"].get(master_sku, {}).get("terms", [])

        gap_analysis = calculate_opportunity_gap(
            kp_ideas=kp_ideas,
            current_search_terms=current_terms,
            min_monthly_searches=100,
            top_n=20,
        )

        logger.info(f"  Current search terms: {gap_analysis['current_search_terms']}")
        logger.info(f"  KP high-volume ideas: {gap_analysis['kp_high_volume_ideas']}")
        logger.info(f"  Gap count: {gap_analysis['gap_count']}")
        logger.info(f"  Gap volume: {gap_analysis['gap_volume']:,}")
        logger.info(f"  Coverage rate: {gap_analysis['coverage_rate']:.1%}")

        opportunity_gaps["skus"][master_sku] = {
            "category": sku_data["category"],
            **gap_analysis,
        }

        total_coverage += gap_analysis["coverage_rate"]
        total_gap_volume += gap_analysis["gap_volume"]
        total_gap_keywords += gap_analysis["gap_count"]

    # Calculate summary
    sku_count = len(keyword_ideas_by_sku["skus"])
    opportunity_gaps["summary"] = {
        "total_skus": sku_count,
        "avg_coverage_rate": round(total_coverage / sku_count, 3) if sku_count > 0 else 0,
        "total_gap_volume": total_gap_volume,
        "total_gap_keywords": total_gap_keywords,
    }

    # Save opportunity gaps
    logger.info(f"\nSaving opportunity gaps to {output_gaps_file}")
    with open(output_gaps_file, "w") as f:
        json.dump(opportunity_gaps, f, indent=2)

    # Print summary table
    logger.info("\n" + "="*80)
    logger.info("SUMMARY TABLE")
    logger.info("="*80)
    logger.info(f"\n{'SKU':<20} {'Category':<35} {'Current':<10} {'KP Ideas':<10} {'Gap':<8} {'Gap Vol':<12} {'Coverage':<10}")
    logger.info("-" * 115)

    for master_sku, gap_data in opportunity_gaps["skus"].items():
        logger.info(
            f"{master_sku:<20} "
            f"{gap_data['category'][:33]:<35} "
            f"{gap_data['current_search_terms']:<10} "
            f"{gap_data['kp_high_volume_ideas']:<10} "
            f"{gap_data['gap_count']:<8} "
            f"{gap_data['gap_volume']:<12,} "
            f"{gap_data['coverage_rate']:.1%}"
        )

    logger.info("-" * 115)
    logger.info(
        f"{'OVERALL':<20} "
        f"{'':<35} "
        f"{'':<10} "
        f"{'':<10} "
        f"{opportunity_gaps['summary']['total_gap_keywords']:<8} "
        f"{opportunity_gaps['summary']['total_gap_volume']:<12,} "
        f"{opportunity_gaps['summary']['avg_coverage_rate']:.1%}"
    )

    logger.info("\n" + "="*80)
    logger.info("COMPLETE")
    logger.info("="*80)
    logger.info(f"Keyword ideas: {output_ideas_file}")
    logger.info(f"Opportunity gaps: {output_gaps_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)
