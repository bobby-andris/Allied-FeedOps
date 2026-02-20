"""Performance impact monitoring helpers and pipeline routines.

This module implements a daily snapshot collector and difference-in-differences
impact scoring pipeline for Google Ads shopping performance.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import fetch_batch_product_performance

logger = logging.getLogger(__name__)

METRIC_COLUMNS: tuple[str, ...] = (
    "roas",
    "cvr",
    "ctr",
    "clicks",
    "conversions",
    "cost",
    "conversion_value",
    "impressions",
)

GUARDRAIL_METRICS: tuple[str, ...] = ("impressions", "conversions", "ctr", "cvr")


def _parse_iso_date(value: str | date | datetime) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def build_refresh_dates(run_date: date, days_to_refresh: int = 3) -> list[str]:
    """Build a rolling lag-correction date list in D-1..D-n format."""
    days = max(1, days_to_refresh)
    return [(run_date - timedelta(days=offset)).isoformat() for offset in range(1, days + 1)]


def compute_diff_in_diff_lift_pct(
    *,
    treated_pre: float,
    treated_post: float,
    control_pre: float,
    control_post: float,
) -> float | None:
    """Return percentage-point difference-in-differences lift.

    Formula:
      DID% = ((treated_post - treated_pre) / treated_pre) * 100
           - ((control_post - control_pre) / control_pre) * 100

    Returns None when a pre-period denominator is zero.
    """
    if treated_pre == 0 or control_pre == 0:
        return None

    treated_change_pct = ((treated_post - treated_pre) / treated_pre) * 100.0
    control_change_pct = ((control_post - control_pre) / control_pre) * 100.0
    return treated_change_pct - control_change_pct


def classify_overall_label(
    *,
    roas_did_lift_pct: float | None,
    guardrail_deltas: dict[str, float],
    positive_threshold: float = 5.0,
    negative_threshold: float = -5.0,
    severe_guardrail_threshold: float = -15.0,
) -> str:
    """Classify overall impact label under balanced thresholding rules."""
    severe_guardrail_drop = any(
        guardrail_deltas.get(metric, 0.0) <= severe_guardrail_threshold
        for metric in GUARDRAIL_METRICS
    )

    if roas_did_lift_pct is not None and roas_did_lift_pct <= negative_threshold:
        return "negative"

    if (
        roas_did_lift_pct is not None
        and roas_did_lift_pct >= positive_threshold
        and not severe_guardrail_drop
    ):
        return "positive"

    return "neutral"


def compute_confidence(
    *,
    sample_size_treated: int,
    sample_size_control: int,
    primary_effect: float,
) -> float:
    """Compute a normalized confidence score in [0, 1].

    This is a pragmatic confidence proxy combining sample size sufficiency and
    effect magnitude. It is intentionally conservative at low sample sizes.
    """
    total_samples = max(0, sample_size_treated) + max(0, sample_size_control)
    if total_samples == 0:
        return 0.0

    size_component = min(1.0, math.log10(total_samples + 1) / 3.0)
    effect_component = min(1.0, abs(primary_effect) / 20.0)

    # Weight sample size higher than magnitude to avoid overconfidence in noise.
    confidence = (0.7 * size_component) + (0.3 * effect_component)
    return round(max(0.0, min(1.0, confidence)), 4)


def _paginate_rows(
    table: str,
    columns: str,
    *,
    page_size: int = 1000,
    filters: list[tuple[str, str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all rows with PostgREST range pagination."""
    client = get_client()
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = client.table(table).select(columns).range(offset, offset + page_size - 1)
        for op, key, value in filters or []:
            if op == "eq":
                query = query.eq(key, value)
            elif op == "gte":
                query = query.gte(key, value)
            elif op == "lte":
                query = query.lte(key, value)
            elif op == "in":
                query = query.in_(key, value)
            elif op == "is_null":
                query = query.is_(key, value)

        result = query.execute()
        data = result.data or []
        if not data:
            break

        rows.extend(data)
        if len(data) < page_size:
            break

        offset += page_size

    return rows


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def _fetch_latest_publish_events(
    *,
    platform: str,
    environment: str,
    master_skus: list[str] | None,
    published_after: date,
) -> dict[str, dict[str, Any]]:
    """Get latest successful publish event per SKU."""
    filters: list[tuple[str, str, Any]] = [
        ("eq", "action", "publish"),
        ("eq", "status", "success"),
        ("eq", "platform", platform),
        ("eq", "environment", environment),
        ("gte", "published_at", published_after.isoformat()),
    ]

    events = _paginate_rows(
        "publish_events",
        "id,master_sku,platform,environment,published_at,content_version,product_category",
        filters=filters,
    )

    if master_skus:
        requested = set(master_skus)
        events = [event for event in events if event.get("master_sku") in requested]

    latest_by_sku: dict[str, dict[str, Any]] = {}
    for event in events:
        sku = event.get("master_sku")
        if not sku:
            continue

        existing = latest_by_sku.get(sku)
        if not existing or str(event.get("published_at", "")) > str(existing.get("published_at", "")):
            latest_by_sku[sku] = event

    return latest_by_sku


