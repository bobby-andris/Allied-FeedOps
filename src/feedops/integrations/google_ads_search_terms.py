"""Google Ads Search Terms Integration for Search Query Insights.

This module provides:
- SearchTermsClient: Fetches search terms from Google Ads with variant-level tracking
- KeywordPlannerClient: Enriches keywords with search volume data from Keyword Planner

These clients are designed for the Search Query Insights dashboard feature,
supporting variant-level granularity via GMC offer IDs.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> str | None:
    """Get environment variable, returning None if empty."""
    val = os.getenv(name)
    if not val:
        return None
    val = val.strip()
    return val or None


def _load_client():
    """Load Google Ads API client.

    Config resolution order:
    1. Environment variables (GOOGLE_ADS_* vars) - best for Cloud Run with Secrets
    2. GOOGLE_ADS_CONFIG_PATH (explicit file path)
    3. Default google-ads.yaml resolution (library default)
    """
    from google.ads.googleads.client import GoogleAdsClient

    # Try environment variables first (best for Cloud Run / serverless)
    developer_token = _truthy_env("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = _truthy_env("GOOGLE_ADS_CLIENT_ID")
    client_secret = _truthy_env("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = _truthy_env("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = _truthy_env("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if all([developer_token, client_id, client_secret, refresh_token]):
        logger.info("Loading Google Ads client from environment variables")
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

    # Fall back to config file
    config_path = _truthy_env("GOOGLE_ADS_CONFIG_PATH")
    if config_path:
        logger.info(f"Loading Google Ads client from config file: {config_path}")
        return GoogleAdsClient.load_from_storage(path=config_path)

    # Default location
    logger.info("Loading Google Ads client from default location")
    return GoogleAdsClient.load_from_storage()


def _get_supabase_client():
    """Get Supabase client for database operations."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    return create_client(url, key)


