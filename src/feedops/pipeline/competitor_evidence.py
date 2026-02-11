"""Competitor evidence fetching and classification.

This module is intentionally **read-only**: it fetches competitor listings and
aggregated patterns from Supabase and returns structured context grouped by
product category.

Safety notes:
- This data reflects *competitor* listings/patterns and must not be treated as
  proof of Allied Brass product specifications.
- Do not generate comparative claims ("better than X") from this evidence.
- Any product-specific claim still requires product evidence (catalog/specs).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Literal
from urllib.parse import urlparse

from feedops.db.supabase_client import get_client, is_supabase_available

SourceBucket = Literal["direct", "marketplace", "mixed", "unknown"]


@dataclass(frozen=True)
class NameCount:
    name: str
    count: int


@dataclass(frozen=True)
class CompetitorPattern:
    pattern_type: str
    pattern_value: str
    frequency: int | None
    avg_position: float | None
    sources: tuple[str, ...]
    example_titles: tuple[str, ...]


@dataclass(frozen=True)
class CompetitorBucket:
    listing_count: int
    top_domains: tuple[NameCount, ...]
    top_brands: tuple[NameCount, ...]
    patterns: tuple[CompetitorPattern, ...]


@dataclass(frozen=True)
class CompetitorEvidence:
    category: str
    direct: CompetitorBucket
    marketplace: CompetitorBucket
    mixed: CompetitorBucket
    unknown: CompetitorBucket
    errors: tuple[str, ...] = ()


_DEFAULT_MARKETPLACE_DOMAINS: frozenset[str] = frozenset(
    {
        # Core marketplaces and multi-seller retailers (expand as needed)
        "amazon.com",
        "ebay.com",
        "etsy.com",
        "walmart.com",
        "wayfair.com",
        "homedepot.com",
        "lowes.com",
        "overstock.com",
    }
)

_DEFAULT_MARKETPLACE_SOURCES: frozenset[str] = frozenset(
    {
        # Matches competitor_listings.source values from the migration comment.
        "amazon",
        "wayfair",
        "homedepot",
        "walmart",
        "ebay",
        "etsy",
    }
)

_UNSAFE_COMPETITOR_LANGUAGE_PATTERNS = (
    re.compile(r"\bnot found in competitors?\b", re.IGNORECASE),
    re.compile(r"\bset(?:s)? this apart from competitors?\b", re.IGNORECASE),
    re.compile(r"\bbetter than\b", re.IGNORECASE),
    re.compile(r"\bsuperior\b", re.IGNORECASE),
    re.compile(r"\boutperform(?:s|ing)? competitors?\b", re.IGNORECASE),
    re.compile(r"\bbeat(?:s)? (?:the )?(?:competition|competitors?)\b", re.IGNORECASE),
)


def normalize_domain(value: str | None) -> str | None:
    """Normalize a domain or URL into a bare hostname.

    Examples:
        "www.amazon.com" -> "amazon.com"
        "https://www.wayfair.com/x" -> "wayfair.com"
    """
    if not value:
        return None

    raw = value.strip().lower()
    if not raw:
        return None

    # If we were handed a URL, parse hostname from it.
    parsed = None
    if "://" in raw:
        parsed = urlparse(raw)
    elif "/" in raw:
        parsed = urlparse("https://" + raw)

    host = (parsed.hostname if parsed else raw) if parsed else raw
    if not host:
        return None

    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _is_marketplace_domain(domain: str, marketplace_domains: frozenset[str]) -> bool:
    d = domain.strip().lower()
    if not d:
        return False
    for base in marketplace_domains:
        if d == base or d.endswith("." + base):
            return True
    return False


def _classify_listing_bucket(
    listing: dict[str, Any],
    *,
    marketplace_domains: frozenset[str],
    marketplace_sources: frozenset[str],
) -> Literal["direct", "marketplace", "unknown"]:
    source_type = (listing.get("source_type") or "").strip().lower()
    source = (listing.get("source") or "").strip().lower()
    domain = normalize_domain(listing.get("domain"))

    if source_type == "marketplace":
        return "marketplace"
    if source in marketplace_sources:
        return "marketplace"
    if domain and _is_marketplace_domain(domain, marketplace_domains):
        return "marketplace"
    if domain:
        return "direct"
    return "unknown"


def _classify_pattern_bucket(
    sources: Iterable[str] | None,
    *,
    marketplace_domains: frozenset[str],
) -> SourceBucket:
    if not sources:
        return "unknown"

    normalized = [normalize_domain(s) for s in sources]
    normalized = [s for s in normalized if s]
    if not normalized:
        return "unknown"

    marketplace = sum(1 for s in normalized if _is_marketplace_domain(s, marketplace_domains))
    direct = len(normalized) - marketplace

    if marketplace and not direct:
        return "marketplace"
    if direct and not marketplace:
        return "direct"
    return "mixed"


def _top_counts(values: Iterable[str | None], *, limit: int = 10) -> tuple[NameCount, ...]:
    counts: dict[str, int] = {}
    for v in values:
        if not v:
            continue
        key = v.strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1

    # Deterministic: count desc, then name asc
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(NameCount(name=k, count=c) for k, c in ordered[:limit])


def _fetch_competitor_listings(
    category: str,
    client: Any,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch competitor_listings rows for a category.

    Uses minimal columns needed for classification + summarization.
    """
    result = (
        client.table("competitor_listings")
        .select("source,source_type,domain,brand,title,position")
        .eq("product_category", category)
        .order("position", desc=False)
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def _fetch_competitor_patterns(
    category: str,
    client: Any,
    *,
    limit: int = 200,
    pattern_types: tuple[str, ...] = (
        "title_structure",
        "keyword",
        "benefit",
        "trust_signal",
        "competitor_brand",
    ),
) -> list[dict[str, Any]]:
    """Fetch competitor_patterns rows for a category."""
    q = (
        client.table("competitor_patterns")
        .select("pattern_type,pattern_value,frequency,avg_position,sources,example_titles")
        .eq("category", category)
    )
    if pattern_types:
        q = q.in_("pattern_type", list(pattern_types))
    q = q.order("frequency", desc=True).limit(limit)
    result = q.execute()
    return list(result.data or [])


def build_competitor_evidence(
    category: str,
    *,
    client: Any | None = None,
    max_listings_per_bucket: int = 25,
    max_patterns_per_bucket: int = 50,
    marketplace_domains: Iterable[str] | None = None,
    marketplace_sources: Iterable[str] | None = None,
) -> CompetitorEvidence:
    """Build competitor evidence for a given product category.

    Args:
        category: Product category (should match competitor_listings.product_category).
        client: Optional Supabase client (dependency injection for tests).
        max_listings_per_bucket: Used for counting/summary only (does not affect queries).
        max_patterns_per_bucket: Cap patterns returned per bucket for prompt-safety.
        marketplace_domains: Optional override set for marketplace domain detection.
        marketplace_sources: Optional override set for marketplace source detection.
    """
    errors: list[str] = []
    marketplace_domain_set = frozenset(marketplace_domains) if marketplace_domains else _DEFAULT_MARKETPLACE_DOMAINS
    marketplace_source_set = frozenset(marketplace_sources) if marketplace_sources else _DEFAULT_MARKETPLACE_SOURCES

    if client is None:
        if not is_supabase_available():
            return CompetitorEvidence(
                category=category,
                direct=CompetitorBucket(0, (), (), ()),
                marketplace=CompetitorBucket(0, (), (), ()),
                mixed=CompetitorBucket(0, (), (), ()),
                unknown=CompetitorBucket(0, (), (), ()),
                errors=("supabase_unavailable",),
            )
        try:
            client = get_client()
        except Exception as e:  # pragma: no cover
            return CompetitorEvidence(
                category=category,
                direct=CompetitorBucket(0, (), (), ()),
                marketplace=CompetitorBucket(0, (), (), ()),
                mixed=CompetitorBucket(0, (), (), ()),
                unknown=CompetitorBucket(0, (), (), ()),
                errors=(f"supabase_error:{type(e).__name__}",),
            )

    listings = _fetch_competitor_listings(category, client)
    patterns = _fetch_competitor_patterns(category, client)

    direct_listings: list[dict[str, Any]] = []
    marketplace_listings: list[dict[str, Any]] = []
    unknown_listings: list[dict[str, Any]] = []

    for row in listings:
        bucket = _classify_listing_bucket(
            row, marketplace_domains=marketplace_domain_set, marketplace_sources=marketplace_source_set
        )
        if bucket == "direct":
            direct_listings.append(row)
        elif bucket == "marketplace":
            marketplace_listings.append(row)
        else:
            unknown_listings.append(row)

    def listing_domain_rows(rows: list[dict[str, Any]]) -> list[str | None]:
        return [normalize_domain(r.get("domain")) for r in rows]

    def listing_brand_rows(rows: list[dict[str, Any]]) -> list[str | None]:
        return [((r.get("brand") or "").strip() or None) for r in rows]

    def _pos_key(row: dict[str, Any]) -> int:
        # Keep missing positions last and ensure deterministic ordering.
        pos = row.get("position")
        return int(pos) if isinstance(pos, int) else 10**9

    def _top_listings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if max_listings_per_bucket <= 0:
            return []
        return sorted(rows, key=_pos_key)[:max_listings_per_bucket]

    direct_summary = _top_listings(direct_listings)
    marketplace_summary = _top_listings(marketplace_listings)
    unknown_summary = _top_listings(unknown_listings)

    direct_bucket = CompetitorBucket(
        listing_count=len(direct_listings),
        top_domains=_top_counts(listing_domain_rows(direct_summary)),
        top_brands=_top_counts(listing_brand_rows(direct_summary)),
        patterns=(),
    )
    marketplace_bucket = CompetitorBucket(
        listing_count=len(marketplace_listings),
        top_domains=_top_counts(listing_domain_rows(marketplace_summary)),
        top_brands=_top_counts(listing_brand_rows(marketplace_summary)),
        patterns=(),
    )
    unknown_bucket = CompetitorBucket(
        listing_count=len(unknown_listings),
        top_domains=_top_counts(listing_domain_rows(unknown_summary)),
        top_brands=_top_counts(listing_brand_rows(unknown_summary)),
        patterns=(),
    )

    direct_patterns: list[CompetitorPattern] = []
    marketplace_patterns: list[CompetitorPattern] = []
    mixed_patterns: list[CompetitorPattern] = []
    unknown_patterns: list[CompetitorPattern] = []

    for row in patterns:
        bucket = _classify_pattern_bucket(row.get("sources"), marketplace_domains=marketplace_domain_set)
        sources_norm: list[str] = []
        for s in (row.get("sources") or []) or []:
            ns = normalize_domain(s)
            if ns:
                sources_norm.append(ns)
        pattern = CompetitorPattern(
            pattern_type=(row.get("pattern_type") or "").strip(),
            pattern_value=(row.get("pattern_value") or "").strip(),
            frequency=row.get("frequency"),
            avg_position=row.get("avg_position"),
            sources=tuple(sources_norm),
            example_titles=tuple((row.get("example_titles") or []) or []),
        )

        if not pattern.pattern_type or not pattern.pattern_value:
            continue

        if bucket == "direct":
            direct_patterns.append(pattern)
        elif bucket == "marketplace":
            marketplace_patterns.append(pattern)
        elif bucket == "mixed":
            mixed_patterns.append(pattern)
        else:
            unknown_patterns.append(pattern)

    # Deterministic ordering: pattern_type asc, frequency desc, pattern_value asc
    def sort_key(p: CompetitorPattern) -> tuple[str, int, str]:
        freq = int(p.frequency) if isinstance(p.frequency, int) else -1
        return (p.pattern_type, -freq, p.pattern_value)

    direct_patterns = sorted(direct_patterns, key=sort_key)[:max_patterns_per_bucket]
    marketplace_patterns = sorted(marketplace_patterns, key=sort_key)[:max_patterns_per_bucket]
    mixed_patterns = sorted(mixed_patterns, key=sort_key)[:max_patterns_per_bucket]
    unknown_patterns = sorted(unknown_patterns, key=sort_key)[:max_patterns_per_bucket]

    direct_bucket = CompetitorBucket(
        listing_count=direct_bucket.listing_count,
        top_domains=direct_bucket.top_domains,
        top_brands=direct_bucket.top_brands,
        patterns=tuple(direct_patterns),
    )
    marketplace_bucket = CompetitorBucket(
        listing_count=marketplace_bucket.listing_count,
        top_domains=marketplace_bucket.top_domains,
        top_brands=marketplace_bucket.top_brands,
        patterns=tuple(marketplace_patterns),
    )
    mixed_bucket = CompetitorBucket(
        listing_count=0,
        top_domains=(),
        top_brands=(),
        patterns=tuple(mixed_patterns),
    )
    unknown_bucket = CompetitorBucket(
        listing_count=unknown_bucket.listing_count,
        top_domains=unknown_bucket.top_domains,
        top_brands=unknown_bucket.top_brands,
        patterns=tuple(unknown_patterns),
    )

    return CompetitorEvidence(
        category=category,
        direct=direct_bucket,
        marketplace=marketplace_bucket,
        mixed=mixed_bucket,
        unknown=unknown_bucket,
        errors=tuple(errors),
    )


def _is_safe_pattern_value(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    return not any(p.search(text) for p in _UNSAFE_COMPETITOR_LANGUAGE_PATTERNS)


def _format_name_counts(counts: tuple[NameCount, ...], *, limit: int) -> str:
    if not counts or limit <= 0:
        return ""
    return ", ".join(f"{item.name} ({item.count})" for item in counts[:limit])


def _safe_pattern_values(
    patterns: tuple[CompetitorPattern, ...],
    *,
    max_patterns: int,
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if pattern.pattern_type not in {"keyword", "title_structure"}:
            continue
        value = (pattern.pattern_value or "").strip()
        if not _is_safe_pattern_value(value):
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        if len(values) >= max_patterns:
            break
    return values


def build_competitor_evidence_rows(
    competitor: CompetitorEvidence,
    *,
    max_domains: int = 5,
    max_patterns: int = 8,
) -> list["Evidence"]:
    """Convert competitor evidence into prompt-safe Evidence rows.

    Rows are intentionally framed as market-language context, not product facts.
    Unsafe comparative phrasing is removed before serialization.
    """
    from feedops.pipeline.enrichment import Evidence

    rows: list[Evidence] = []

    direct_domains = _format_name_counts(competitor.direct.top_domains, limit=max_domains)
    if direct_domains:
        rows.append(
            Evidence(
                field="competitor_direct_domains",
                value=f"Observed direct competitor domains: {direct_domains}",
                source="competitor_evidence_direct",
            )
        )

    marketplace_domains = _format_name_counts(
        competitor.marketplace.top_domains, limit=max_domains
    )
    if marketplace_domains:
        rows.append(
            Evidence(
                field="competitor_marketplace_domains",
                value=f"Observed marketplace domains: {marketplace_domains}",
                source="competitor_evidence_marketplace",
            )
        )

    direct_patterns = _safe_pattern_values(
        competitor.direct.patterns + competitor.mixed.patterns,
        max_patterns=max_patterns,
    )
    if direct_patterns:
        rows.append(
            Evidence(
                field="competitor_direct_language_patterns",
                value=(
                    "Observed direct competitor listing language (context only, not product facts): "
                    + ", ".join(direct_patterns)
                ),
                source="competitor_evidence_direct",
            )
        )

    marketplace_patterns = _safe_pattern_values(
        competitor.marketplace.patterns,
        max_patterns=max_patterns,
    )
    if marketplace_patterns:
        rows.append(
            Evidence(
                field="competitor_marketplace_language_patterns",
                value=(
                    "Observed marketplace listing language (context only, not product facts): "
                    + ", ".join(marketplace_patterns)
                ),
                source="competitor_evidence_marketplace",
            )
        )

    return rows