def _fetch_variant_rows_for_skus(master_skus: list[str]) -> list[dict[str, Any]]:
    """Fetch variant rows with gmc_offer_id and category for a SKU list."""
    if not master_skus:
        return []

    rows: list[dict[str, Any]] = []
    for sku_chunk in _chunked(sorted(set(master_skus)), 200):
        rows.extend(
            _paginate_rows(
                "variant_index",
                "master_sku,gmc_offer_id,product_category",
                filters=[("in", "master_sku", sku_chunk)],
            )
        )

    return rows


def _build_master_sku_categories(variant_rows: list[dict[str, Any]]) -> dict[str, str | None]:
    categories: dict[str, str | None] = {}
    for row in variant_rows:
        sku = row.get("master_sku")
        if not sku:
            continue
        # Keep the first observed category so category matching remains deterministic.
        if sku not in categories:
            categories[sku] = row.get("product_category")
    return categories


def _mean_metric_for_window(rows: list[dict[str, Any]], metric: str, start: date, end: date) -> float:
    values: list[float] = []
    for row in rows:
        snapshot_date = _parse_iso_date(row.get("snapshot_date"))
        if start <= snapshot_date <= end:
            values.append(float(row.get(metric) or 0.0))

    if not values:
        return 0.0
    return sum(values) / len(values)


def _window_sample_size(rows: list[dict[str, Any]], start: date, end: date) -> int:
    count = 0
    for row in rows:
        snapshot_date = _parse_iso_date(row.get("snapshot_date"))
        if start <= snapshot_date <= end:
            count += 1
    return count


