"""
Propagation spot-check script: Supabase approved_content vs Google Sheets feed rows.

Compares approved titles and descriptions in Supabase against what actually landed
in the Google Sheets supplemental feed for 10-20 published SKUs.

Also quantifies the {FINISH_NAME} placeholder bug scope in approved_content.

Google Sheets access uses a Node.js helper (fetch_sheets_data.js) since the
service account private key in GOOGLE_SERVICE_ACCOUNT_KEY uses a non-standard RSA
modulus size rejected by Python's cryptography library but accepted by Node.js.

Usage:
    cd /Users/bobby/Documents/GitHub/Allied-FeedOps
    source .venv/bin/activate
    set -a && source .env.vercel && set +a
    python scripts/spot_check_propagation.py
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH  = PROJECT_ROOT / ".planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json"
NODE_HELPER  = SCRIPT_DIR / "fetch_sheets_data.js"


# ─────────────────────────────────────────────────────────────────────────────
# Supabase client
# ─────────────────────────────────────────────────────────────────────────────

def get_supabase_client():
    """Return an authenticated Supabase client."""
    from supabase import create_client

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. Set NEXT_PUBLIC_SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY)."
        )
    return create_client(url, key)


# ─────────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(text: str | None) -> str:
    """Normalize for comparison: decode HTML entities, collapse whitespace, strip."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


FINISH_PLACEHOLDER_TITLE = "{FINISH_NAME}"
FINISH_PLACEHOLDER_SENTENCE = "{FINISH_SENTENCE}"

# Regex that matches a leading finish-name token in titles
# e.g. "Antique Bronze 3 Inch" -> everything before " 3 Inch..."
# The idea: strip the first word/phrase up to the first non-finish word boundary.
# We use a simple heuristic: strip up to the first occurrence of a non-finish token.
# For comparison we blank out the leading finish name in both.
_LEADING_FINISH_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+",
)


FINISH_PLACEHOLDER_TITLE    = "{FINISH_NAME}"
FINISH_PLACEHOLDER_SENTENCE = "{FINISH_SENTENCE}"

# Sentence boundary for finish-sentence extraction: ends at a period followed by space/end
_SENTENCE_END_RE = re.compile(r"\.\s+")

# Leading Title-Cased word sequence (finish name like "Antique Bronze", "Pink", etc.)
_LEADING_FINISH_RE = re.compile(r"^(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+")


def _strip_leading_finish_name(text: str) -> str:
    """
    Strip a leading finish-name phrase from a title for structural comparison.

    Handles both the literal {FINISH_NAME} placeholder and actual finish names
    like "Antique Bronze" or "Pink".
    """
    text = text.strip()
    if text.startswith(FINISH_PLACEHOLDER_TITLE):
        return text[len(FINISH_PLACEHOLDER_TITLE):].lstrip()
    m = _LEADING_FINISH_RE.match(text)
    if m:
        return text[m.end():]
    return text


def _normalize_finish_sentence(text: str) -> str:
    """
    For descriptions: replace {FINISH_SENTENCE} (and its substituted equivalent)
    with a canonical token so both sides compare equal on structure.

    Strategy:
    - If Supabase text has {FINISH_SENTENCE}, replace it with "<<FINISH_SENTENCE>>".
    - For Sheets text (where the placeholder was substituted), detect the inserted
      sentence: it is the sentence(s) between the text before and after the placeholder
      position. We detect it by matching the text prefix/suffix from the Supabase version.
    """
    if FINISH_PLACEHOLDER_SENTENCE in text:
        return text.replace(FINISH_PLACEHOLDER_SENTENCE, "<<FINISH_SENTENCE>>").strip()
    return text