class KeywordPlannerClient:
    """Fetches keyword metrics from Google Ads Keyword Planner.

    Provides search volume, competition, and CPC data for keywords.
    Results are cached in the keyword_metrics table (refresh monthly).
    """

    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or _truthy_env("GOOGLE_ADS_CUSTOMER_ID") or "6253381786"
        self._client = None
        self._supabase = None

    @property
    def client(self):
        if self._client is None:
            self._client = _load_client()
        return self._client

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = _get_supabase_client()
        return self._supabase

    def get_historical_metrics(
        self,
        keywords: list[str],
        language_id: str = "1000",  # English
        geo_target_id: str = "2840",  # USA
        use_cache: bool = True,
        cache_max_age_days: int = 30,
    ) -> dict[str, dict]:
        """Fetch historical metrics for keywords from Keyword Planner.

        Args:
            keywords: List of keywords to get metrics for
            language_id: Language constant ID (1000 = English)
            geo_target_id: Geo target constant ID (2840 = USA)
            use_cache: Whether to check cache before API call
            cache_max_age_days: Max age of cached data before refresh

        Returns:
            Dict mapping keyword -> {
                avg_monthly_searches: int,
                competition: str (LOW/MEDIUM/HIGH/UNSPECIFIED),
                competition_index: int (0-100),
                low_cpc_micros: int,
                high_cpc_micros: int,
                monthly_searches: list[{year, month, searches}]
            }
        """
        if not keywords:
            return {}

        keywords = list(set(keywords))  # Deduplicate
        results = {}

        # Check cache first
        if use_cache:
            cached = self._get_cached_metrics(keywords, cache_max_age_days)
            results.update(cached)
            keywords = [k for k in keywords if k not in cached]

        if not keywords:
            return results

        # Fetch from API in batches (rate limit: ~100 per request)
        batch_size = 100
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i + batch_size]
            try:
                batch_results = self._fetch_from_api(batch, language_id, geo_target_id)
                results.update(batch_results)

                # Cache the results
                self._cache_metrics(batch_results)
            except Exception as e:
                logger.warning(f"Keyword Planner API error for batch {i}: {e}")

        return results

    def _fetch_from_api(
        self,
        keywords: list[str],
        language_id: str,
        geo_target_id: str,
    ) -> dict[str, dict]:
        """Fetch metrics from Keyword Planner API."""
        service = self.client.get_service("KeywordPlanIdeaService")

        request = self.client.get_type("GenerateKeywordHistoricalMetricsRequest")
        request.customer_id = self.customer_id
        request.keywords.extend(keywords)
        request.language = f"languageConstants/{language_id}"
        request.geo_target_constants.append(f"geoTargetConstants/{geo_target_id}")
        request.keyword_plan_network = (
            self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        )

        response = service.generate_keyword_historical_metrics(request=request)

        results = {}
        for result in response.results:
            metrics = result.keyword_metrics
            monthly_searches = []

            for m in metrics.monthly_search_volumes:
                monthly_searches.append({
                    "year": m.year,
                    "month": m.month,
                    "searches": m.monthly_searches or 0,
                })

            results[result.text] = {
                "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                "competition": metrics.competition.name if metrics.competition else "UNSPECIFIED",
                "competition_index": metrics.competition_index or 0,
                "low_cpc_micros": metrics.low_top_of_page_bid_micros or 0,
                "high_cpc_micros": metrics.high_top_of_page_bid_micros or 0,
                "monthly_searches": monthly_searches,
            }

        return results

    def _get_cached_metrics(self, keywords: list[str], max_age_days: int) -> dict[str, dict]:
        """Get cached metrics from Supabase."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()

            result = (
                self.supabase.table("keyword_metrics")
                .select("*")
                .in_("keyword", keywords)
                .gte("updated_at", cutoff)
                .execute()
            )

            return {
                row["keyword"]: {
                    "avg_monthly_searches": row["avg_monthly_searches"],
                    "competition": row["competition"],
                    "competition_index": row["competition_index"],
                    "low_cpc_micros": row["low_cpc_micros"],
                    "high_cpc_micros": row["high_cpc_micros"],
                    "monthly_searches": row.get("monthly_searches"),
                }
                for row in result.data
            }
        except Exception as e:
            logger.warning(f"Error fetching cached metrics: {e}")
            return {}

    def _cache_metrics(self, metrics: dict[str, dict]) -> None:
        """Cache metrics to Supabase."""
        if not metrics:
            return

        try:
            rows = [
                {
                    "keyword": keyword,
                    "avg_monthly_searches": data["avg_monthly_searches"],
                    "competition": data["competition"],
                    "competition_index": data["competition_index"],
                    "low_cpc_micros": data["low_cpc_micros"],
                    "high_cpc_micros": data["high_cpc_micros"],
                    "monthly_searches": data.get("monthly_searches"),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                for keyword, data in metrics.items()
            ]

            self.supabase.table("keyword_metrics").upsert(
                rows, on_conflict="keyword"
            ).execute()
        except Exception as e:
            logger.warning(f"Error caching metrics: {e}")

    def generate_keyword_ideas(
        self,
        seed_keywords: list[str] | None = None,
        seed_url: str | None = None,
        language_id: str = "1000",
        geo_target_id: str = "2840",
        limit: int = 100,
    ) -> list[dict]:
        """Generate keyword ideas from seeds (keywords or URL).

        Useful for discovering related search terms we might be missing.

        Args:
            seed_keywords: Keywords to seed the generator
            seed_url: URL to extract keywords from
            language_id: Language constant ID
            geo_target_id: Geo target constant ID
            limit: Max ideas to return

        Returns:
            List of keyword ideas with metrics
        """
        if not seed_keywords and not seed_url:
            raise ValueError("Must provide seed_keywords or seed_url")

        service = self.client.get_service("KeywordPlanIdeaService")

        request = self.client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = self.customer_id
        request.language = f"languageConstants/{language_id}"
        request.geo_target_constants.append(f"geoTargetConstants/{geo_target_id}")
        request.keyword_plan_network = (
            self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        )

        if seed_keywords and seed_url:
            request.keyword_and_url_seed.keywords.extend(seed_keywords[:10])
            request.keyword_and_url_seed.url = seed_url
        elif seed_keywords:
            request.keyword_seed.keywords.extend(seed_keywords[:10])
        else:
            request.url_seed.url = seed_url

        response = service.generate_keyword_ideas(request=request)

        ideas = []
        for idea in response.results[:limit]:
            metrics = idea.keyword_idea_metrics
            ideas.append({
                "keyword": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                "competition": metrics.competition.name if metrics.competition else "UNSPECIFIED",
                "competition_index": metrics.competition_index or 0,
                "low_cpc_micros": metrics.low_top_of_page_bid_micros or 0,
                "high_cpc_micros": metrics.high_top_of_page_bid_micros or 0,
            })

        return ideas


class SearchTermsClient:
    """Fetches search term data from Google Ads Shopping campaigns with variant-level tracking.

    Key features:
    - Tracks search terms at the variant level (GMC offer ID)
    - Maps GMC offer IDs to master SKU + finish via variant_index table
    - Aggregates data at both variant and master SKU levels
    - Identifies finish-specific search patterns
    """

    # GMC offer ID format: shopify_us_{shopify_product_id}_{shopify_variant_id}
    GMC_OFFER_ID_PATTERN = re.compile(r"shopify_us_(\d+)_(\d+)", re.IGNORECASE)

    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or _truthy_env("GOOGLE_ADS_CUSTOMER_ID") or "6253381786"
        self._client = None
        self._supabase = None
        self._variant_cache: dict[str, dict] = {}

    @property
    def client(self):
        if self._client is None:
            self._client = _load_client()
        return self._client

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = _get_supabase_client()
        return self._supabase

    def parse_gmc_offer_id(self, offer_id: str) -> tuple[str | None, str | None]:
        """Parse GMC offer ID to extract Shopify product and variant IDs.

        Format: shopify_us_{product_id}_{variant_id}
        Example: shopify_us_4545063682180_32128479625348

        Returns: (shopify_product_id, shopify_variant_id)
        """
        if not offer_id:
            return None, None

        match = self.GMC_OFFER_ID_PATTERN.match(offer_id)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def get_variant_info(self, gmc_offer_id: str) -> dict:
        """Look up variant info from variant_index table.

        Returns dict with: master_sku, finish, finish_code, shopify_variant_id
        """
        if not gmc_offer_id:
            return {"master_sku": None, "finish": None, "finish_code": None, "shopify_variant_id": None}

        # Normalize to lowercase before lookup and caching.
        # Google Ads returns uppercase shopify_US_ but variant_index stores lowercase shopify_us_.
        # Without this normalization every lookup is a cache miss and DB query returns no results.
        gmc_offer_id = gmc_offer_id.lower()

        # Check cache
        if gmc_offer_id in self._variant_cache:
            return self._variant_cache[gmc_offer_id]

        try:
            result = (
                self.supabase.table("variant_index")
                .select("master_sku, finish, finish_code, shopify_variant_id")
                .eq("gmc_offer_id", gmc_offer_id)
                .limit(1)
                .execute()
            )

            if result.data:
                info = result.data[0]
                self._variant_cache[gmc_offer_id] = info
                return info

            # Fallback: try to find by shopify_variant_id
            _, variant_id = self.parse_gmc_offer_id(gmc_offer_id)
            if variant_id:
                result = (
                    self.supabase.table("variant_index")
                    .select("master_sku, finish, finish_code, shopify_variant_id")
                    .eq("shopify_variant_id", variant_id)
                    .limit(1)
                    .execute()
                )

                if result.data:
                    info = result.data[0]
                    self._variant_cache[gmc_offer_id] = info
                    return info
        except Exception as e:
            logger.warning(f"Error fetching variant info for {gmc_offer_id}: {e}")

        return {"master_sku": None, "finish": None, "finish_code": None, "shopify_variant_id": None}

    def _fetch_shopping_campaigns(self) -> list[str]:
        """Fetch all Shopping campaign IDs.

        Returns:
            List of campaign resource names
        """
        from google.protobuf.json_format import MessageToDict

        ga_service = self.client.get_service("GoogleAdsService")

        query = """
            SELECT
                campaign.resource_name,
                campaign.id,
                campaign.name
            FROM campaign
            WHERE campaign.advertising_channel_type = 'SHOPPING'
                AND campaign.status = 'ENABLED'
        """

        campaigns = []
        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id, query=query
            )

            for batch in stream:
                for row in batch.results:
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                    campaign = row_dict.get("campaign", {}) or {}
                    resource_name = campaign.get("resource_name")
                    if resource_name:
                        campaigns.append(resource_name)
                        logger.info(f"Found Shopping campaign: {campaign.get('name')} ({campaign.get('id')})")

        except Exception as e:
            logger.warning(f"Error fetching shopping campaigns: {e}")

        return campaigns

    def _fetch_campaign_products(
        self,
        days: int = 30,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, list[str]]:
        """Fetch product item_ids grouped by campaign.

        Uses shopping_performance_view to get products that have had impressions,
        grouped by campaign. This is more reliable than shopping_product which
        has strict filter requirements.

        Args:
            days: Number of days to look back (used if start_date/end_date not provided)
            start_date: Explicit start date (overrides days-based calculation)
            end_date: Explicit end date (overrides days-based calculation)

        Returns:
            Dict mapping campaign.id -> list of item_ids in that campaign
        """
        from google.protobuf.json_format import MessageToDict

        ga_service = self.client.get_service("GoogleAdsService")

        # Compute explicit date range — LAST_N_DAYS syntax only supports specific
        # enum values (LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS) and rejects
        # arbitrary N values like 90 or 180 with INVALID_ARGUMENT errors.
        _end_date = end_date or date.today()
        _start_date = start_date or (_end_date - timedelta(days=days))
        end_date_str = _end_date.strftime("%Y-%m-%d")
        start_date_str = _start_date.strftime("%Y-%m-%d")

        # Use shopping_performance_view to get products with impressions by campaign
        # Note: Must SELECT campaign.advertising_channel_type when filtering by it
        query = f"""
            SELECT
                segments.product_item_id,
                campaign.id,
                campaign.name,
                campaign.advertising_channel_type,
                metrics.impressions
            FROM shopping_performance_view
            WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
                AND campaign.advertising_channel_type = 'SHOPPING'
                AND metrics.impressions > 0
            ORDER BY metrics.impressions DESC
            LIMIT 50000
        """

        campaign_products: dict[str, list[str]] = defaultdict(list)
        seen_products: set[tuple[str, str]] = set()  # (campaign_id, item_id)

        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id, query=query
            )

            for batch in stream:
                for row in batch.results:
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)

                    segments = row_dict.get("segments", {}) or {}
                    campaign = row_dict.get("campaign", {}) or {}

                    item_id = segments.get("product_item_id")
                    campaign_id = str(campaign.get("id", ""))

                    if item_id and campaign_id:
                        # Deduplicate
                        key = (campaign_id, item_id)
                        if key not in seen_products:
                            seen_products.add(key)
                            campaign_products[campaign_id].append(item_id)

            logger.info(f"Found {len(seen_products)} unique product-campaign combinations across {len(campaign_products)} campaigns")

        except Exception as e:
            logger.warning(f"Error fetching campaign products: {e}")

        return dict(campaign_products)

    def fetch_search_terms(
        self,
        days: int = 30,
        limit: int = 1000,
        start_date: date | None = None,
        end_date: date | None = None,
        filter_skus: list[str] | None = None,
    ) -> list[dict]:
        """Fetch search terms from Shopping campaigns WITH variant-level tracking.

        Strategy:
        1. Fetch products by campaign from shopping_performance_view
        2. Fetch search terms with campaign.id from search_term_view
        3. Join via campaign to associate search terms with products

        Args:
            days: Number of days to look back (used if start_date/end_date not provided)
            limit: Maximum results to return
            start_date: Explicit start date (overrides days-based calculation)
            end_date: Explicit end date (overrides days-based calculation)
            filter_skus: If set, only return results for these master_skus

        Returns:
            List of dicts with search term data including variant info
        """
        from google.protobuf.json_format import MessageToDict

        ga_service = self.client.get_service("GoogleAdsService")

        # Step 1: Fetch products grouped by campaign
        logger.info("Fetching products by campaign...")
        campaign_products = self._fetch_campaign_products(
            days=days, start_date=start_date, end_date=end_date
        )
        logger.info(f"Found products across {len(campaign_products)} campaigns")

        # Step 2: Fetch search terms with campaign.id
        # Compute explicit date range — LAST_N_DAYS syntax only supports specific
        # enum values (LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS) and rejects
        # arbitrary N values like 90 or 180 with INVALID_ARGUMENT errors.
        _end_date = end_date or date.today()
        _start_date = start_date or (_end_date - timedelta(days=days))
        st_end_date = _end_date.strftime("%Y-%m-%d")
        st_start_date = _start_date.strftime("%Y-%m-%d")

        query = f"""
            SELECT
                search_term_view.search_term,
                campaign.id,
                campaign.name,
                ad_group.id,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.conversions_value,
                metrics.cost_micros
            FROM search_term_view
            WHERE segments.date BETWEEN '{st_start_date}' AND '{st_end_date}'
                AND campaign.advertising_channel_type = 'SHOPPING'
            ORDER BY metrics.impressions DESC
            LIMIT {limit}
        """

        results = []
        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id, query=query
            )

            for batch in stream:
                for row in batch.results:
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)

                    metrics = row_dict.get("metrics", {}) or {}
                    search_term = row_dict.get("search_term_view", {}).get("search_term")
                    campaign_data = row_dict.get("campaign", {}) or {}
                    ad_group_data = row_dict.get("ad_group", {}) or {}

                    campaign_id = str(campaign_data.get("id", ""))
                    ad_group_id = ad_group_data.get("id")

                    if not search_term:
                        continue

                    # Step 3: Find products in this campaign
                    item_ids = campaign_products.get(campaign_id, [])

                    # Phase 13 fix: emit one result per item_id so each variant gets
                    # credited for the search term (previously used item_ids[0] which
                    # attributed all terms to the single highest-impression variant).
                    if item_ids:
                        for item_id in item_ids[:10]:  # up to 10 variants per campaign
                            variant_info = self.get_variant_info(item_id)
                            results.append({
                                "search_term": search_term,
                                "impressions": int(metrics.get("impressions", 0) or 0),
                                "clicks": int(metrics.get("clicks", 0) or 0),
                                "conversions": float(metrics.get("conversions", 0) or 0),
                                "conversion_value": float(metrics.get("conversions_value", 0) or 0),
                                "cost_micros": int(metrics.get("cost_micros", 0) or 0),
                                "campaign_id": campaign_id,
                                "ad_group_id": ad_group_id,
                                "item_ids": item_ids[:10],
                                "gmc_offer_id": item_id,
                                "master_sku": variant_info.get("master_sku"),
                                "finish": variant_info.get("finish"),
                                "finish_code": variant_info.get("finish_code"),
                                "shopify_variant_id": variant_info.get("shopify_variant_id"),
                            })
                    else:
                        # No products in campaign — emit one row with null gmc_offer_id
                        results.append({
                            "search_term": search_term,
                            "impressions": int(metrics.get("impressions", 0) or 0),
                            "clicks": int(metrics.get("clicks", 0) or 0),
                            "conversions": float(metrics.get("conversions", 0) or 0),
                            "conversion_value": float(metrics.get("conversions_value", 0) or 0),
                            "cost_micros": int(metrics.get("cost_micros", 0) or 0),
                            "campaign_id": campaign_id,
                            "ad_group_id": ad_group_id,
                            "item_ids": [],
                            "gmc_offer_id": None,
                            "master_sku": None,
                            "finish": None,
                            "finish_code": None,
                            "shopify_variant_id": None,
                        })

        except Exception as e:
            logger.error(f"Google Ads API error: {e}")
            raise

        # Apply filter_skus if provided — limits results to specified master_skus only
        if filter_skus:
            filter_set = set(filter_skus)
            results = [r for r in results if r.get("master_sku") in filter_set]
            logger.info(f"filter_skus applied: kept {len(results)} results for {len(filter_set)} SKUs")

        return results

    def get_terms_for_master_sku(
        self,
        master_sku: str,
        shopify_product_id: str,
        days: int = 30,
    ) -> dict:
        """Get search terms for all variants of a master SKU.

        Args:
            master_sku: The master SKU identifier
            shopify_product_id: Shopify product ID for offer ID matching
            days: Number of days to look back

        Returns:
            {
                aggregate: All queries combined across variants,
                by_variant: Queries broken down by finish variant
            }
        """
        from google.protobuf.json_format import MessageToDict

        ga_service = self.client.get_service("GoogleAdsService")

        # Note: Google Ads API doesn't support both search_term and product_item_id
        # in the same query. This function is now deprecated and returns empty results.
        # Use fetch_search_terms() for search term data at the campaign level.
        logger.warning(
            f"get_terms_for_master_sku is deprecated due to API limitations. "
            f"Use fetch_search_terms() and match via variant_index table."
        )
        return {"aggregate": [], "by_variant": {}}

        # Legacy code below kept for reference but won't execute
        offer_pattern = f"shopify_us_{shopify_product_id}_%"

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.conversions_value
            FROM search_term_view
            WHERE segments.date DURING LAST_{days}_DAYS
                AND campaign.advertising_channel_type = 'SHOPPING'
            ORDER BY metrics.impressions DESC
            LIMIT 500
        """

        aggregate: dict[str, dict] = {}  # query_text -> aggregated metrics
        by_variant: dict[str, dict] = {}  # finish_code -> {query_text -> metrics}

        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id, query=query
            )

            for batch in stream:
                for row in batch.results:
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)

                    search_term = row_dict.get("search_term_view", {}).get("search_term")
                    if not search_term:
                        continue

                    gmc_offer_id = None  # Not available from search_term_view
                    variant_info = self.get_variant_info(gmc_offer_id)
                    finish_code = variant_info.get("finish_code") or "UNKNOWN"

                    metrics = row_dict.get("metrics", {}) or {}
                    impressions = int(metrics.get("impressions", 0) or 0)
                    clicks = int(metrics.get("clicks", 0) or 0)
                    conversions = float(metrics.get("conversions", 0) or 0)
                    conversion_value = float(metrics.get("conversions_value", 0) or 0)

                    # Aggregate across all variants
                    if search_term not in aggregate:
                        aggregate[search_term] = {
                            "search_term": search_term,
                            "impressions": 0,
                            "clicks": 0,
                            "conversions": 0,
                            "conversion_value": 0,
                            "variants": set(),
                        }
                    aggregate[search_term]["impressions"] += impressions
                    aggregate[search_term]["clicks"] += clicks
                    aggregate[search_term]["conversions"] += conversions
                    aggregate[search_term]["conversion_value"] += conversion_value
                    aggregate[search_term]["variants"].add(finish_code)

                    # Track by variant
                    if finish_code not in by_variant:
                        by_variant[finish_code] = {}
                    if search_term not in by_variant[finish_code]:
                        by_variant[finish_code][search_term] = {
                            "search_term": search_term,
                            "impressions": 0,
                            "clicks": 0,
                            "conversions": 0,
                            "conversion_value": 0,
                            "finish": variant_info.get("finish"),
                            "finish_code": finish_code,
                        }
                    by_variant[finish_code][search_term]["impressions"] += impressions
                    by_variant[finish_code][search_term]["clicks"] += clicks
                    by_variant[finish_code][search_term]["conversions"] += conversions
                    by_variant[finish_code][search_term]["conversion_value"] += conversion_value

        except Exception as e:
            logger.error(f"Google Ads API error: {e}")
            raise

        # Convert aggregate variants set to count
        for query in aggregate.values():
            query["variant_count"] = len(query["variants"])
            del query["variants"]

        # Sort by impressions
        aggregate_list = sorted(
            aggregate.values(), key=lambda x: x["impressions"], reverse=True
        )

        by_variant_sorted = {}
        for finish_code, queries in by_variant.items():
            by_variant_sorted[finish_code] = sorted(
                queries.values(), key=lambda x: x["impressions"], reverse=True
            )

        return {
            "master_sku": master_sku,
            "aggregate": aggregate_list,
            "by_variant": by_variant_sorted,
        }

    def get_terms_for_specific_variant(
        self,
        gmc_offer_id: str,
        days: int = 30,
    ) -> list[dict]:
        """Get search terms for a SPECIFIC variant only.

        Use this to see what queries trigger a specific finish variant.

        Args:
            gmc_offer_id: The GMC offer ID for the variant
            days: Number of days to look back

        Returns:
            List of search term dicts for this variant
        """
        from google.protobuf.json_format import MessageToDict

        ga_service = self.client.get_service("GoogleAdsService")

        # Compute explicit date range — LAST_N_DAYS syntax only supports specific
        # enum values (LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS) and rejects
        # arbitrary N values like 90 or 180 with INVALID_ARGUMENT errors.
        sv_end_date = date.today().strftime("%Y-%m-%d")
        sv_start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = f"""
            SELECT
                search_term_view.search_term,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.conversions_value
            FROM search_term_view
            WHERE segments.date BETWEEN '{sv_start_date}' AND '{sv_end_date}'
                AND campaign.advertising_channel_type = 'SHOPPING'
                AND segments.product_item_id = '{gmc_offer_id}'
            ORDER BY metrics.impressions DESC
            LIMIT 100
        """

        results = []
        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id, query=query
            )

            for batch in stream:
                for row in batch.results:
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)

                    search_term = row_dict.get("search_term_view", {}).get("search_term")
                    if not search_term:
                        continue

                    metrics = row_dict.get("metrics", {}) or {}
                    results.append({
                        "search_term": search_term,
                        "impressions": int(metrics.get("impressions", 0) or 0),
                        "clicks": int(metrics.get("clicks", 0) or 0),
                        "conversions": float(metrics.get("conversions", 0) or 0),
                        "conversion_value": float(metrics.get("conversions_value", 0) or 0),
                    })

        except Exception as e:
            logger.error(f"Google Ads API error: {e}")
            raise

        return results

    def identify_finish_specific_queries(
        self,
        master_sku_data: dict,
    ) -> dict[str, list[dict]]:
        """Identify queries that are specific to certain finishes.

        Example:
        - "antique brass towel bar" -> likely only triggers AB variants
        - "chrome bathroom accessories" -> likely only triggers PC/SCH variants

        Args:
            master_sku_data: Result from get_terms_for_master_sku()

        Returns:
            {finish_code: [queries that primarily trigger this finish]}
        """
        by_variant = master_sku_data.get("by_variant", {})
        aggregate = {q["search_term"]: q for q in master_sku_data.get("aggregate", [])}

        finish_specific = {}

        for finish_code, queries in by_variant.items():
            finish_specific[finish_code] = []

            for query_data in queries:
                search_term = query_data["search_term"]
                variant_impressions = query_data["impressions"]

                # Check if this query is disproportionately associated with this finish
                total_impressions = aggregate.get(search_term, {}).get("impressions", 0)

                if total_impressions > 0:
                    share = variant_impressions / total_impressions
                    # If this finish gets >60% of impressions for this query, it's finish-specific
                    if share > 0.6:
                        finish_specific[finish_code].append({
                            "query": search_term,
                            "share": share,
                            "impressions": variant_impressions,
                        })

        return finish_specific

    def save_search_terms_to_db(
        self,
        search_terms: list[dict],
        period_start: date,
        period_end: date,
        sync_job_id: str | None = None,
    ) -> int:
        """Save search terms to the search_queries table.

        Args:
            search_terms: List of search term dicts from fetch_search_terms
            period_start: Start date of the data period
            period_end: End date of the data period
            sync_job_id: Optional sync job ID for tracking

        Returns:
            Number of rows upserted
        """
        if not search_terms:
            return 0

        # Deduplicate by (query_text, gmc_offer_id) - aggregate metrics
        # The same search term can appear across multiple ad_groups
        deduped: dict[tuple[str, str | None], dict] = {}

        for term in search_terms:
            query_text = term["search_term"]
            gmc_offer_id = term.get("gmc_offer_id")

            # Normalize offer ID case to uppercase (shopify_us_ → shopify_US_)
            if gmc_offer_id:
                gmc_offer_id = re.sub(r'^shopify_us_', 'shopify_US_', gmc_offer_id, flags=re.IGNORECASE)

            key = (query_text, gmc_offer_id)

            if key not in deduped:
                # Normalize case for all item_ids in the array
                item_ids = term.get("item_ids", [])
                if item_ids:
                    item_ids = [
                        re.sub(r'^shopify_us_', 'shopify_US_', offer_id, flags=re.IGNORECASE)
                        for offer_id in item_ids
                    ]
                # Store as JSON string for JSONB column (Supabase expects string)
                item_ids_json = json.dumps(item_ids) if item_ids else None

                deduped[key] = {
                    "query_text": query_text,
                    "gmc_offer_id": gmc_offer_id,
                    "master_sku": term.get("master_sku"),
                    "finish": term.get("finish"),
                    "finish_code": term.get("finish_code"),
                    "shopify_variant_id": term.get("shopify_variant_id"),
                    "campaign_id": term.get("campaign_id"),
                    "ad_group_id": term.get("ad_group_id"),
                    "item_ids": item_ids_json,
                    "impressions": term.get("impressions", 0),
                    "clicks": term.get("clicks", 0),
                    "conversions": term.get("conversions", 0),
                    "conversion_value": term.get("conversion_value", 0),
                    "cost_micros": term.get("cost_micros", 0),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "sync_job_id": sync_job_id,
                    "fetched_at": datetime.utcnow().isoformat(),
                    "synced_at": datetime.utcnow().isoformat(),
                }
            else:
                # Aggregate metrics for duplicate entries
                deduped[key]["impressions"] += term.get("impressions", 0)
                deduped[key]["clicks"] += term.get("clicks", 0)
                deduped[key]["conversions"] += term.get("conversions", 0)
                deduped[key]["conversion_value"] += term.get("conversion_value", 0)
                deduped[key]["cost_micros"] += term.get("cost_micros", 0)

        rows = list(deduped.values())
        logger.info(f"Deduped {len(search_terms)} search terms to {len(rows)} unique entries")

        try:
            # Use proper Supabase upsert with ignoreDuplicates to handle conflicts
            # The unique constraint is (query_text, gmc_offer_id, period_start, period_end)
            result = self.supabase.table("search_queries").upsert(
                rows,
                on_conflict="query_text,gmc_offer_id,period_start,period_end",
                ignore_duplicates=False  # Update existing rows instead of ignoring
            ).execute()

            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error saving search terms: {e}")
            raise

    def aggregate_by_master_sku(
        self,
        period_start: date,
        period_end: date,
    ) -> int:
        """Aggregate search queries by master SKU and save to search_queries_by_master_sku.

        Args:
            period_start: Start date of the data period
            period_end: End date of the data period

        Returns:
            Number of aggregated rows created/updated
        """
        try:
            # Fetch all queries for this period
            result = (
                self.supabase.table("search_queries")
                .select("*")
                .eq("period_start", period_start.isoformat())
                .eq("period_end", period_end.isoformat())
                .not_.is_("master_sku", "null")
                .execute()
            )

            if not result.data:
                return 0

            # Aggregate by master_sku + query_text
            aggregated: dict[tuple[str, str], dict] = {}

            for row in result.data:
                key = (row["master_sku"], row["query_text"])

                if key not in aggregated:
                    aggregated[key] = {
                        "master_sku": row["master_sku"],
                        "query_text": row["query_text"],
                        "total_impressions": 0,
                        "total_clicks": 0,
                        "total_conversions": 0,
                        "total_conversion_value": 0,
                        "variants": set(),
                        "top_variant_impressions": 0,
                        "top_variant_finish": None,
                        "top_variant_finish_code": None,
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                    }

                agg = aggregated[key]
                agg["total_impressions"] += row.get("impressions", 0)
                agg["total_clicks"] += row.get("clicks", 0)
                agg["total_conversions"] += row.get("conversions", 0)
                agg["total_conversion_value"] += row.get("conversion_value", 0)

                if row.get("finish_code"):
                    agg["variants"].add(row["finish_code"])

                # Track top variant
                if row.get("impressions", 0) > agg["top_variant_impressions"]:
                    agg["top_variant_impressions"] = row["impressions"]
                    agg["top_variant_finish"] = row.get("finish")
                    agg["top_variant_finish_code"] = row.get("finish_code")

            # Prepare rows for upsert
            rows = []
            for agg in aggregated.values():
                rows.append({
                    "master_sku": agg["master_sku"],
                    "query_text": agg["query_text"],
                    "total_impressions": agg["total_impressions"],
                    "total_clicks": agg["total_clicks"],
                    "total_conversions": agg["total_conversions"],
                    "total_conversion_value": agg["total_conversion_value"],
                    "variant_count": len(agg["variants"]),
                    "top_variant_finish": agg["top_variant_finish"],
                    "top_variant_finish_code": agg["top_variant_finish_code"],
                    "period_start": agg["period_start"],
                    "period_end": agg["period_end"],
                    "updated_at": datetime.utcnow().isoformat(),
                })

            result = self.supabase.table("search_queries_by_master_sku").upsert(
                rows,
                on_conflict="master_sku,query_text,period_start,period_end",
            ).execute()

            return len(result.data) if result.data else 0

        except Exception as e:
            logger.error(f"Error aggregating by master SKU: {e}")
            raise

    def enrich_with_keyword_metrics(
        self,
        period_start: date,
        period_end: date,
        batch_size: int = 100,
    ) -> int:
        """Enrich search queries with Keyword Planner metrics.

        Args:
            period_start: Start date of the data period
            period_end: End date of the data period
            batch_size: Number of keywords to process per Keyword Planner API call

        Returns:
            Number of queries enriched
        """
        kp_client = KeywordPlannerClient(self.customer_id)

        try:
            # Fetch queries that haven't been enriched recently
            result = (
                self.supabase.table("search_queries")
                .select("id, query_text")
                .eq("period_start", period_start.isoformat())
                .eq("period_end", period_end.isoformat())
                .is_("keyword_metrics_updated_at", "null")
                .limit(1000)
                .execute()
            )

            if not result.data:
                return 0

            # Extract unique keywords
            keywords = list(set(row["query_text"] for row in result.data))
            id_by_query = {row["query_text"]: row["id"] for row in result.data}

            # Fetch metrics
            all_metrics = kp_client.get_historical_metrics(keywords)

            # Update search_queries with metrics
            enriched_count = 0
            for keyword, metrics in all_metrics.items():
                if keyword in id_by_query:
                    self.supabase.table("search_queries").update({
                        "avg_monthly_searches": metrics["avg_monthly_searches"],
                        "competition": metrics["competition"],
                        "competition_index": metrics["competition_index"],
                        "low_cpc_micros": metrics["low_cpc_micros"],
                        "high_cpc_micros": metrics["high_cpc_micros"],
                        "keyword_metrics_updated_at": datetime.utcnow().isoformat(),
                    }).eq("query_text", keyword).eq(
                        "period_start", period_start.isoformat()
                    ).eq("period_end", period_end.isoformat()).execute()

                    enriched_count += 1

            # Also update aggregated table
            for keyword, metrics in all_metrics.items():
                self.supabase.table("search_queries_by_master_sku").update({
                    "avg_monthly_searches": metrics["avg_monthly_searches"],
                    "competition": metrics["competition"],
                    "competition_index": metrics["competition_index"],
                }).eq("query_text", keyword).eq(
                    "period_start", period_start.isoformat()
                ).eq("period_end", period_end.isoformat()).execute()

            return enriched_count

        except Exception as e:
            logger.error(f"Error enriching with keyword metrics: {e}")
            raise