def collect_daily_performance_snapshots(
    *,
    run_date: date,
    platform: str = "google",
    environment: str = "production",
    master_skus: list[str] | None = None,
    days_to_refresh: int = 3,
    max_controls: int = 500,
) -> dict[str, Any]:
    """Collect daily performance snapshots with rolling lag correction."""
    if platform != "google":
        raise ValueError("Daily collector currently supports platform='google' only")

    supabase = get_client()
    refresh_dates = build_refresh_dates(run_date, days_to_refresh=days_to_refresh)

    latest_publishes = _fetch_latest_publish_events(
        platform=platform,
        environment=environment,
        master_skus=master_skus,
        published_after=run_date - timedelta(days=365),
    )
    treated_skus = sorted(latest_publishes.keys())

    all_variant_rows = _paginate_rows("variant_index", "master_sku,product_category")
    all_sku_categories = _build_master_sku_categories(all_variant_rows)
    all_skus = sorted(all_sku_categories.keys())

    if master_skus:
        target_scope = sorted(set(master_skus))
        target_scope_set = set(target_scope)
        scoped_categories = {
            all_sku_categories.get(sku)
            for sku in target_scope
            if all_sku_categories.get(sku)
        }
        scoped_categories.discard(None)

        control_skus = [
            sku
            for sku in all_skus
            if sku not in target_scope_set
            and (
                not scoped_categories
                or all_sku_categories.get(sku) in scoped_categories
            )
        ][:max_controls]
        target_skus = sorted(target_scope_set.union(control_skus))
    else:
        treated_set = set(treated_skus)
        control_skus = [sku for sku in all_skus if sku not in treated_set][:max_controls]
        target_skus = sorted(set(treated_skus).union(control_skus))

    variant_rows = _fetch_variant_rows_for_skus(target_skus)

    offer_to_sku: dict[str, str] = {}
    sku_to_category: dict[str, str | None] = {}
    for row in variant_rows:
        sku = row.get("master_sku")
        offer_id = row.get("gmc_offer_id")
        if not sku:
            continue
        if sku not in sku_to_category:
            sku_to_category[sku] = row.get("product_category")
        if offer_id:
            offer_to_sku[offer_id] = sku

    offer_ids = sorted(offer_to_sku.keys())

    rows_upserted = 0
    snapshot_rows_total = 0

    if not offer_ids:
        return {
            "success": True,
            "message": "No eligible offer IDs found for snapshot collection",
            "run_date": run_date.isoformat(),
            "snapshot_dates": refresh_dates,
            "skus_processed": len(target_skus),
            "rows_upserted": 0,
            "treated_skus": len(treated_skus),
            "control_skus": len(control_skus),
        }

    # Pre-sort publish events by publish date for date-accurate event assignment.
    publish_history_by_sku: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in _paginate_rows(
        "publish_events",
        "id,master_sku,published_at,content_version,product_category,platform,environment,action,status",
        filters=[
            ("eq", "action", "publish"),
            ("eq", "status", "success"),
            ("eq", "platform", platform),
            ("eq", "environment", environment),
            ("gte", "published_at", (run_date - timedelta(days=365)).isoformat()),
        ],
    ):
        sku = event.get("master_sku")
        if sku in target_skus:
            publish_history_by_sku[sku].append(event)

    for sku in publish_history_by_sku:
        publish_history_by_sku[sku].sort(key=lambda row: str(row.get("published_at", "")), reverse=True)

    for snapshot_date_str in refresh_dates:
        snapshot_date = _parse_iso_date(snapshot_date_str)
        fetched_at = datetime.utcnow().isoformat() + "Z"
        by_offer = fetch_batch_product_performance(
            offer_ids=offer_ids,
            start_date=snapshot_date_str,
            end_date=snapshot_date_str,
        )

        aggregated_by_sku: dict[str, dict[str, float]] = {
            sku: {
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
                "cost": 0.0,
            }
            for sku in target_skus
        }

        for offer_id, metrics in by_offer.items():
            sku = offer_to_sku.get(offer_id)
            if not sku:
                continue
            entry = aggregated_by_sku.setdefault(
                sku,
                {
                    "impressions": 0.0,
                    "clicks": 0.0,
                    "conversions": 0.0,
                    "conversion_value": 0.0,
                    "cost": 0.0,
                },
            )
            entry["impressions"] += float(metrics.get("impressions") or 0.0)
            entry["clicks"] += float(metrics.get("clicks") or 0.0)
            entry["conversions"] += float(metrics.get("conversions") or 0.0)
            entry["conversion_value"] += float(metrics.get("conversion_value") or 0.0)
            entry["cost"] += float(metrics.get("cost") or 0.0)

        payload: list[dict[str, Any]] = []

        for sku in target_skus:
            metrics = aggregated_by_sku.get(sku) or {
                "impressions": 0.0,
                "clicks": 0.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
                "cost": 0.0,
            }

            clicks = metrics["clicks"]
            impressions = metrics["impressions"]
            conversions = metrics["conversions"]
            cost = metrics["cost"]
            conversion_value = metrics["conversion_value"]

            ctr = (clicks / impressions) if impressions > 0 else 0.0
            cvr = (conversions / clicks) if clicks > 0 else 0.0
            cpc = (cost / clicks) if clicks > 0 else 0.0
            roas = (conversion_value / cost) if cost > 0 else 0.0

            matched_event = None
            for event in publish_history_by_sku.get(sku, []):
                published_at = _parse_iso_date(event["published_at"])
                if published_at <= snapshot_date:
                    matched_event = event
                    break

            publish_event_id = matched_event.get("id") if matched_event else None
            content_version = str(matched_event.get("content_version")) if matched_event and matched_event.get("content_version") is not None else None
            days_since_publish = (
                (snapshot_date - _parse_iso_date(matched_event["published_at"])).days
                if matched_event
                else None
            )

            payload.append(
                {
                    "master_sku": sku,
                    "platform": platform,
                    "environment": environment,
                    "snapshot_date": snapshot_date.isoformat(),
                    "impressions": int(round(impressions)),
                    "clicks": int(round(clicks)),
                    "ctr": round(ctr, 6),
                    "conversions": int(round(conversions)),
                    "conversion_value": round(conversion_value, 6),
                    "cvr": round(cvr, 6),
                    "cost": round(cost, 6),
                    "cpc": round(cpc, 6),
                    "roas": round(roas, 6),
                    "publish_event_id": publish_event_id,
                    "content_version": content_version,
                    "days_since_publish": days_since_publish,
                    "cohort_type": "treated" if publish_event_id else "control",
                    "product_category": sku_to_category.get(sku),
                    "fetched_at": fetched_at,
                }
            )

        if payload:
            supabase.table("performance_snapshots").upsert(
                payload,
                on_conflict="master_sku,platform,environment,snapshot_date",
            ).execute()
            rows_upserted += len(payload)
            snapshot_rows_total += len(payload)

    return {
        "success": True,
        "run_date": run_date.isoformat(),
        "snapshot_dates": refresh_dates,
        "skus_processed": len(target_skus),
        "offer_ids_processed": len(offer_ids),
        "rows_upserted": rows_upserted,
        "rows_processed": snapshot_rows_total,
        "treated_skus": len(treated_skus),
        "control_skus": len(control_skus),
        "message": f"Upserted {rows_upserted} snapshot rows across {len(refresh_dates)} refresh dates",
    }