def _strip_finish_sentence_from_sheets(
    sheets_text: str,
    supabase_text: str,
) -> str:
    """
    Remove the substituted finish sentence from Sheets text so it matches
    the Supabase text (which still has the {FINISH_SENTENCE} placeholder).

    Algorithm:
    1. Split the Supabase text on {FINISH_SENTENCE} into prefix and suffix.
    2. Find those prefix/suffix positions in the Sheets text.
    3. Remove the text between them (the substituted finish sentence).
    4. Return the reconstructed text with <<FINISH_SENTENCE>> in place.
    """
    if FINISH_PLACEHOLDER_SENTENCE not in supabase_text:
        return sheets_text

    parts = supabase_text.split(FINISH_PLACEHOLDER_SENTENCE, 1)
    prefix = normalize_text(parts[0])
    suffix = normalize_text(parts[1]) if len(parts) > 1 else ""

    norm_sheets = normalize_text(sheets_text)

    if not prefix or not suffix:
        # Can't reliably find boundaries; return as-is
        return norm_sheets

    # Find where the prefix ends in the sheets text
    prefix_end_idx = norm_sheets.find(prefix)
    if prefix_end_idx == -1:
        return norm_sheets
    prefix_end_idx += len(prefix)

    # Find where the suffix starts (after the prefix end)
    suffix_start_idx = norm_sheets.find(suffix, prefix_end_idx)
    if suffix_start_idx == -1:
        return norm_sheets

    # Reconstruct: prefix + <<FINISH_SENTENCE>> + suffix
    return (
        norm_sheets[:prefix_end_idx].rstrip() + " <<FINISH_SENTENCE>> " +
        norm_sheets[suffix_start_idx:].lstrip()
    )


def meaningful_diff(supabase_val: str | None, sheets_val: str | None) -> tuple[bool, str]:
    """
    Compare two content values after structural normalization.

    Handles the expected differences between master-level Supabase approved_content
    (which has finish placeholders) and variant-level Sheets rows (where finish
    names and sentences have been substituted by expand-variants.ts).

    Returns:
        (is_match, diff_detail) — is_match=True means no meaningful structural difference.
    """
    norm_supa  = normalize_text(supabase_val)
    norm_sheet = normalize_text(sheets_val)

    if norm_supa == norm_sheet:
        return True, ""

    if not norm_supa and not norm_sheet:
        return True, ""

    if not norm_supa:
        return False, f"Supabase value is empty; Sheets has {len(norm_sheet)}-char value"

    if not norm_sheet:
        return False, f"Sheets cell is empty; Supabase has {len(norm_supa)}-char value"

    # ── Structural normalization ──────────────────────────────────────────────
    # 1. Strip leading finish name (title comparison)
    supa_stripped  = normalize_text(_strip_leading_finish_name(norm_supa))
    sheet_stripped = normalize_text(_strip_leading_finish_name(norm_sheet))

    # 2. Normalize {FINISH_SENTENCE} substitutions (description comparison)
    # a) Replace placeholder token in Supabase text
    supa_norm = _normalize_finish_sentence(supa_stripped)
    # b) Remove the substituted finish sentence from Sheets text
    sheet_norm = _strip_finish_sentence_from_sheets(sheet_stripped, supa_stripped)
    sheet_norm = _normalize_finish_sentence(sheet_norm)

    if supa_norm == sheet_norm:
        return True, ""

    supa_preview  = norm_supa[:80]  + ("..." if len(norm_supa) > 80 else "")
    sheet_preview = norm_sheet[:80] + ("..." if len(norm_sheet) > 80 else "")
    return False, f"Structural content differs. Supabase: '{supa_preview}' | Sheets: '{sheet_preview}'"