def compute_and_store_impact_scores(
    *,
    run_date: date,
    platform: str = "google",
    environment: str = "production",
    master_skus: list[str] | None = None,
    pre_window_days: int = 30,
    post_window_days: int = 30,
) -> dict[str, Any]:
    """Compute and persist difference-in-differences impact scores."""
    if platform != "google":
        raise ValueError("Impact computation currently supports platform='google' only")

    supabase = get_client()

    latest_events = _fetch_latest_publish_events(
        platform=platform,
        environment=environment,
        master_skus=master_skus,
        published_after=run_date - timedelta(days=365),
    )

    if not latest_events:
        return {
            "success": True,
            "run_date": run_date.isoformat(),
            "events_processed": 0,
            "rows_upserted": 0,
            "message": "No eligible publish events found for impact computation",
        }

    min_pre_start = min(
        _parse_iso_date(event["published_at"]) - timedelta(days=pre_window_days)
        for event in latest_events.values()
    )

    snapshot_rows = _paginate_rows(
        "performance_snapshots",
        "master_sku,platform,environment,snapshot_date,impressions,clicks,ctr,conversions,conversion_value,cvr,cost,cpc,roas,publish_event_id,product_category",
        filters=[
            ("eq", "platform", platform),
            ("eq", "environment", environment),
            ("gte", "snapshot_date", min_pre_start.isoformat()),
            ("lte", "snapshot_date", run_date.isoformat()),
        ],
    )

    if master_skus:
        scope = set(master_skus)
        snapshot_rows = [row for row in snapshot_rows if row.get("master_sku") in scope]

    rows_by_sku: dict[str, list[dict[str, Any]]] = defaultdict(list)
    control_rows_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_control_rows: list[dict[str, Any]] = []
    treated_event_skus = set(latest_events.keys())

    for row in snapshot_rows:
        sku = row.get("master_sku")
        if not sku:
            continue
        rows_by_sku[sku].append(row)

        if not row.get("publish_event_id") and sku not in treated_event_skus:
            global_control_rows.append(row)
            category = row.get("product_category") or "__uncategorized__"
            control_rows_by_category[category].append(row)

    impact_rows: list[dict[str, Any]] = []

    for sku, event in latest_events.items():
        if sku not in rows_by_sku:
            continue

        publish_date = _parse_iso_date(event["published_at"])
        if publish_date >= run_date:
            continue

        pre_start = publish_date - timedelta(days=pre_window_days)
        pre_end = publish_date - timedelta(days=1)
        post_start = publish_date + timedelta(days=1)
        post_end = min(publish_date + timedelta(days=post_window_days), run_date)

        if post_start > post_end:
            continue

        treated_rows = rows_by_sku.get(sku, [])
        category = event.get("product_category") or "__uncategorized__"
        control_rows = control_rows_by_category.get(category) or global_control_rows

        treated_sample_size = min(
            _window_sample_size(treated_rows, pre_start, pre_end),
            _window_sample_size(treated_rows, post_start, post_end),
        )
        control_sample_size = min(
            _window_sample_size(control_rows, pre_start, pre_end),
            _window_sample_size(control_rows, post_start, post_end),
        )

        metric_payload: dict[str, dict[str, float | None]] = {}
        for metric in METRIC_COLUMNS:
            pre_value = _mean_metric_for_window(treated_rows, metric, pre_start, pre_end)
            post_value = _mean_metric_for_window(treated_rows, metric, post_start, post_end)
            control_pre = _mean_metric_for_window(control_rows, metric, pre_start, pre_end)
            control_post = _mean_metric_for_window(control_rows, metric, post_start, post_end)
            did_lift = compute_diff_in_diff_lift_pct(
                treated_pre=pre_value,
                treated_post=post_value,
                control_pre=control_pre,
                control_post=control_post,
            )
            metric_payload[metric] = {
                "pre": pre_value,
                "post": post_value,
                "control_pre": control_pre,
                "control_post": control_post,
                "did": did_lift,
            }

        guardrail_deltas = {
            metric: float(metric_payload.get(metric, {}).get("did") or 0.0)
            for metric in GUARDRAIL_METRICS
        }
        roas_did = metric_payload.get("roas", {}).get("did")

        label = classify_overall_label(
            roas_did_lift_pct=roas_did if isinstance(roas_did, float) else None,
            guardrail_deltas=guardrail_deltas,
        )
        confidence = compute_confidence(
            sample_size_treated=treated_sample_size,
            sample_size_control=control_sample_size,
            primary_effect=float(roas_did or 0.0),
        )

        for metric in METRIC_COLUMNS:
            payload = metric_payload[metric]
            impact_rows.append(
                {
                    "publish_event_id": event["id"],
                    "master_sku": sku,
                    "platform": platform,
                    "environment": environment,
                    "metric_name": metric,
                    "pre_value": round(float(payload["pre"] or 0.0), 8),
                    "post_value": round(float(payload["post"] or 0.0), 8),
                    "control_pre": round(float(payload["control_pre"] or 0.0), 8),
                    "control_post": round(float(payload["control_post"] or 0.0), 8),
                    "did_lift_pct": round(float(payload["did"]), 8) if payload["did"] is not None else None,
                    "label": label,
                    "confidence": confidence,
                    "sample_size_treated": treated_sample_size,
                    "sample_size_control": control_sample_size,
                    "window_pre_days": pre_window_days,
                    "window_post_days": post_window_days,
                    "run_date": run_date.isoformat(),
                }
            )

    rows_upserted = 0
    for offset in range(0, len(impact_rows), 500):
        payload = impact_rows[offset:offset + 500]
        if not payload:
            continue
        computed_at = datetime.utcnow().isoformat() + "Z"
        for row in payload:
            row["computed_at"] = computed_at
        supabase.table("performance_impact_scores").upsert(
            payload,
            on_conflict="publish_event_id,metric_name,platform,environment",
        ).execute()
        rows_upserted += len(payload)

    return {
        "success": True,
        "run_date": run_date.isoformat(),
        "events_processed": len(latest_events),
        "rows_upserted": rows_upserted,
        "message": f"Computed {rows_upserted} metric impact rows",
    }