# ─────────────────────────────────────────────────────────────────────────────
# Google Sheets (via Node.js helper)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sheets_lookup() -> dict[str, dict[str, str]]:
    """
    Run the Node.js helper to fetch all offer IDs from the Sheets feed.

    Returns:
        {lowercase_offer_id: {"title": "...", "description": "..."}}

    Raises:
        RuntimeError if the Node.js helper fails.
    """
    if not NODE_HELPER.exists():
        raise RuntimeError(f"Node.js helper not found: {NODE_HELPER}")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["node", str(NODE_HELPER), tmp_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            raise RuntimeError(
                f"Node.js helper exited with code {result.returncode}:\n{result.stderr}"
            )

        with open(tmp_path) as f:
            data = json.load(f)

        # lookup: {lowercase_offer_id: {title, description}}
        lookup = data.get("lookup", {})
        print(f"[INFO] Sheets lookup loaded: {len(lookup)} offer IDs")
        return lookup

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Supabase queries
# ─────────────────────────────────────────────────────────────────────────────

def fetch_published_sku_sample(supa) -> list[dict]:
    """
    Build a representative 15-20 SKU sample from publish_events.

    Criteria:
    1. Up to 5 recently published  (last 30 days)
    2. Up to 5 older published     (30-90 days ago)
    3. Up to 5 high-value          (highest impressions, among published)
    4. Up to 3 random              (from remaining)
    """
    from datetime import timedelta

    now            = datetime.now(timezone.utc)
    recent_cutoff  = (now - timedelta(days=30)).isoformat()
    older_start    = (now - timedelta(days=90)).isoformat()
    older_end      = recent_cutoff

    resp = (
        supa.table("publish_events")
        .select("master_sku, published_at")
        .eq("status", "success")
        .eq("action", "publish")
        .order("published_at", desc=True)
        .execute()
    )
    all_events: list[dict] = resp.data or []

    # Deduplicate — keep most recent publish per SKU
    seen: dict[str, str] = {}
    for ev in all_events:
        sku = ev["master_sku"]
        if sku not in seen:
            seen[sku] = ev["published_at"]

    all_published = [{"master_sku": s, "published_at": t} for s, t in seen.items()]

    if not all_published:
        print("[WARN] No published SKUs found in publish_events.")
        return []

    recent_skus = [p for p in all_published if p["published_at"] >= recent_cutoff]
    older_skus  = [p for p in all_published if older_start <= p["published_at"] < older_end]

    sample: list[dict] = []

    for p in recent_skus[:5]:
        sample.append({**p, "selection_reason": "recently_published"})
    for p in older_skus[:5]:
        sample.append({**p, "selection_reason": "older_published"})

    # High-value by impression volume
    try:
        hv_resp = (
            supa.table("search_queries")
            .select("master_sku, impressions")
            .order("impressions", desc=True)
            .limit(200)
            .execute()
        )
        hv_totals: dict[str, int] = {}
        for row in hv_resp.data or []:
            ms  = row.get("master_sku")
            imp = row.get("impressions") or 0
            if ms:
                hv_totals[ms] = hv_totals.get(ms, 0) + imp

        already  = {s["master_sku"] for s in sample}
        pub_set  = {p["master_sku"] for p in all_published}
        pub_at   = {p["master_sku"]: p["published_at"] for p in all_published}
        hv_cands = [
            ms for ms, _ in sorted(hv_totals.items(), key=lambda x: -x[1])
            if ms in pub_set and ms not in already
        ]
        for ms in hv_cands[:5]:
            sample.append({
                "master_sku": ms,
                "published_at": pub_at.get(ms, ""),
                "selection_reason": "high_value",
            })
    except Exception as e:
        print(f"[WARN] Could not fetch high-value SKUs: {e}")

    # Random fill
    import random
    already = {s["master_sku"] for s in sample}
    pool    = [p for p in all_published if p["master_sku"] not in already]
    random.seed(42)
    for p in random.sample(pool, min(3, len(pool))):
        sample.append({**p, "selection_reason": "random"})

    # Ensure at least 10 if available
    if len(sample) < 10:
        already = {s["master_sku"] for s in sample}
        extras  = [p for p in all_published if p["master_sku"] not in already]
        for p in extras[: 10 - len(sample)]:
            sample.append({**p, "selection_reason": "fill"})

    print(f"[INFO] Sample assembled: {len(sample)} SKUs")
    return sample


def fetch_approved_content(supa, master_skus: list[str]) -> dict[str, dict[str, str]]:
    """Fetch approved_content (platform=google) for master_skus."""
    if not master_skus:
        return {}
    resp = (
        supa.table("generated_content")
        .select("master_sku, content_type, approved_content")
        .eq("platform", "google")
        .in_("master_sku", master_skus)
        .not_.is_("approved_content", "null")
        .execute()
    )
    content: dict[str, dict[str, str]] = {}
    for row in resp.data or []:
        sku = row["master_sku"]
        ct  = row["content_type"]
        val = row["approved_content"] or ""
        content.setdefault(sku, {})[ct] = val
    return content


def fetch_offer_ids(supa, master_skus: list[str]) -> dict[str, list[dict]]:
    """
    Fetch all gmc_offer_id and finish values from variant_index for master_skus.

    Returns:
        {master_sku: [{"gmc_offer_id": "...", "finish": "..."}, ...]}
    """
    if not master_skus:
        return {}
    resp = (
        supa.table("variant_index")
        .select("master_sku, gmc_offer_id, finish")
        .in_("master_sku", master_skus)
        .execute()
    )
    result: dict[str, list[dict]] = {}
    for row in resp.data or []:
        sku = row["master_sku"]
        oid = row.get("gmc_offer_id")
        if sku and oid:
            result.setdefault(sku, []).append({
                "gmc_offer_id": oid,
                "finish": row.get("finish") or "",
            })
    return result


def fetch_finish_name_bug(supa) -> dict:
    """Count generated_content rows with literal '{FINISH_NAME}' in approved_content."""
    placeholder = "{FINISH_NAME}"
    resp = (
        supa.table("generated_content")
        .select("master_sku, platform, content_type")
        .like("approved_content", f"%{placeholder}%")
        .execute()
    )
    rows = resp.data or []
    affected_skus = sorted({r["master_sku"] for r in rows})
    return {
        "affected_skus": affected_skus,
        "total_affected_rows": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_spot_check() -> None:
    print("=" * 60)
    print("Allied-FeedOps: Propagation Spot-Check")
    print("Supabase approved_content vs Google Sheets SupplementalFeedData")
    print("=" * 60)

    # ── Supabase ─────────────────────────────────────────────────────────────
    supa = get_supabase_client()
    print("[OK] Supabase client ready")

    # ── {FINISH_NAME} bug scope ───────────────────────────────────────────────
    fn_placeholder = "{FINISH_NAME}"
    print(f"\n[INFO] Querying {fn_placeholder} bug scope...")
    finish_name_bug = fetch_finish_name_bug(supa)
    bug_row_count   = finish_name_bug["total_affected_rows"]
    bug_sku_count   = len(finish_name_bug["affected_skus"])
    print(f"[INFO] {fn_placeholder} bug: {bug_row_count} rows across {bug_sku_count} SKUs")

    # ── Google Sheets ─────────────────────────────────────────────────────────
    sheets_available = False
    sheets_lookup: dict[str, dict[str, str]] = {}
    sheets_error = ""

    try:
        print("\n[INFO] Loading Google Sheets data via Node.js helper...")
        sheets_lookup     = fetch_sheets_lookup()
        sheets_available  = True
        print("[OK] Sheets data ready")
    except Exception as e:
        sheets_error = str(e)
        print(f"[WARN] Google Sheets unavailable: {e}")
        print("[INFO] Outputting partial results (Supabase-only).")

    if not sheets_available:
        result = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "sheets_error": sheets_error,
            "summary": {
                "total_checked": 0,
                "title_matched": 0,
                "description_matched": 0,
                "total_matched": 0,
                "total_with_discrepancy": 0,
                "finish_name_bug_count": bug_row_count,
            },
            "skus": [],
            "finish_name_bug": finish_name_bug,
        }
        _write_and_print(result)
        return

    # ── SKU sample ────────────────────────────────────────────────────────────
    print("\n[INFO] Assembling SKU sample from publish_events...")
    sample = fetch_published_sku_sample(supa)

    if not sample:
        print("[WARN] No published SKUs found.")
        result = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_checked": 0,
                "title_matched": 0,
                "description_matched": 0,
                "total_matched": 0,
                "total_with_discrepancy": 0,
                "finish_name_bug_count": bug_row_count,
            },
            "skus": [],
            "finish_name_bug": finish_name_bug,
        }
        _write_and_print(result)
        return

    sample_skus = [s["master_sku"] for s in sample]

    # ── Fetch Supabase data ───────────────────────────────────────────────────
    print("[INFO] Fetching approved_content from Supabase...")
    approved = fetch_approved_content(supa, sample_skus)
    print(f"[INFO] Got approved content for {len(approved)} / {len(sample_skus)} SKUs")

    print("[INFO] Fetching offer IDs from variant_index...")
    offer_ids_by_sku = fetch_offer_ids(supa, sample_skus)
    print(f"[INFO] Found offer IDs for {len(offer_ids_by_sku)} SKUs")

    # ── Per-SKU comparison ────────────────────────────────────────────────────
    sku_results:         list[dict] = []
    title_matched_count  = 0
    desc_matched_count   = 0
    total_matched_count  = 0

    for entry in sample:
        sku    = entry["master_sku"]
        reason = entry["selection_reason"]
        pub_at = entry.get("published_at", "")

        content    = approved.get(sku, {})
        supa_title = content.get("title")
        supa_desc  = content.get("description")

        variants = offer_ids_by_sku.get(sku, [])

        has_fn_placeholder = (
            fn_placeholder in (supa_title or "") or
            fn_placeholder in (supa_desc  or "")
        )

        # ── Find all matching Sheets rows for this SKU ────────────────────────
        # Compare Supabase master content (with finish placeholders) against
        # each variant's Sheets row.
        # Strategy: for each variant, substitute the finish name into the
        # approved_content title (replacing {FINISH_NAME}) and compare.
        # If ANY variant matches → propagation is correct for that field.
        # Count ALL rows found regardless of match status for accurate reporting.
        rows_found         = 0
        sheet_title_sample: str | None = None  # first matched row title (for reporting)
        sheet_desc_sample:  str | None = None

        title_any_match = False
        desc_any_match  = False
        title_diff_sample = ""
        desc_diff_sample  = ""

        for variant in variants:
            raw_oid = variant["gmc_offer_id"]
            finish  = variant.get("finish") or ""
            gmc_id  = raw_oid.replace("shopify_us_", "shopify_US_")
            row_data = sheets_lookup.get(gmc_id.lower())
            if not row_data:
                continue
            rows_found += 1
            sheet_t = row_data.get("title")
            sheet_d = row_data.get("description")

            if sheet_title_sample is None:
                sheet_title_sample = sheet_t
                sheet_desc_sample  = sheet_d

            # For comparison: substitute the actual finish name into the
            # Supabase approved_content so we can do an exact comparison.
            effective_title = (supa_title or "").replace(fn_placeholder, finish) if finish else (supa_title or "")
            effective_desc  = supa_desc  # description uses {FINISH_SENTENCE} which meaningful_diff handles

            t_match, t_diff = meaningful_diff(effective_title, sheet_t)
            d_match, d_diff = meaningful_diff(effective_desc,  sheet_d)

            if t_match and not title_any_match:
                title_any_match = True
            if d_match and not desc_any_match:
                desc_any_match  = True

            # Store the first non-matching diff for reporting
            if not t_match and not title_diff_sample:
                title_diff_sample = t_diff
            if not d_match and not desc_diff_sample:
                desc_diff_sample  = d_diff

        # (Do not break early — count ALL rows for accurate reporting)

        if not supa_title and not supa_desc:
            sku_results.append({
                "master_sku":                sku,
                "selection_reason":          reason,
                "published_at":              pub_at[:10] if pub_at else "",
                "offer_ids_checked":         len(variants),
                "rows_found_in_sheet":       rows_found,
                "title_match":               False,
                "description_match":         False,
                "discrepancy_detail":        "No approved_content in Supabase (platform='google')",
                "has_finish_name_placeholder": False,
                "supabase_title_length":     0,
                "supabase_desc_length":      0,
                "sheets_title_length":       len(normalize_text(sheet_title_sample)),
                "sheets_desc_length":        len(normalize_text(sheet_desc_sample)),
            })
            continue

        if rows_found == 0:
            title_any_match  = False
            desc_any_match   = False
            title_diff_sample = "No matching offer IDs found in Google Sheets"
            desc_diff_sample  = "No matching offer IDs found in Google Sheets"

        both_match = title_any_match and desc_any_match

        if title_any_match:
            title_matched_count += 1
        if desc_any_match:
            desc_matched_count += 1
        if both_match:
            total_matched_count += 1

        diff_parts = []
        if not title_any_match:
            diff_parts.append(f"Title: {title_diff_sample}")
        if not desc_any_match:
            diff_parts.append(f"Description: {desc_diff_sample}")

        sku_results.append({
            "master_sku":                sku,
            "selection_reason":          reason,
            "published_at":              pub_at[:10] if pub_at else "",
            "offer_ids_checked":         len(variants),
            "rows_found_in_sheet":       rows_found,
            "title_match":               title_any_match,
            "description_match":         desc_any_match,
            "discrepancy_detail":        "; ".join(diff_parts),
            "has_finish_name_placeholder": has_fn_placeholder,
            "supabase_title_length":     len(supa_title or ""),
            "supabase_desc_length":      len(supa_desc  or ""),
            "sheets_title_length":       len(normalize_text(sheet_title_sample)),
            "sheets_desc_length":        len(normalize_text(sheet_desc_sample)),
        })

    total_checked          = len(sku_results)
    total_with_discrepancy = total_checked - total_matched_count

    result = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_checked":          total_checked,
            "title_matched":          title_matched_count,
            "description_matched":    desc_matched_count,
            "total_matched":          total_matched_count,
            "total_with_discrepancy": total_with_discrepancy,
            "finish_name_bug_count":  bug_row_count,
        },
        "skus": sku_results,
        "finish_name_bug": finish_name_bug,
    }

    _write_and_print(result)


def _write_and_print(result: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n[OK] Results written to {OUTPUT_PATH}")

    s   = result.get("summary", {})
    fn  = result.get("finish_name_bug", {})

    print("\n" + "=" * 60)
    print("SPOT-CHECK SUMMARY")
    print("=" * 60)
    print(f"  Timestamp          : {result.get('run_timestamp', 'N/A')}")
    print(f"  SKUs checked       : {s.get('total_checked', 0)}")
    print(f"  Title matched      : {s.get('title_matched', 0)} / {s.get('total_checked', 0)}")
    print(f"  Description matched: {s.get('description_matched', 0)} / {s.get('total_checked', 0)}")
    print(f"  Both matched       : {s.get('total_matched', 0)} / {s.get('total_checked', 0)}")
    print(f"  Discrepancies      : {s.get('total_with_discrepancy', 0)}")
    print(f"  {{FINISH_NAME}} bug  : {s.get('finish_name_bug_count', 0)} rows in DB")

    if fn.get("affected_skus"):
        print(f"  Affected SKUs      : {', '.join(fn['affected_skus'])}")

    if result.get("sheets_error"):
        print(f"\n  [WARN] Sheets unavailable: {result['sheets_error']}")

    skus = result.get("skus", [])
    if skus:
        print("\nPer-SKU breakdown:")
        hdr = f"  {'SKU':<20} {'Reason':<22} {'Published':<12} {'Title':<8} {'Desc':<8} {'Rows':<6} Note"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for sk in skus:
            title_ok = "OK"   if sk.get("title_match")       else "DIFF"
            desc_ok  = "OK"   if sk.get("description_match") else "DIFF"
            rows     = sk.get("rows_found_in_sheet", 0)
            note     = ""
            if sk.get("has_finish_name_placeholder"):
                note = "{FINISH_NAME} bug"
            elif sk.get("discrepancy_detail"):
                note = sk["discrepancy_detail"][:60]
            print(
                f"  {sk['master_sku']:<20} {sk.get('selection_reason',''):<22} "
                f"{sk.get('published_at',''):<12} {title_ok:<8} {desc_ok:<8} {rows:<6} {note}"
            )
    print("=" * 60)


if __name__ == "__main__":
    run_spot_check()
